-- Staging and verification records for individual jobs extracted from artifacts.
-- Candidates remain here until verified and explicitly loaded into website OLTP.

BEGIN;

CREATE TABLE IF NOT EXISTS job_ingest_candidates (
    candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES crawl_artifacts (artifact_id),
    source_id UUID NOT NULL REFERENCES job_sources (source_id),
    record_index INTEGER NOT NULL CHECK (record_index >= 1),
    source_job_key TEXT,
    project_track TEXT NOT NULL,
    candidate_json JSONB NOT NULL,
    verification_status TEXT NOT NULL
        CHECK (verification_status IN ('verified', 'needs_review', 'rejected')),
    validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(validation_errors) = 'array'),
    validation_warnings JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(validation_warnings) = 'array'),
    validator_version TEXT NOT NULL,
    load_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (load_status IN ('pending', 'loaded')),
    job_id UUID REFERENCES jobs (job_id),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    loaded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (artifact_id, record_index),
    CHECK ((load_status = 'loaded' AND job_id IS NOT NULL AND loaded_at IS NOT NULL)
        OR (load_status = 'pending' AND loaded_at IS NULL))
);

CREATE INDEX IF NOT EXISTS ix_job_ingest_candidates_status
    ON job_ingest_candidates (verification_status, load_status, created_at);
CREATE INDEX IF NOT EXISTS ix_job_ingest_candidates_source_key
    ON job_ingest_candidates (source_id, source_job_key);

-- This is an ingestion/review table; never expose candidate JSON to the website role.
REVOKE SELECT ON TABLE job_ingest_candidates FROM job_web_reader;

INSERT INTO schema_migrations (version)
VALUES ('004_job_ingest_candidates')
ON CONFLICT (version) DO NOTHING;

COMMIT;
