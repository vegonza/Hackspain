CREATE TABLE IF NOT EXISTS public.usage_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (BTRIM(operation) <> ''),
    document_id UUID NOT NULL,
    document_name TEXT NOT NULL,
    usage JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(usage) = 'array')
);

COMMENT ON COLUMN public.usage_log.usage IS
    'Array of {model, provider, cost, details}. Cost is expressed in USD.';

-- Usage history survives document deletion.
CREATE INDEX IF NOT EXISTS idx_usage_log_document
    ON public.usage_log (document_id);

CREATE INDEX IF NOT EXISTS idx_usage_log_created_at
    ON public.usage_log (created_at DESC, id DESC);

ALTER TABLE public.usage_log ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.usage_log FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.usage_log TO service_role;

CREATE OR REPLACE FUNCTION public.get_usage_dashboard(p_page INTEGER DEFAULT 0)
RETURNS JSONB
LANGUAGE sql STABLE
SET search_path = public
AS $$
    WITH call_totals AS MATERIALIZED (
        SELECT
            (log.created_at AT TIME ZONE 'UTC')::date AS day,
            log.operation,
            amounts.cost,
            amounts.pages
        FROM public.usage_log AS log
        CROSS JOIN LATERAL (
            SELECT
                COALESCE(SUM((entry->>'cost')::numeric), 0) AS cost,
                COALESCE(SUM((entry->'details'->>'pages_processed')::bigint), 0) AS pages
            FROM jsonb_array_elements(log.usage) AS entry
        ) AS amounts
    ),
    totals AS (
        SELECT COUNT(*) AS calls,
            COALESCE(SUM(cost), 0) AS cost,
            COALESCE(SUM(pages), 0) AS pages,
            GREATEST(1, (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - MIN(day) + 1) AS days
        FROM call_totals
    ),
    operation_totals AS (
        SELECT day, operation, COUNT(*) AS calls, SUM(cost) AS cost
        FROM call_totals
        GROUP BY day, operation
    ),
    daily_rows AS (
        SELECT day AS date, SUM(calls) AS calls,
            SUM(cost)::text AS cost_usd,
            jsonb_object_agg(operation, cost::text) AS operations
        FROM operation_totals
        GROUP BY day
        ORDER BY day DESC
        LIMIT 14
    ),
    log_rows AS (
        SELECT * FROM public.usage_log
        ORDER BY created_at DESC, id DESC
        LIMIT 25 OFFSET (p_page::bigint * 25)
    )
    SELECT jsonb_build_object(
        'records', COALESCE(
            (SELECT jsonb_agg(to_jsonb(log_rows) ORDER BY created_at DESC, id DESC) FROM log_rows),
            '[]'::jsonb
        ),
        'total', totals.calls,
        'page_size', 25,
        'summary', jsonb_build_object(
            'calls', totals.calls,
            'pages', totals.pages,
            'cost_usd', totals.cost::text,
            'average_daily_cost_usd', (totals.cost / totals.days)::text
        ),
        'daily', COALESCE(
            (SELECT jsonb_agg(to_jsonb(daily_rows) ORDER BY date) FROM daily_rows),
            '[]'::jsonb
        )
    ) FROM totals;
$$;

REVOKE ALL ON FUNCTION public.get_usage_dashboard(INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_usage_dashboard(INTEGER) TO service_role;
