ALTER TABLE public.documents ADD COLUMN IF NOT EXISTS payment_decision JSONB;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS claimed_by_document_id UUID REFERENCES public.documents(id);
CREATE INDEX IF NOT EXISTS orders_claimed_document_idx ON public.orders (claimed_by_document_id)
    WHERE claimed_by_document_id IS NOT NULL;

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
BEGIN
    UPDATE public.documents SET payment_decision = p_decision
    WHERE id = p_document_id AND deleted_at IS NULL
      AND public.normalize_order_key(purchase_order) = public.normalize_order_key(p_order_key)
      AND (p_decision->>'classification' <> 'PAGAR' OR EXISTS (
          SELECT 1 FROM public.orders WHERE public.normalize_order_key(order_id) = public.normalize_order_key(p_order_key)
          AND claimed_by_document_id = p_document_id
      ));
    IF NOT FOUND THEN RAISE EXCEPTION 'Document changed or order claim was lost'; END IF;
    RETURN p_decision;
END;
$$;

REVOKE ALL ON FUNCTION public.release_document_order_claim() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.claim_invoice_order(UUID, TEXT) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.publish_payment_decision(UUID, TEXT, JSONB) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.release_document_order_claim() TO service_role;
GRANT EXECUTE ON FUNCTION public.claim_invoice_order(UUID, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION public.publish_payment_decision(UUID, TEXT, JSONB) TO service_role;
