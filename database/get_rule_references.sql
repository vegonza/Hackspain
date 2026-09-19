CREATE OR REPLACE FUNCTION public.normalize_order_key(p_value TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET search_path = public
AS $$
    SELECT upper(btrim(p_value, U&'\0009\000A\000B\000C\000D\001C\001D\001E\001F\0020\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000'));
$$;

REVOKE ALL ON FUNCTION public.normalize_order_key(TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.normalize_order_key(TEXT) TO service_role;

CREATE UNIQUE INDEX IF NOT EXISTS orders_normalized_key_idx
    ON public.orders (public.normalize_order_key(order_id));
CREATE INDEX IF NOT EXISTS erp_entries_snapshot_normalized_order_idx
    ON public.erp_entries (snapshot_id, public.normalize_order_key(order_id));

CREATE OR REPLACE FUNCTION public.get_rule_references(p_document_id UUID, p_order_key TEXT)
RETURNS JSONB
LANGUAGE plpgsql STABLE
SET search_path = public
AS $$
DECLARE
    pinned_snapshot UUID;
    result JSONB;
BEGIN
    SELECT erp_snapshot_id INTO pinned_snapshot
    FROM public.documents WHERE id = p_document_id AND deleted_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Document not found';
    END IF;
    IF pinned_snapshot IS NULL THEN
        RAISE EXCEPTION 'Document has no ERP snapshot';
    END IF;

    WITH matching_orders AS MATERIALIZED (
        SELECT * FROM public.orders
        WHERE public.normalize_order_key(order_id) = public.normalize_order_key(p_order_key)
          AND public.normalize_order_key(p_order_key) <> ''
    ), chosen_order AS (
        SELECT * FROM matching_orders WHERE (SELECT count(*) FROM matching_orders) = 1
    )
    SELECT jsonb_build_object(
        'order', (SELECT to_jsonb(o) || jsonb_build_object('amount', o.amount::text) FROM chosen_order o),
        'order_ambiguous', (SELECT count(*) > 1 FROM matching_orders),
        'supplier', (SELECT to_jsonb(s) FROM public.suppliers s JOIN chosen_order o USING (supplier_id)),
        'entries', (
            SELECT coalesce(jsonb_agg(to_jsonb(e) || jsonb_build_object('amount', e.amount::text)
                                     ORDER BY e.entry_id, e.id), '[]'::jsonb)
            FROM public.erp_entries e
            WHERE e.snapshot_id = pinned_snapshot
              AND public.normalize_order_key(e.order_id) = public.normalize_order_key(p_order_key)
              AND public.normalize_order_key(p_order_key) <> ''
        )
    ) INTO result;
    RETURN result;
END;
$$;

REVOKE ALL ON FUNCTION public.get_rule_references(UUID, TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_rule_references(UUID, TEXT) TO service_role;
