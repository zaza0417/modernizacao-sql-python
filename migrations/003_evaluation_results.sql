CREATE TABLE evaluation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,
    execution_id UUID NOT NULL REFERENCES modernization_history (id),
    routine TEXT NOT NULL,
    scenario TEXT NOT NULL,
    equivalent BOOLEAN NOT NULL,
    outcome_match BOOLEAN NOT NULL,
    state_match BOOLEAN NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evaluation_run ON evaluation_results (run_id);
