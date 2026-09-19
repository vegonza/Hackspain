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
