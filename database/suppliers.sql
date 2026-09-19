CREATE TABLE IF NOT EXISTS public.suppliers (
    supplier_id TEXT PRIMARY KEY CHECK (length(btrim(supplier_id)) > 0),
    legal_name TEXT NOT NULL CHECK (length(btrim(legal_name)) > 0),
    tax_id TEXT NOT NULL CHECK (length(btrim(tax_id)) > 0),
    iban TEXT NOT NULL CHECK (length(btrim(iban)) > 0),
    city TEXT NOT NULL CHECK (length(btrim(city)) > 0),
    payment_terms_days INTEGER NOT NULL CHECK (payment_terms_days >= 0)
);

ALTER TABLE public.suppliers ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.suppliers FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.suppliers TO service_role;
