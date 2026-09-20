ALTER TABLE public.documents ADD COLUMN IF NOT EXISTS payment_decision JSONB;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS claimed_by_document_id UUID REFERENCES public.documents(id);
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS claim_conflicted BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS orders_claimed_document_idx ON public.orders (claimed_by_document_id)
    WHERE claimed_by_document_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_approved_invoice_identity
    ON public.documents ((public.normalize_tax_id(COALESCE(supplier_nif, ''))), (upper(regexp_replace(COALESCE(invoice_number, ''), '^[[:space:]]+|[[:space:]]+$', '', 'g'))))
    WHERE deleted_at IS NULL AND payment_decision->>'classification' = 'PAGAR';

CREATE OR REPLACE FUNCTION public.order_conflict_decision(p_decision JSONB)
RETURNS JSONB LANGUAGE sql IMMUTABLE STRICT SET search_path = public AS $$
    SELECT CASE WHEN p_decision->'resolution' IS NOT NULL AND p_decision->'resolution' <> 'null'::jsonb
        THEN p_decision ELSE p_decision || jsonb_build_object(
        'classification', CASE WHEN p_decision->>'classification' = 'NO_PAGAR' THEN 'NO_PAGAR' ELSE 'ESCALAR' END,
        'checks', (p_decision->'checks') || '{"order_claim": false, "order_unique": false}'::jsonb,
        'reasons', CASE WHEN p_decision->>'classification' = 'PAGAR' THEN '[]'::jsonb
                       ELSE p_decision->'reasons' END
            || CASE WHEN p_decision->'reasons' @> jsonb_build_array('Varias facturas reclaman el mismo pedido; revisar antes de autorizar el pago.')
                    THEN '[]'::jsonb
                    ELSE jsonb_build_array('Varias facturas reclaman el mismo pedido; revisar antes de autorizar el pago.') END) END;
$$;

CREATE OR REPLACE FUNCTION public.release_document_order_claim()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF NEW.deleted_at IS NOT NULL OR public.normalize_order_key(NEW.purchase_order)
        IS DISTINCT FROM public.normalize_order_key(OLD.purchase_order) THEN
        PERFORM 1 FROM public.orders
        WHERE public.normalize_order_key(order_id) = public.normalize_order_key(OLD.purchase_order)
        FOR UPDATE;
        -- A BEFORE trigger still sees OLD in documents; exclude the departing invoice.
        UPDATE public.orders SET
            claimed_by_document_id = CASE WHEN claimed_by_document_id = OLD.id THEN NULL
                                         ELSE claimed_by_document_id END,
            claim_conflicted = (
                SELECT count(*) > 1 FROM public.documents
                WHERE deleted_at IS NULL AND id <> OLD.id
                  AND public.normalize_order_key(purchase_order) = public.normalize_order_key(OLD.purchase_order)
            )
        WHERE public.normalize_order_key(order_id) = public.normalize_order_key(OLD.purchase_order);
        NEW.payment_decision := NULL;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER documents_release_order_claim
BEFORE UPDATE OF deleted_at, purchase_order ON public.documents
FOR EACH ROW EXECUTE FUNCTION public.release_document_order_claim();

CREATE OR REPLACE FUNCTION public.claim_invoice_order(p_document_id UUID, p_order_key TEXT)
RETURNS UUID LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    conflicted BOOLEAN;
    key TEXT := public.normalize_order_key(p_order_key);
BEGIN
    -- Claims and publications lock the order before touching its invoices.
    PERFORM 1 FROM public.orders
    WHERE public.normalize_order_key(order_id) = key AND key <> '' FOR UPDATE;
    IF NOT FOUND THEN RETURN NULL; END IF;

    PERFORM 1 FROM public.documents WHERE id = p_document_id AND deleted_at IS NULL
        AND public.normalize_order_key(purchase_order) = key FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Document extraction changed or document was deleted'; END IF;
    SELECT EXISTS (
        SELECT 1 FROM public.documents
        WHERE deleted_at IS NULL AND id <> p_document_id
          AND public.normalize_order_key(purchase_order) = key
    ) INTO conflicted;

    UPDATE public.orders SET claim_conflicted = conflicted,
        claimed_by_document_id = CASE WHEN conflicted THEN NULL ELSE p_document_id END
    WHERE public.normalize_order_key(order_id) = key;

    IF conflicted THEN
        UPDATE public.documents SET payment_decision = public.order_conflict_decision(payment_decision)
        WHERE deleted_at IS NULL
          AND public.normalize_order_key(purchase_order) = key AND payment_decision IS NOT NULL;
        RETURN NULL;
    END IF;

    RETURN p_document_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.publish_payment_decision(p_document_id UUID, p_order_key TEXT, p_decision JSONB)
RETURNS JSONB LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    document public.documents%ROWTYPE;
    decision JSONB := p_decision;
    violated_constraint TEXT;
    owner UUID;
    conflicted BOOLEAN;
    key TEXT := public.normalize_order_key(p_order_key);
