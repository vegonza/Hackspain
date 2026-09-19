CREATE INDEX IF NOT EXISTS idx_erp_entries_identity
    ON public.erp_entries (entry_id, public.normalize_order_key(order_id), snapshot_id);

CREATE OR REPLACE FUNCTION public.get_erp_entry(p_entry_id UUID)
RETURNS JSONB
LANGUAGE sql STABLE
SET search_path = public
AS $$
    WITH selected AS MATERIALIZED (
        SELECT * FROM public.erp_entries WHERE id = p_entry_id
    ), versions AS MATERIALIZED (
        -- A repeated business identity in one snapshot cannot be matched across downloads.
        SELECT v.id, count(*) OVER (PARTITION BY v.snapshot_id) AS occurrences
        FROM public.erp_entries v
        JOIN selected e ON v.entry_id = e.entry_id
            AND public.normalize_order_key(v.order_id) = public.normalize_order_key(e.order_id)
        WHERE e.entry_id <> '' AND public.normalize_order_key(e.order_id) <> ''
    ), linked_entries AS (
        SELECT id FROM selected
        UNION
        SELECT v.id FROM versions v
        WHERE v.occurrences = 1
          AND EXISTS (
              SELECT 1 FROM versions current_entry
              WHERE current_entry.id = p_entry_id AND current_entry.occurrences = 1
          )
    )
    SELECT (to_jsonb(e) - 'snapshot_id') || jsonb_build_object(
        'amount', e.amount::text,
        'documents', (
            SELECT coalesce(jsonb_agg(
                jsonb_build_object('id', d.id, 'name', d.name) ORDER BY d.name, d.id
            ), '[]'::jsonb)
            FROM public.documents d
            JOIN linked_entries linked ON linked.id = d.erp_entry_id
            WHERE d.deleted_at IS NULL
        )
    )
    FROM selected e;
$$;

REVOKE ALL ON FUNCTION public.get_erp_entry(UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_erp_entry(UUID) TO service_role;
