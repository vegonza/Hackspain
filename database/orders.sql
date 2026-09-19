CREATE TABLE IF NOT EXISTS public.orders (
    order_id TEXT PRIMARY KEY CHECK (length(btrim(order_id)) > 0),
    supplier_id TEXT NOT NULL REFERENCES public.suppliers (supplier_id),
    tax_id TEXT,
    amount NUMERIC(18, 2) NOT NULL,
    status TEXT NOT NULL CHECK (length(btrim(status)) > 0),
    date DATE NOT NULL,
    review_required BOOLEAN NOT NULL DEFAULT FALSE,
    claimed_by_document_id UUID REFERENCES public.documents(id),
    claim_conflicted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS orders_supplier_id_idx ON public.orders (supplier_id);

ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.orders FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.orders TO service_role;