BEGIN
    SELECT claimed_by_document_id, claim_conflicted INTO owner, conflicted FROM public.orders
    WHERE public.normalize_order_key(order_id) = key FOR UPDATE;
    SELECT * INTO document FROM public.documents
    WHERE id = p_document_id AND deleted_at IS NULL
      AND public.normalize_order_key(purchase_order) = public.normalize_order_key(p_order_key)
    FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Document changed or document was deleted'; END IF;

    IF document.payment_decision->'resolution' IS NOT NULL
       AND document.payment_decision->'resolution' <> 'null'::jsonb THEN
        RETURN document.payment_decision;
    END IF;

    IF conflicted THEN
        decision := public.order_conflict_decision(decision);
    END IF;

    IF decision->>'classification' = 'PAGAR' THEN
        IF public.normalize_tax_id(COALESCE(document.supplier_nif, '')) = ''
           OR regexp_replace(COALESCE(document.invoice_number, ''), '[[:space:]]', '', 'g') = '' THEN
            decision := decision || jsonb_build_object(
                'classification', 'ESCALAR',
                'reasons', jsonb_build_array('No se puede comprobar si la factura está duplicada: falta el NIF o el número de factura.'),
                'checks', (decision->'checks') || '{"invoice_identity": false}'::jsonb);
        ELSE
            IF owner IS DISTINCT FROM p_document_id THEN RAISE EXCEPTION 'Order claim was lost'; END IF;
            decision := decision || jsonb_build_object(
                'checks', (decision->'checks') || '{"invoice_identity": true, "invoice_unique": true}'::jsonb);
        END IF;
    END IF;

    BEGIN
        UPDATE public.documents SET payment_decision = decision WHERE id = p_document_id;
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
        IF violated_constraint <> 'idx_documents_approved_invoice_identity' THEN RAISE; END IF;
        decision := decision || jsonb_build_object(
            'classification', 'ESCALAR',
            'reasons', jsonb_build_array('Ya existe otra factura aprobada para pago con este proveedor y número de factura.'),
            'checks', (decision->'checks') || '{"invoice_unique": false}'::jsonb);
        UPDATE public.documents SET payment_decision = decision WHERE id = p_document_id;
    END;
    RETURN decision;
END;
$$;

REVOKE ALL ON FUNCTION public.release_document_order_claim() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.claim_invoice_order(UUID, TEXT) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.publish_payment_decision(UUID, TEXT, JSONB) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.release_document_order_claim() TO service_role;
GRANT EXECUTE ON FUNCTION public.claim_invoice_order(UUID, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION public.publish_payment_decision(UUID, TEXT, JSONB) TO service_role;

REVOKE ALL ON FUNCTION public.order_conflict_decision(JSONB) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.order_conflict_decision(JSONB) TO service_role;

CREATE OR REPLACE FUNCTION public.resolve_invoice_decision(p_document_id UUID, p_classification TEXT)
RETURNS JSONB LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    invoice public.documents%ROWTYPE;
    order_key TEXT;
    decision JSONB;
    violated_constraint TEXT;
BEGIN
    IF p_classification NOT IN ('PAGAR', 'NO_PAGAR') OR p_classification IS NULL THEN
        RAISE EXCEPTION 'invoice_not_reviewable';
    END IF;

    SELECT public.normalize_order_key(purchase_order) INTO order_key
    FROM public.documents WHERE id = p_document_id AND deleted_at IS NULL;
    PERFORM 1 FROM public.orders WHERE public.normalize_order_key(order_id) = order_key FOR UPDATE;
    SELECT * INTO invoice FROM public.documents
    WHERE id = p_document_id AND deleted_at IS NULL FOR UPDATE;
    IF NOT FOUND OR invoice.status <> 'ready'
       OR invoice.payment_decision->>'classification' IS DISTINCT FROM 'ESCALAR'
       OR public.normalize_order_key(invoice.purchase_order) IS DISTINCT FROM order_key THEN
        RAISE EXCEPTION 'invoice_not_reviewable';
    END IF;

    IF p_classification = 'PAGAR' AND (
        public.normalize_tax_id(COALESCE(invoice.supplier_nif, '')) = ''
        OR regexp_replace(COALESCE(invoice.invoice_number, ''), '[[:space:]]', '', 'g') = ''
    ) THEN
        RAISE EXCEPTION 'invoice_identity_required';
    END IF;

    decision := invoice.payment_decision || jsonb_build_object(
        'classification', p_classification,
        'resolution', jsonb_build_object('resolved_at', now(), 'previous_reasons', invoice.payment_decision->'reasons'),
        'reasons', jsonb_build_array(CASE WHEN p_classification = 'PAGAR'
            THEN 'Resuelta manualmente: pagar.' ELSE 'Resuelta manualmente: no pagar.' END));
    BEGIN
        UPDATE public.documents SET payment_decision = decision WHERE id = p_document_id;
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
        IF violated_constraint <> 'idx_documents_approved_invoice_identity' THEN RAISE; END IF;
        RAISE EXCEPTION 'invoice_duplicate_payment';
    END;
    RETURN jsonb_build_object('name', invoice.name, 'decision', decision);
END;
$$;

REVOKE ALL ON FUNCTION public.resolve_invoice_decision(UUID, TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.resolve_invoice_decision(UUID, TEXT) TO service_role;
