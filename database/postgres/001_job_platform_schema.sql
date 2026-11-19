-- PostgreSQL schema-only bootstrap for the IT Job Platform.
-- Mounted by the dedicated Docker service on first initialization.
-- No sample/source/job rows are inserted here.

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_sources (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    permission_status TEXT NOT NULL DEFAULT 'pending_review'
        CHECK (permission_status IN ('pending_review', 'approved', 'blocked', 'revoked')),
    allow_crawl BOOLEAN NOT NULL DEFAULT FALSE,
    allow_store_metadata BOOLEAN NOT NULL DEFAULT FALSE,
    allow_store_description BOOLEAN NOT NULL DEFAULT FALSE,
    allow_analyze_description BOOLEAN NOT NULL DEFAULT FALSE,
    allow_display_metadata BOOLEAN NOT NULL DEFAULT FALSE,
    allow_display_description BOOLEAN NOT NULL DEFAULT FALSE,
    terms_url TEXT,
    robots_checked_at TIMESTAMPTZ,
    permission_evidence_ref TEXT,
    min_delay_seconds NUMERIC(8, 2) NOT NULL DEFAULT 3.00
        CHECK (min_delay_seconds >= 0),
    max_concurrency SMALLINT NOT NULL DEFAULT 1
        CHECK (max_concurrency = 1),
    adapter_version TEXT,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS companies (
    company_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES job_sources (source_id),
    source_company_key TEXT,
    display_name TEXT NOT NULL,
    logo_url TEXT,
    cover_image_url TEXT,
    source_slug TEXT,
    source_url TEXT,
    tagline TEXT,
    company_size_label TEXT,
    num_job_openings INTEGER CHECK (num_job_openings IS NULL OR num_job_openings >= 0),
    num_employees INTEGER CHECK (num_employees IS NULL OR num_employees >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_id, source_company_key),
    UNIQUE (company_id, source_id)
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES job_sources (source_id),
    source_job_key TEXT NOT NULL,
    company_id UUID,
    title TEXT NOT NULL,
    project_track TEXT NOT NULL,
    source_url TEXT NOT NULL,
    application_url TEXT,
    source_slug TEXT,
    source_status_label TEXT,
    work_mode TEXT NOT NULL DEFAULT 'unknown'
        CHECK (work_mode IN ('onsite', 'remote', 'hybrid', 'unknown')),
    listing_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (listing_status IN ('active', 'expired', 'removed', 'unknown')),
    published_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    refreshed_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_id, source_job_key),
    FOREIGN KEY (company_id, source_id)
        REFERENCES companies (company_id, source_id)
);

