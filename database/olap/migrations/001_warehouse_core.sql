-- Initial star-schema warehouse for the IT job platform.
-- Location is optional and multi-valued: jobs without a provided location have
-- no bridge_job_location row; remote is represented by work_mode, not a fake city.

BEGIN TRANSACTION;

CREATE SCHEMA IF NOT EXISTS olap_meta;
CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS olap_meta.schema_migrations (
    version VARCHAR PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE IF NOT EXISTS warehouse.surrogate_key_seq START 1;

CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    calendar_year SMALLINT NOT NULL,
    calendar_quarter SMALLINT NOT NULL CHECK (calendar_quarter BETWEEN 1 AND 4),
    calendar_month SMALLINT NOT NULL CHECK (calendar_month BETWEEN 1 AND 12),
    month_start DATE NOT NULL,
    iso_week SMALLINT NOT NULL CHECK (iso_week BETWEEN 1 AND 53),
    day_of_month SMALLINT NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_source (
    source_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    source_id UUID NOT NULL UNIQUE,
    source_code VARCHAR NOT NULL UNIQUE,
    display_name VARCHAR NOT NULL,
    base_url VARCHAR
);

CREATE TABLE IF NOT EXISTS warehouse.dim_company (
    company_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    source_key BIGINT NOT NULL REFERENCES warehouse.dim_source (source_key),
    source_company_key VARCHAR,
    company_name VARCHAR NOT NULL,
    company_size_label VARCHAR,
    UNIQUE (source_key, source_company_key)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_location (
    location_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    location_hash VARCHAR NOT NULL UNIQUE,
    country_code VARCHAR,
    province_city VARCHAR,
    district VARCHAR,
    ward VARCHAR,
    address_line VARCHAR
);

CREATE TABLE IF NOT EXISTS warehouse.dim_job (
    job_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    source_key BIGINT NOT NULL REFERENCES warehouse.dim_source (source_key),
    source_job_key VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    project_track VARCHAR NOT NULL,
    source_url VARCHAR NOT NULL,
    work_mode VARCHAR NOT NULL CHECK (work_mode IN ('onsite', 'remote', 'hybrid', 'unknown')),
    listing_status VARCHAR NOT NULL CHECK (listing_status IN ('active', 'expired', 'removed', 'unknown')),
    description_hash VARCHAR,
    first_seen_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (source_key, source_job_key)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_seniority (
    seniority_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    source_key BIGINT NOT NULL REFERENCES warehouse.dim_source (source_key),
    source_label VARCHAR NOT NULL,
    normalized_level VARCHAR NOT NULL,
    mapping_version VARCHAR NOT NULL,
    is_unknown BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (source_key, source_label, mapping_version)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_skill (
    skill_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    canonical_name VARCHAR NOT NULL,
    category VARCHAR,
    taxonomy_version VARCHAR NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (canonical_name, taxonomy_version)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_skill_alias (
    skill_alias_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    skill_key BIGINT NOT NULL REFERENCES warehouse.dim_skill (skill_key),
    alias_text VARCHAR NOT NULL,
    normalized_alias VARCHAR NOT NULL,
    language_code VARCHAR,
    taxonomy_version VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouse.dim_analyzer_version (
    analyzer_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    analyzer_name VARCHAR NOT NULL,
    analyzer_version VARCHAR NOT NULL,
    taxonomy_version VARCHAR NOT NULL,
    method VARCHAR NOT NULL,
    config_hash VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (analyzer_name, analyzer_version, taxonomy_version)
);

CREATE TABLE IF NOT EXISTS warehouse.bridge_job_location (
    job_key BIGINT NOT NULL REFERENCES warehouse.dim_job (job_key),
    location_key BIGINT NOT NULL REFERENCES warehouse.dim_location (location_key),
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (job_key, position)
);

CREATE TABLE IF NOT EXISTS warehouse.bridge_job_source_label (
    job_key BIGINT NOT NULL REFERENCES warehouse.dim_job (job_key),
    source_field VARCHAR NOT NULL,
    label_type VARCHAR NOT NULL,
    label_text VARCHAR NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (job_key, source_field, position)
);

CREATE TABLE IF NOT EXISTS warehouse.fact_job_posting (
    job_key BIGINT PRIMARY KEY REFERENCES warehouse.dim_job (job_key),
    source_key BIGINT NOT NULL REFERENCES warehouse.dim_source (source_key),
    published_date_key INTEGER REFERENCES warehouse.dim_date (date_key),
    expires_date_key INTEGER REFERENCES warehouse.dim_date (date_key),
    company_key BIGINT REFERENCES warehouse.dim_company (company_key),
    seniority_key BIGINT REFERENCES warehouse.dim_seniority (seniority_key),
    work_mode VARCHAR NOT NULL CHECK (work_mode IN ('onsite', 'remote', 'hybrid', 'unknown')),
    salary_min DECIMAL(14, 2) CHECK (salary_min IS NULL OR salary_min >= 0),
    salary_max DECIMAL(14, 2) CHECK (salary_max IS NULL OR salary_max >= 0),
    salary_currency VARCHAR,
    salary_period VARCHAR,
    job_count SMALLINT NOT NULL DEFAULT 1 CHECK (job_count = 1),
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (salary_min IS NULL OR salary_max IS NULL OR salary_max >= salary_min)
);

CREATE TABLE IF NOT EXISTS warehouse.fact_job_analysis (
    analysis_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    job_key BIGINT NOT NULL REFERENCES warehouse.dim_job (job_key),
    analyzer_key BIGINT NOT NULL REFERENCES warehouse.dim_analyzer_version (analyzer_key),
    analyzed_date_key INTEGER REFERENCES warehouse.dim_date (date_key),
    description_hash VARCHAR NOT NULL,
    analysis_status VARCHAR NOT NULL CHECK (analysis_status IN ('complete', 'skipped', 'failed')),
    skill_count INTEGER NOT NULL DEFAULT 0 CHECK (skill_count >= 0),
    error_code VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (job_key, analyzer_key, description_hash)
);

CREATE TABLE IF NOT EXISTS warehouse.fact_job_skill (
    analysis_key BIGINT NOT NULL REFERENCES warehouse.fact_job_analysis (analysis_key),
    skill_key BIGINT NOT NULL REFERENCES warehouse.dim_skill (skill_key),
    max_confidence DECIMAL(7, 6) CHECK (max_confidence IS NULL OR max_confidence BETWEEN 0 AND 1),
    evidence_count INTEGER NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    job_skill_count SMALLINT NOT NULL DEFAULT 1 CHECK (job_skill_count = 1),
    PRIMARY KEY (analysis_key, skill_key)
);

CREATE TABLE IF NOT EXISTS warehouse.fact_job_skill_evidence (
    evidence_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    analysis_key BIGINT NOT NULL REFERENCES warehouse.fact_job_analysis (analysis_key),
    skill_key BIGINT NOT NULL REFERENCES warehouse.dim_skill (skill_key),
    evidence_position INTEGER NOT NULL CHECK (evidence_position >= 0),
    start_offset INTEGER,
    end_offset INTEGER,
    excerpt VARCHAR,
    confidence DECIMAL(7, 6) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    match_method VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouse.fact_crawl_run (
    crawl_run_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    source_key BIGINT NOT NULL REFERENCES warehouse.dim_source (source_key),
    window_start DATE,
    window_end DATE,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    run_status VARCHAR NOT NULL CHECK (run_status IN ('running', 'complete', 'empty', 'paused', 'failed')),
    pages_seen INTEGER NOT NULL DEFAULT 0 CHECK (pages_seen >= 0),
    jobs_seen INTEGER NOT NULL DEFAULT 0 CHECK (jobs_seen >= 0),
    candidates_staged INTEGER NOT NULL DEFAULT 0 CHECK (candidates_staged >= 0),
    verified_count INTEGER NOT NULL DEFAULT 0 CHECK (verified_count >= 0),
    needs_review_count INTEGER NOT NULL DEFAULT 0 CHECK (needs_review_count >= 0),
    rejected_count INTEGER NOT NULL DEFAULT 0 CHECK (rejected_count >= 0),
    http_429_count INTEGER NOT NULL DEFAULT 0 CHECK (http_429_count >= 0)
);

CREATE TABLE IF NOT EXISTS warehouse.mart_skill_demand_monthly (
    month_key INTEGER NOT NULL,
    source_key BIGINT,
    project_track VARCHAR NOT NULL,
    location_key BIGINT,
    work_mode VARCHAR NOT NULL,
    seniority_key BIGINT,
    skill_key BIGINT NOT NULL,
    total_job_count INTEGER NOT NULL,
    eligible_job_count INTEGER NOT NULL,
    analyzed_job_count INTEGER NOT NULL,
    skill_job_count INTEGER NOT NULL,
    skill_share DECIMAL(9, 6),
    analysis_coverage DECIMAL(9, 6),
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouse.mart_source_coverage_monthly (
    month_key INTEGER NOT NULL,
    source_key BIGINT NOT NULL,
    project_track VARCHAR NOT NULL,
    total_job_count INTEGER NOT NULL,
    jobs_with_location INTEGER NOT NULL,
    jobs_without_location INTEGER NOT NULL,
    remote_without_location INTEGER NOT NULL,
    latest_published_date DATE,
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO olap_meta.schema_migrations (version)
VALUES ('001_warehouse_core')
ON CONFLICT (version) DO NOTHING;

COMMIT;
