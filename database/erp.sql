CREATE TABLE IF NOT EXISTS public.erp_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fetched_at TIMESTAMPTZ NOT NULL,
    erp_version TEXT NOT NULL,
    update_loaded BOOLEAN NOT NULL,
    entry_count INTEGER NOT NULL CHECK (entry_count > 0)
);

CREATE INDEX IF NOT EXISTS idx_erp_snapshots_fetched_at
    ON public.erp_snapshots (fetched_at DESC, id);

CREATE TABLE IF NOT EXISTS public.erp_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES public.erp_snapshots(id),
    entry_id TEXT NOT NULL,
    supplier_id TEXT NOT NULL,
    tax_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    status TEXT NOT NULL,
    date DATE,
    amount NUMERIC,
    raw_date TEXT NOT NULL,
    raw_amount TEXT NOT NULL,
    warnings TEXT[] NOT NULL DEFAULT '{}',
    UNIQUE (snapshot_id, id)
);

-- ERP identifiers may be duplicated; preserve every row for reconciliation.
CREATE INDEX IF NOT EXISTS idx_erp_entries_snapshot_order
    ON public.erp_entries (snapshot_id, order_id);

ALTER TABLE public.erp_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_entries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_snapshots, public.erp_entries FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.erp_snapshots, public.erp_entries TO service_role;

-- The caller validates the download before publishing it. Both inserts commit together.
CREATE OR REPLACE FUNCTION public.save_erp_snapshot(
    p_fetched_at TIMESTAMPTZ,
    p_erp_version TEXT,
    p_update_loaded BOOLEAN,
    p_entries JSONB
)
RETURNS UUID
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    snapshot_id UUID;
BEGIN
    INSERT INTO public.erp_snapshots (fetched_at, erp_version, update_loaded, entry_count)
    VALUES (p_fetched_at, p_erp_version, p_update_loaded, jsonb_array_length(p_entries))
    RETURNING id INTO snapshot_id;

    INSERT INTO public.erp_entries (
        snapshot_id, entry_id, supplier_id, tax_id, order_id, status,
        date, amount, raw_date, raw_amount, warnings
    )
    SELECT snapshot_id, e.entry_id, e.supplier_id, e.tax_id, e.order_id, e.status,
        e.date, e.amount, e.raw_date, e.raw_amount, e.warnings
    FROM jsonb_to_recordset(p_entries) AS e(
        entry_id TEXT, supplier_id TEXT, tax_id TEXT, order_id TEXT, status TEXT,
        date DATE, amount NUMERIC, raw_date TEXT, raw_amount TEXT, warnings TEXT[]
    );

    RETURN snapshot_id;
END;
$$;

REVOKE ALL ON FUNCTION public.save_erp_snapshot(TIMESTAMPTZ, TEXT, BOOLEAN, JSONB) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.save_erp_snapshot(TIMESTAMPTZ, TEXT, BOOLEAN, JSONB) TO service_role;
