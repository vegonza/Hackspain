DROP FUNCTION IF EXISTS public.get_analytics_dashboard();
DROP FUNCTION IF EXISTS public.get_analytics_dashboard(INTEGER);

CREATE OR REPLACE FUNCTION public.get_analytics_dashboard()
RETURNS JSONB
LANGUAGE sql STABLE
SET search_path = public
AS $$
    WITH ready_invoices AS MATERIALIZED (
        SELECT
            duration_ms,
            started_at,
            finished_at,
            exchange_rate,
            line_items,
            supplier_nif,
            vat_amount_eur,
            payment_decision
        FROM public.documents
        WHERE status = 'ready' AND deleted_at IS NULL
    ),
    category_amounts AS (
        SELECT
            item->>'category' AS category,
            SUM(
                CASE
                    WHEN item->>'amount' ~ '^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$'
                    THEN round((item->>'amount')::numeric * invoice.exchange_rate, 2)
                END
            ) AS amount_eur
        FROM ready_invoices AS invoice
        CROSS JOIN LATERAL jsonb_array_elements(invoice.line_items) AS item
        WHERE invoice.exchange_rate IS NOT NULL
        GROUP BY item->>'category'
    ),
    spending AS (
        SELECT
            COALESCE(SUM(amount_eur), 0) AS total_eur,
            COALESCE(
                jsonb_agg(
                    jsonb_build_object('category', category, 'amount_eur', amount_eur::text)
                    ORDER BY amount_eur DESC, category
                ) FILTER (WHERE amount_eur > 0),
                '[]'::jsonb
            ) AS categories
        FROM category_amounts
    ),
    approved_vat AS (
        SELECT
            vat_amount_eur,
            CASE
                WHEN CASE
                    WHEN public.normalize_tax_id(COALESCE(supplier_nif, '')) LIKE 'ES%'
                    THEN substr(public.normalize_tax_id(COALESCE(supplier_nif, '')), 3)
                    ELSE public.normalize_tax_id(COALESCE(supplier_nif, ''))
                END ~ '^([ABCDEFGHJNPQRSUVW][0-9]{7}[0-9A-J]|[0-9]{8}[A-Z]|[XYZ][0-9]{7}[A-Z])$'
                THEN 'deductible'
                ELSE 'foreign'
            END AS vat_kind
        FROM ready_invoices
        WHERE vat_amount_eur > 0
          AND payment_decision->>'classification' = 'PAGAR'
    ),
    vat AS (
        SELECT
            COALESCE(SUM(vat_amount_eur), 0) AS total_eur,
            COALESCE(SUM(vat_amount_eur) FILTER (WHERE vat_kind = 'deductible'), 0) AS deductible_eur,
            COALESCE(SUM(vat_amount_eur) FILTER (WHERE vat_kind = 'foreign'), 0) AS foreign_eur
        FROM approved_vat
    ),
    usage_calls AS MATERIALIZED (
        SELECT
            log.document_id,
            log.operation,
            COALESCE(SUM((entry->>'cost')::numeric), 0) AS cost
        FROM public.usage_log AS log
        LEFT JOIN LATERAL jsonb_array_elements(log.usage) AS entry ON TRUE
        GROUP BY log.id, log.document_id, log.operation
    ),
    usage_totals AS (
        SELECT COUNT(DISTINCT document_id) AS documents, COALESCE(SUM(cost), 0) AS cost
        FROM usage_calls
    ),
    operation_costs AS (
        SELECT operation, SUM(cost) AS cost
        FROM usage_calls
        GROUP BY operation
    ),
    usage_distribution AS (
        SELECT
            COALESCE(totals.cost / NULLIF(totals.documents, 0), 0) AS average_document_cost_usd,
            COALESCE(
                jsonb_agg(
                    jsonb_build_object(
                        'operation', operations.operation,
                        'average_document_cost_usd', (operations.cost / NULLIF(totals.documents, 0))::text
                    )
                    ORDER BY operations.cost DESC, operations.operation
                ) FILTER (WHERE operations.cost > 0 AND totals.documents > 0),
                '[]'::jsonb
            ) AS operations
        FROM usage_totals AS totals
        LEFT JOIN operation_costs AS operations ON TRUE
        GROUP BY totals.documents, totals.cost
    ),
    processing_events AS (
        SELECT started_at AS occurred_at, 1 AS delta
        FROM ready_invoices
        WHERE started_at IS NOT NULL AND finished_at IS NOT NULL
        UNION ALL
        SELECT finished_at AS occurred_at, -1 AS delta
        FROM ready_invoices
        WHERE started_at IS NOT NULL AND finished_at IS NOT NULL
    ),
    processing_concurrency AS (
        SELECT SUM(delta) OVER (
            ORDER BY occurred_at, delta
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS active_workers
        FROM processing_events
    ),
    duration_metrics AS (
        SELECT
            AVG(duration_ms::numeric) FILTER (WHERE duration_ms IS NOT NULL) AS average_duration_ms
        FROM ready_invoices
    ),
    processing AS (
        SELECT
            duration.average_duration_ms,
            duration.average_duration_ms / 1000 / NULLIF(MAX(concurrency.active_workers), 0) AS seconds_per_invoice,
            COALESCE(MAX(concurrency.active_workers), 0)::integer AS workers
        FROM duration_metrics AS duration
        LEFT JOIN processing_concurrency AS concurrency ON TRUE
        GROUP BY duration.average_duration_ms
    )
    SELECT jsonb_build_object(
        'spending', jsonb_build_object(
            'total_eur', spending.total_eur::text,
            'categories', spending.categories
        ),
        'vat', jsonb_build_object(
            'total_eur', vat.total_eur::text,
            'deductible_eur', vat.deductible_eur::text,
            'foreign_eur', vat.foreign_eur::text
        ),
        'usage', jsonb_build_object(
            'average_document_cost_usd', usage_distribution.average_document_cost_usd::text,
            'operations', usage_distribution.operations
        ),
        'processing', jsonb_build_object(
            'average_duration_ms', processing.average_duration_ms::text,
            'seconds_per_invoice', processing.seconds_per_invoice::text,
            'workers', processing.workers
        )
    )
    FROM spending, vat, usage_distribution, processing;
$$;

REVOKE ALL ON FUNCTION public.get_analytics_dashboard() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_analytics_dashboard() TO service_role;
