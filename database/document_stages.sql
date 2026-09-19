CREATE TABLE IF NOT EXISTS public.document_stages (
    document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    stage TEXT NOT NULL CHECK (stage IN ('ocr', 'text', 'merge')),
    status TEXT NOT NULL DEFAULT 'unavailable'
        CHECK (status IN ('unavailable', 'queued', 'processing', 'ready', 'error')),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    duration_ms BIGINT CHECK (duration_ms >= 0),
    result_path TEXT,
    PRIMARY KEY (document_id, stage),
    CHECK (status <> 'ready' OR result_path IS NOT NULL)
);

ALTER TABLE public.document_stages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.document_stages FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.document_stages TO service_role;

-- Create all stages in the same transaction as their document.
CREATE OR REPLACE FUNCTION public.initialize_document_stages()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    INSERT INTO public.document_stages (document_id, stage, status)
    VALUES (NEW.id, 'ocr', 'queued'), (NEW.id, 'text', 'unavailable'), (NEW.id, 'merge', 'unavailable');
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.initialize_document_stages() FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE TRIGGER initialize_document_stages
    AFTER INSERT ON public.documents
    FOR EACH ROW EXECUTE FUNCTION public.initialize_document_stages();

-- Each usage operation identifies the stage that made the AI call.
CREATE OR REPLACE FUNCTION public.get_document_stage_costs(p_document_id UUID)
RETURNS TABLE (stage TEXT, cost_usd TEXT)
LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT log.operation, SUM((entry->>'cost')::numeric)::text
    FROM public.usage_log log
    CROSS JOIN LATERAL jsonb_array_elements(log.usage) entry
    WHERE log.document_id = p_document_id
    GROUP BY log.operation;
$$;
REVOKE ALL ON FUNCTION public.get_document_stage_costs(UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_document_stage_costs(UUID) TO service_role;
