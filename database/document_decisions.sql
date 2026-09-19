ALTER TABLE public.documents ADD COLUMN IF NOT EXISTS payment_decision JSONB;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS claimed_by_document_id UUID REFERENCES public.documents(id);
CREATE INDEX IF NOT EXISTS orders_claimed_document_idx ON public.orders (claimed_by_document_id)
    WHERE claimed_by_document_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_approved_invoice_identity
    ON public.documents ((upper(regexp_replace(COALESCE(supplier_nif, ''), '[[:space:]]', '', 'g'))), (upper(regexp_replace(COALESCE(invoice_number, ''), '^[[:space:]]+|[[:space:]]+$', '', 'g'))))
    WHERE deleted_at IS NULL AND payment_decision->>'classification' = 'PAGAR';

CREATE OR REPLACE FUNCTION public.release_document_order_claim()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF NEW.deleted_at IS NOT NULL OR public.normalize_order_key(NEW.purchase_order)
        IS DISTINCT FROM public.normalize_order_key(OLD.purchase_order) THEN
        UPDATE public.orders SET claimed_by_document_id = NULL WHERE claimed_by_document_id = OLD.id;
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
    owner UUID;
    key TEXT := public.normalize_order_key(p_order_key);
BEGIN
    PERFORM 1 FROM public.documents WHERE id = p_document_id AND deleted_at IS NULL
        AND public.normalize_order_key(purchase_order) = key FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Document extraction changed or document was deleted'; END IF;
    UPDATE public.orders SET claimed_by_document_id = p_document_id
    WHERE public.normalize_order_key(order_id) = key AND key <> ''
      AND (claimed_by_document_id IS NULL OR claimed_by_document_id = p_document_id)
    RETURNING claimed_by_document_id INTO owner;
    IF FOUND THEN RETURN owner; END IF;
    SELECT claimed_by_document_id INTO owner FROM public.orders WHERE public.normalize_order_key(order_id) = key;
    RETURN owner;
END;
$$;

CREATE OR REPLACE FUNCTION public.publish_payment_decision(p_document_id UUID, p_order_key TEXT, p_decision JSONB)
RETURNS JSONB LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    document public.documents%ROWTYPE;
    decision JSONB := p_decision;
    violated_constraint TEXT;
BEGIN
    SELECT * INTO document FROM public.documents
    WHERE id = p_document_id AND deleted_at IS NULL
      AND public.normalize_order_key(purchase_order) = public.normalize_order_key(p_order_key)
    FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Document changed or document was deleted'; END IF;

    IF decision->>'classification' = 'PAGAR' THEN
        IF regexp_replace(COALESCE(document.supplier_nif, ''), '[[:space:]]', '', 'g') = ''
           OR regexp_replace(COALESCE(document.invoice_number, ''), '[[:space:]]', '', 'g') = '' THEN
            decision := decision || jsonb_build_object(
                'classification', 'ESCALAR',
                'reasons', jsonb_build_array('No se puede comprobar si la factura está duplicada: falta el NIF o el número de factura.'),
                'checks', (decision->'checks') || '{"invoice_identity": false}'::jsonb);
        ELSE
            PERFORM 1 FROM public.orders
            WHERE public.normalize_order_key(order_id) = public.normalize_order_key(p_order_key)
              AND claimed_by_document_id = p_document_id FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'Order claim was lost'; END IF;
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
