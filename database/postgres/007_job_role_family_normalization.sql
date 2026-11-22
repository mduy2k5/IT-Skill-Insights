-- 007_job_role_family_normalization.sql
-- Add normalized role family columns to jobs table in OLTP (PostgreSQL)
-- Single Source of Truth for job search, filtering, and OLAP analytics ingestion.

BEGIN;

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS role_family VARCHAR(100),
    ADD COLUMN IF NOT EXISTS role_cleaned_title TEXT,
    ADD COLUMN IF NOT EXISTS role_confidence NUMERIC(6, 4),
    ADD COLUMN IF NOT EXISTS role_margin NUMERIC(6, 4),
    ADD COLUMN IF NOT EXISTS role_decision_status VARCHAR(50), -- 'AUTO_ASSIGNED', 'AMBIGUOUS_REVIEW', 'LOW_CONFIDENCE_REVIEW'
    ADD COLUMN IF NOT EXISTS role_candidate_top2 VARCHAR(100),
    ADD COLUMN IF NOT EXISTS role_normalized_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS role_model_version VARCHAR(80);

-- Indexes for lightning-fast search and filtering by role family
CREATE INDEX IF NOT EXISTS idx_jobs_role_family ON jobs(role_family);
CREATE INDEX IF NOT EXISTS idx_jobs_role_decision_status ON jobs(role_decision_status);

-- In PostgreSQL, replacing a view cannot change the order of existing columns.
-- We append new columns at the end, or drop view and recreate.
DROP VIEW IF EXISTS olap_verified_jobs;

CREATE VIEW olap_verified_jobs AS
SELECT
    j.job_id,
    j.source_id,
    s.code AS source_code,
    s.display_name AS source_display_name,
    s.base_url AS source_base_url,
    s.allow_analyze_description,
    j.source_job_key,
    j.company_id,
    j.title,
    j.project_track,
    j.source_url,
    j.work_mode,
    j.listing_status,
    j.published_at,
    j.expires_at,
    j.first_seen_at,
    j.last_seen_at,
    j.role_family,
    j.role_cleaned_title,
    j.role_confidence,
    j.role_margin,
    j.role_decision_status,
    j.role_candidate_top2,
    j.role_normalized_at,
    j.role_model_version
FROM jobs AS j
JOIN job_sources AS s ON s.source_id = j.source_id
WHERE s.permission_status = 'approved'
  AND s.allow_store_metadata = TRUE
  AND EXISTS (
      SELECT 1
      FROM job_ingest_candidates AS c
      WHERE c.job_id = j.job_id
        AND c.source_id = j.source_id
        AND c.source_job_key = j.source_job_key
        AND c.verification_status = 'verified'
        AND c.load_status = 'loaded'
  );

GRANT SELECT ON TABLE olap_verified_jobs TO job_web_reader;

INSERT INTO schema_migrations (version)
VALUES ('007_job_role_family_normalization')
ON CONFLICT (version) DO NOTHING;

COMMIT;
