CREATE TABLE IF NOT EXISTS discharge_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    document_hash VARCHAR(64) NOT NULL,
    primary_diagnosis VARCHAR(255),
    discharge_date VARCHAR(50),
    pipeline_status VARCHAR(30),
    extracted_fields JSONB,
    fk_scores JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    -- Lock pipeline_status to the three values the orchestrator writes so a
    -- future status rename (e.g. "complete_with_errors") fails loudly in
    -- tests instead of drifting silently. Canonical set is enforced by
    -- db/migrations/20260420_pipeline_status_width_and_check.sql.
    CONSTRAINT chk_pipeline_status CHECK (pipeline_status IN (
        'complete',
        'complete_with_warnings',
        'partial'
    ))
);
