-- Raw crawl artifact storage. JSON/JSONL keeps both the original UTF-8 text
-- and a parsed JSONB value; HTML is stored as original text only.

BEGIN;

CREATE TABLE IF NOT EXISTS crawl_artifacts (
    artifact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES job_sources (source_id),
    crawl_run_id UUID REFERENCES crawl_runs (run_id),
    artifact_kind TEXT NOT NULL,
    file_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    artifact_date DATE,
    content_type TEXT NOT NULL
        CHECK (content_type IN ('text/html', 'application/json', 'application/x-ndjson')),
    content_sha256 CHAR(64) NOT NULL
        CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    content_text TEXT NOT NULL,
    content_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_id, file_name, content_sha256),
    CHECK (
        (content_type = 'text/html' AND content_json IS NULL)
        OR
        (content_type IN ('application/json', 'application/x-ndjson') AND content_json IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_crawl_artifacts_source_date
    ON crawl_artifacts (source_id, artifact_date DESC);
CREATE INDEX IF NOT EXISTS ix_crawl_artifacts_kind_date
    ON crawl_artifacts (artifact_kind, artifact_date DESC);

INSERT INTO schema_migrations (version)
VALUES ('002_crawl_artifacts')
ON CONFLICT (version) DO NOTHING;

COMMIT;
