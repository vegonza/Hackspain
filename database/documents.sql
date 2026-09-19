CREATE TABLE IF NOT EXISTS public.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'processing', 'ready', 'error')),
    pages INTEGER NOT NULL DEFAULT 0 CHECK (pages >= 0),
    invoice_number TEXT,
    supplier_name TEXT,
    supplier_nif TEXT,
    iban TEXT,
    invoice_date TEXT,
    purchase_order TEXT,
    line_items JSONB,
    tax_base NUMERIC,
    vat_rate NUMERIC,
    vat_amount NUMERIC,
    total NUMERIC,
    erp_snapshot_id UUID REFERENCES public.erp_snapshots(id),
    erp_entry_id UUID,
    deleted_at TIMESTAMPTZ,
    CONSTRAINT documents_erp_entry_requires_snapshot
        CHECK (erp_entry_id IS NULL OR erp_snapshot_id IS NOT NULL),
    CONSTRAINT documents_erp_entry_snapshot_fk
        FOREIGN KEY (erp_snapshot_id, erp_entry_id)
        REFERENCES public.erp_entries(snapshot_id, id)
);

CREATE INDEX IF NOT EXISTS idx_documents_active_created_at
    ON public.documents (created_at DESC, id) WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_active_sha256
    ON public.documents (sha256) WHERE deleted_at IS NULL;

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.documents FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.documents TO service_role;
