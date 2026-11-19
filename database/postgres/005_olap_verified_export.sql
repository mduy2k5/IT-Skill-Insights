-- Read-only export surface for the DuckDB loader. Candidate JSON stays private.

BEGIN;

CREATE OR REPLACE VIEW olap_verified_jobs AS
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
    j.last_seen_at
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
VALUES ('005_olap_verified_export')
ON CONFLICT (version) DO NOTHING;

COMMIT;
