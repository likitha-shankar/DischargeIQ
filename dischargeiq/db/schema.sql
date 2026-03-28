CREATE TABLE IF NOT EXISTS discharge_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    document_hash VARCHAR(64) NOT NULL,
    primary_diagnosis VARCHAR(255),
    discharge_date VARCHAR(50),
    pipeline_status VARCHAR(20),
    extracted_fields JSONB,
    fk_scores JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
