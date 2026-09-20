CREATE TABLE public.billing_company (
    id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id),
    name TEXT NOT NULL, tax_id TEXT NOT NULL, address TEXT NOT NULL,
    email TEXT NOT NULL, logo_url TEXT NOT NULL,
    iban TEXT NOT NULL, payment_method TEXT NOT NULL
);
CREATE TABLE public.billing_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL, tax_id TEXT NOT NULL UNIQUE, address TEXT NOT NULL,
    email TEXT NOT NULL, logo_url TEXT NOT NULL
);
CREATE TABLE public.issued_invoice_counters (
    year INTEGER PRIMARY KEY,
    last_number INTEGER NOT NULL
);
CREATE TABLE public.issued_invoices (
    id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES public.billing_clients(id),
    status TEXT NOT NULL DEFAULT 'issuing' CHECK (status IN ('issuing', 'issued', 'paid')),
    invoice_number TEXT NOT NULL UNIQUE,
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL CHECK (due_date >= issue_date),
    company JSONB NOT NULL,
    client JSONB NOT NULL,
    items JSONB NOT NULL CHECK (jsonb_typeof(items) = 'array' AND jsonb_array_length(items) > 0),
    notes TEXT NOT NULL,
    base_amount NUMERIC NOT NULL,
    tax_amount NUMERIC NOT NULL,
    total_amount NUMERIC NOT NULL,
    pdf_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    paid_at TIMESTAMPTZ,
    verifactu_test JSONB,
    CHECK (status NOT IN ('issued', 'paid') OR pdf_path IS NOT NULL)
);
CREATE INDEX issued_invoices_date_idx ON public.issued_invoices(issue_date DESC, id);

ALTER TABLE public.billing_company ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.billing_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.issued_invoice_counters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.issued_invoices ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.billing_company, public.billing_clients, public.issued_invoice_counters, public.issued_invoices FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.billing_company, public.billing_clients, public.issued_invoice_counters, public.issued_invoices TO service_role;
GRANT DELETE ON public.billing_clients TO service_role;

CREATE FUNCTION public.reserve_issued_invoice(p_id UUID, p_invoice JSONB)
RETURNS JSONB LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_invoice public.issued_invoices;
    v_company JSONB;
    v_client JSONB;
    v_base NUMERIC;
    v_tax NUMERIC;
    v_year INTEGER;
    v_number INTEGER;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(p_id::text, 0));
    SELECT * INTO v_invoice FROM public.issued_invoices WHERE id = p_id;
    IF FOUND THEN RETURN to_jsonb(v_invoice); END IF;
    SELECT to_jsonb(c) - 'id' INTO v_company FROM public.billing_company c WHERE id;
    IF v_company IS NULL THEN RAISE EXCEPTION 'billing_company_required' USING ERRCODE = 'P0001'; END IF;
    SELECT to_jsonb(c) - 'id' INTO STRICT v_client FROM public.billing_clients c WHERE id = (p_invoice->>'client_id')::uuid;
    SELECT sum(round((x->>'quantity')::numeric * (x->>'unit_price')::numeric, 2)),
        sum(round(round((x->>'quantity')::numeric * (x->>'unit_price')::numeric, 2) * (x->>'tax_rate')::numeric / 100, 2))
    INTO v_base, v_tax FROM jsonb_array_elements(p_invoice->'items') x;
    v_year := extract(year FROM (p_invoice->>'issue_date')::date);
    INSERT INTO public.issued_invoice_counters(year, last_number) VALUES(v_year, 1)
    ON CONFLICT(year) DO UPDATE SET last_number = issued_invoice_counters.last_number + 1
    RETURNING last_number INTO v_number;
    INSERT INTO public.issued_invoices(id, client_id, status, invoice_number, company, client, issue_date, due_date, items, notes, base_amount, tax_amount, total_amount)
    VALUES (p_id, (p_invoice->>'client_id')::uuid, 'issuing',
        'F-' || v_year || '-' || lpad(v_number::text, greatest(4, length(v_number::text)), '0'),
        v_company, v_client, (p_invoice->>'issue_date')::date, (p_invoice->>'due_date')::date,
        p_invoice->'items', p_invoice->>'notes', v_base, v_tax, v_base + v_tax)
    RETURNING * INTO v_invoice;
    RETURN to_jsonb(v_invoice);
END;
$$;
REVOKE ALL ON FUNCTION public.reserve_issued_invoice(UUID, JSONB) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reserve_issued_invoice(UUID, JSONB) TO service_role;

INSERT INTO public.billing_company (id, name, tax_id, address, email, logo_url, iban, payment_method)
VALUES (TRUE, 'Banco Miralmar S.A.', 'A58231077', 'Paseo de la Castellana 214, Madrid', '', '', '', '')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, tax_id = EXCLUDED.tax_id, address = EXCLUDED.address;