CREATE TABLE IF NOT EXISTS job_descriptions (
    job_id UUID PRIMARY KEY REFERENCES jobs (job_id),
    overview_text TEXT,
    responsibilities_text TEXT,
    requirements_text TEXT,
    benefits_text TEXT,
    fetch_status TEXT NOT NULL DEFAULT 'not_requested'
        CHECK (fetch_status IN ('not_requested', 'pending', 'complete', 'empty', 'unavailable', 'not_authorized')),
    content_hash BYTEA CHECK (content_hash IS NULL OR octet_length(content_hash) = 32),
    fetched_at TIMESTAMPTZ,
    source_modified_at TIMESTAMPTZ,
    parser_version TEXT,
    permission_scope TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_compensations (
    job_id UUID PRIMARY KEY REFERENCES jobs (job_id),
    min_amount NUMERIC(14, 2) CHECK (min_amount IS NULL OR min_amount >= 0),
    max_amount NUMERIC(14, 2) CHECK (max_amount IS NULL OR max_amount >= 0),
    currency_code CHAR(3),
    pay_period TEXT,
    display_text TEXT,
    is_negotiable BOOLEAN,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (min_amount IS NULL OR max_amount IS NULL OR max_amount >= min_amount)
);

CREATE TABLE IF NOT EXISTS job_locations (
    job_location_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs (job_id),
    position SMALLINT NOT NULL CHECK (position >= 0),
    country_code CHAR(2),
    province_city TEXT,
    district TEXT,
    ward TEXT,
    address_line TEXT,
    UNIQUE (job_id, position)
);

-- Source labels stay as text. No canonical skill/category/seniority mapping
-- is required for job ingestion or the initial website.
CREATE TABLE IF NOT EXISTS job_source_labels (
    job_source_label_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs (job_id),
    source_field TEXT NOT NULL,
    label_type TEXT NOT NULL,
    label_text TEXT NOT NULL,
    position SMALLINT NOT NULL DEFAULT 0 CHECK (position >= 0),
    UNIQUE (job_id, source_field, position)
);

CREATE TABLE IF NOT EXISTS company_source_labels (
    company_source_label_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies (company_id),
    source_field TEXT NOT NULL,
    label_type TEXT NOT NULL,
    label_text TEXT NOT NULL,
    position SMALLINT NOT NULL DEFAULT 0 CHECK (position >= 0),
    UNIQUE (company_id, source_field, position)
);

CREATE TABLE IF NOT EXISTS crawl_windows (
    window_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES job_sources (source_id),
    requested_from DATE NOT NULL,
    requested_to DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'complete', 'empty', 'paused', 'failed')),
    cursor JSONB,
    items_seen INTEGER NOT NULL DEFAULT 0 CHECK (items_seen >= 0),
    jobs_inserted INTEGER NOT NULL DEFAULT 0 CHECK (jobs_inserted >= 0),
    jobs_updated INTEGER NOT NULL DEFAULT 0 CHECK (jobs_updated >= 0),
    details_fetched INTEGER NOT NULL DEFAULT 0 CHECK (details_fetched >= 0),
    last_error_stage TEXT,
    last_error_code TEXT,
    last_error_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    UNIQUE (source_id, requested_from, requested_to),
    CHECK (requested_to >= requested_from)
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    window_id UUID NOT NULL REFERENCES crawl_windows (window_id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    run_trigger TEXT NOT NULL CHECK (run_trigger IN ('manual', 'schedule', 'retry')),
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'complete', 'empty', 'paused', 'failed')),
    items_seen INTEGER NOT NULL DEFAULT 0 CHECK (items_seen >= 0),
    jobs_inserted INTEGER NOT NULL DEFAULT 0 CHECK (jobs_inserted >= 0),
    jobs_updated INTEGER NOT NULL DEFAULT 0 CHECK (jobs_updated >= 0),
    details_fetched INTEGER NOT NULL DEFAULT 0 CHECK (details_fetched >= 0),
    http_429_count INTEGER NOT NULL DEFAULT 0 CHECK (http_429_count >= 0),
    blocked_count INTEGER NOT NULL DEFAULT 0 CHECK (blocked_count >= 0),
    error_stage TEXT,
    error_code TEXT
);

CREATE INDEX IF NOT EXISTS ix_jobs_listing_status_published_at
    ON jobs (listing_status, published_at DESC);
CREATE INDEX IF NOT EXISTS ix_jobs_project_track_published_at
    ON jobs (project_track, published_at DESC);
CREATE INDEX IF NOT EXISTS ix_job_locations_province_city_district
    ON job_locations (province_city, district);
CREATE INDEX IF NOT EXISTS ix_job_source_labels_job_type
    ON job_source_labels (job_id, label_type);
CREATE INDEX IF NOT EXISTS ix_job_source_labels_type_text
    ON job_source_labels (label_type, label_text);
CREATE INDEX IF NOT EXISTS ix_company_source_labels_company_type
    ON company_source_labels (company_id, label_type);
CREATE INDEX IF NOT EXISTS ix_crawl_windows_source_status
    ON crawl_windows (source_id, status, requested_from, requested_to);
CREATE INDEX IF NOT EXISTS ix_crawl_runs_window_started_at
    ON crawl_runs (window_id, started_at DESC);

COMMIT;
