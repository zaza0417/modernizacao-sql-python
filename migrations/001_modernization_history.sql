CREATE TABLE modernization_history(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_code TEXT NOT NULL,
    generated_code text,
    report JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL
           CHECK ( status IN ('sucesso', 'falha', 'parcial') ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_history_created_at ON modernization_history (created_at DESC);