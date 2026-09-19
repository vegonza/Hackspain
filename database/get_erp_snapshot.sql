-- A scalar JSON result keeps the complete entry list outside PostgREST's row limit.
CREATE OR REPLACE FUNCTION public.get_erp_snapshot()
RETURNS JSONB
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT to_jsonb(s) || jsonb_build_object('entries', (
        SELECT coalesce(jsonb_agg(
            (to_jsonb(e) - 'snapshot_id') || jsonb_build_object('amount', e.amount::text)
            ORDER BY e.entry_id, e.id
        ), '[]'::jsonb)
        FROM public.erp_entries e
        WHERE e.snapshot_id = s.id
    ))
    FROM (
        SELECT * FROM public.erp_snapshots
        ORDER BY fetched_at DESC, id DESC
        LIMIT 1
    ) s;
$$;

REVOKE ALL ON FUNCTION public.get_erp_snapshot() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_erp_snapshot() TO service_role;
