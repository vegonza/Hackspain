CREATE TABLE public.gestoria_settings (
    id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id),
    email TEXT NOT NULL DEFAULT ''
);
ALTER TABLE public.gestoria_settings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.gestoria_settings FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.gestoria_settings TO service_role;
INSERT INTO public.gestoria_settings (id) VALUES (TRUE);

CREATE FUNCTION public.mark_gestoria_sent(p_received_ids UUID[], p_issued_ids UUID[])
RETURNS VOID LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    UPDATE public.documents SET gestoria_sent_at = now()
    WHERE id = ANY(p_received_ids) AND gestoria_sent_at IS NULL;
    UPDATE public.issued_invoices SET gestoria_sent_at = now()
    WHERE id = ANY(p_issued_ids) AND gestoria_sent_at IS NULL;
END;
$$;
REVOKE ALL ON FUNCTION public.mark_gestoria_sent(UUID[], UUID[]) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.mark_gestoria_sent(UUID[], UUID[]) TO service_role;
