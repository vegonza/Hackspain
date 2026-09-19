CREATE OR REPLACE FUNCTION public.get_documents(p_offset INTEGER DEFAULT 0, p_limit INTEGER DEFAULT 1000)
RETURNS JSONB LANGUAGE sql STABLE SET search_path = public AS $$
WITH page AS MATERIALIZED (
    SELECT * FROM public.documents WHERE deleted_at IS NULL
    ORDER BY created_at DESC, id LIMIT p_limit OFFSET p_offset
), costs AS (
    SELECT u.document_id, u.operation, SUM((entry->>'cost')::numeric) AS cost
    FROM public.usage_log u JOIN page p ON p.id = u.document_id
    CROSS JOIN LATERAL jsonb_array_elements(u.usage) entry
    GROUP BY u.document_id, u.operation
), metrics AS (
    SELECT s.document_id, s.stage, s.status, c.cost,
        CASE WHEN s.status = 'processing' AND s.started_at IS NOT NULL
            THEN GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - s.started_at)) * 1000))::bigint
            ELSE s.duration_ms END AS duration_ms
    FROM public.document_stages s JOIN page p ON p.id = s.document_id
    LEFT JOIN costs c ON c.document_id = s.document_id AND c.operation = s.stage
), summaries AS (
    SELECT document_id,
        SUM(cost)::text AS total_cost_usd, SUM(duration_ms)::bigint AS total_duration_ms,
        jsonb_agg(jsonb_build_object('stage', stage, 'cost_usd', cost::text, 'duration_ms', duration_ms)
            ORDER BY CASE stage WHEN 'ocr' THEN 0 WHEN 'text' THEN 1 ELSE 2 END) AS stage_metrics,
        COALESCE(jsonb_agg(stage ORDER BY CASE stage WHEN 'ocr' THEN 0 WHEN 'text' THEN 1 ELSE 2 END)
            FILTER (WHERE status IN ('processing', 'queued', 'error')), '[]'::jsonb) AS current_stages
    FROM metrics GROUP BY document_id
)
SELECT COALESCE(jsonb_agg(to_jsonb(p) - 'deleted_at' || jsonb_build_object(
    'total_cost_usd', s.total_cost_usd, 'total_duration_ms', s.total_duration_ms,
    'stage_metrics', COALESCE(s.stage_metrics, '[]'::jsonb),
    'current_stages', COALESCE(s.current_stages, '[]'::jsonb)
) ORDER BY p.created_at DESC, p.id), '[]'::jsonb)
FROM page p LEFT JOIN summaries s ON s.document_id = p.id;
$$;
REVOKE ALL ON FUNCTION public.get_documents(INTEGER, INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_documents(INTEGER, INTEGER) TO service_role;
