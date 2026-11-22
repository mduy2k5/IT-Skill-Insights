-- 003_add_role_family_to_olap.sql
-- Add normalized role family dimensions to DuckDB OLAP warehouse

ALTER TABLE fact_job_postings 
    ADD COLUMN IF NOT EXISTS role_family VARCHAR;

ALTER TABLE fact_job_postings 
    ADD COLUMN IF NOT EXISTS role_decision_status VARCHAR;

ALTER TABLE fact_job_postings 
    ADD COLUMN IF NOT EXISTS role_confidence DOUBLE;
