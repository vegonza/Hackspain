CREATE OR REPLACE FUNCTION public.get_invoices(p_offset INTEGER DEFAULT 0, p_limit INTEGER DEFAULT 1000)
RETURNS JSONB LANGUAGE sql STABLE SET search_path = public AS $$
WITH page AS MATERIALIZED (
    SELECT id, name, sha256, created_at, status, pages, payment_decision, started_at, finished_at, duration_ms,
        jsonb_build_object(
            'invoice_number', invoice_number, 'supplier_name', supplier_name,
            'supplier_nif', supplier_nif, 'invoice_date', invoice_date, 'purchase_order', purchase_order,
            'line_items', line_items, 'currency', currency, 'tax_base', tax_base::text, 'total', total::text,
            'tax_base_eur', tax_base_eur::text, 'total_eur', total_eur::text
        ) AS billing
    FROM public.documents WHERE deleted_at IS NULL
    ORDER BY created_at DESC, id LIMIT p_limit OFFSET p_offset
), costs AS (
    SELECT u.document_id, SUM((entry->>'cost')::numeric)::text AS total_cost_usd
    FROM public.usage_log u JOIN page p ON p.id = u.document_id
    CROSS JOIN LATERAL jsonb_array_elements(u.usage) entry
    GROUP BY u.document_id
)
SELECT COALESCE(jsonb_agg(
    to_jsonb(p) - 'started_at' - 'duration_ms' || jsonb_build_object(
        'total_cost_usd', c.total_cost_usd,
        'total_duration_ms', CASE WHEN p.status = 'processing' AND p.finished_at IS NULL AND p.started_at IS NOT NULL
            THEN GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - p.started_at)) * 1000))::bigint
            ELSE p.duration_ms END
    ) ORDER BY p.created_at DESC, p.id
), '[]'::jsonb)
FROM page p LEFT JOIN costs c ON c.document_id = p.id;
$$;
REVOKE ALL ON FUNCTION public.get_invoices(INTEGER, INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_invoices(INTEGER, INTEGER) TO service_role;
