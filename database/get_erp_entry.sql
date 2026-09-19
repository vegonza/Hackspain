CREATE OR REPLACE FUNCTION public.get_erp_entry(p_entry_id UUID)
RETURNS JSONB
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT (to_jsonb(e) - 'snapshot_id') || jsonb_build_object(
        'amount', e.amount::text,
        'documents', (
            SELECT coalesce(jsonb_agg(
                jsonb_build_object('id', d.id, 'name', d.name) ORDER BY d.name, d.id
            ), '[]'::jsonb)
            FROM public.documents d
            WHERE d.erp_entry_id = e.id AND d.deleted_at IS NULL
        )
    )
    FROM public.erp_entries e
    WHERE e.id = p_entry_id;
$$;

REVOKE ALL ON FUNCTION public.get_erp_entry(UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_erp_entry(UUID) TO service_role;
