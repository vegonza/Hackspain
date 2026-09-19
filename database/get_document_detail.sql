CREATE OR REPLACE FUNCTION public.get_document_detail(p_document_id UUID)
RETURNS JSONB LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT to_jsonb(d) - 'deleted_at' - 'started_at' - 'duration_ms' || jsonb_build_object(
        'erp', CASE WHEN e.id IS NOT NULL
            THEN to_jsonb(e) || jsonb_build_object('amount', e.amount::text)
            ELSE NULL END,
        'total_duration_ms', CASE WHEN d.status = 'processing' AND d.finished_at IS NULL AND d.started_at IS NOT NULL
            THEN GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - d.started_at)) * 1000))::bigint
            ELSE d.duration_ms END,
        'total_cost_usd', (
            SELECT SUM((entry->>'cost')::numeric)::text
            FROM public.usage_log log
            CROSS JOIN LATERAL jsonb_array_elements(log.usage) entry
            WHERE log.document_id = d.id
        )
    )
    FROM public.documents d
    LEFT JOIN public.erp_entries e ON e.snapshot_id = d.erp_snapshot_id AND e.id = d.erp_entry_id
    WHERE d.id = p_document_id AND d.deleted_at IS NULL;
$$;
REVOKE ALL ON FUNCTION public.get_document_detail(UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_document_detail(UUID) TO service_role;
