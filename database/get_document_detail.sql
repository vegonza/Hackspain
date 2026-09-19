CREATE OR REPLACE FUNCTION public.get_document_detail(p_document_id UUID)
RETURNS JSONB
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT to_jsonb(d) - 'deleted_at' || jsonb_build_object(
        'stages', (
            SELECT COALESCE(jsonb_agg(
                to_jsonb(s) || jsonb_build_object('cost_usd', costs.cost_usd)
                ORDER BY CASE s.stage WHEN 'ocr' THEN 0 WHEN 'text' THEN 1 ELSE 2 END
            ), '[]'::jsonb)
            FROM public.document_stages s
            LEFT JOIN (
                SELECT log.operation, SUM((entry->>'cost')::numeric)::text AS cost_usd
                FROM public.usage_log log
                CROSS JOIN LATERAL jsonb_array_elements(log.usage) entry
                WHERE log.document_id = p_document_id
                GROUP BY log.operation
            ) costs ON costs.operation = s.stage
            WHERE s.document_id = d.id
        )
    )
    FROM public.documents d
    WHERE d.id = p_document_id AND d.deleted_at IS NULL;
$$;

REVOKE ALL ON FUNCTION public.get_document_detail(UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_document_detail(UUID) TO service_role;
