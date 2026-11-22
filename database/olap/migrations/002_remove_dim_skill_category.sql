-- DuckDB cannot drop this column in place because an index uses a later column.
-- Rebuild dim_skill and its foreign-key children while preserving all rows.
BEGIN TRANSACTION;

CREATE TEMP TABLE _migration_dim_skill AS
SELECT skill_key, canonical_name, taxonomy_version, is_active
FROM warehouse.dim_skill;

CREATE TEMP TABLE _migration_dim_skill_alias AS
SELECT skill_alias_key, skill_key, alias_text, normalized_alias,
       language_code, taxonomy_version
FROM warehouse.dim_skill_alias;

CREATE TEMP TABLE _migration_fact_job_skill AS
SELECT analysis_key, skill_key, max_confidence, evidence_count, job_skill_count
FROM warehouse.fact_job_skill;

CREATE TEMP TABLE _migration_fact_job_skill_evidence AS
SELECT evidence_key, analysis_key, skill_key, evidence_position,
       start_offset, end_offset, excerpt, confidence, match_method
FROM warehouse.fact_job_skill_evidence;

DROP TABLE warehouse.fact_job_skill_evidence;
DROP TABLE warehouse.fact_job_skill;
DROP TABLE warehouse.dim_skill_alias;
DROP TABLE warehouse.dim_skill;

CREATE TABLE warehouse.dim_skill (
    skill_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    canonical_name VARCHAR NOT NULL,
    taxonomy_version VARCHAR NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (canonical_name, taxonomy_version)
);

INSERT INTO warehouse.dim_skill
    (skill_key, canonical_name, taxonomy_version, is_active)
SELECT skill_key, canonical_name, taxonomy_version, is_active
FROM _migration_dim_skill;

CREATE TABLE warehouse.dim_skill_alias (
    skill_alias_key BIGINT PRIMARY KEY DEFAULT nextval('warehouse.surrogate_key_seq'),
    skill_key BIGINT NOT NULL REFERENCES warehouse.dim_skill (skill_key),
    alias_text VARCHAR NOT NULL,
    normalized_alias VARCHAR NOT NULL,
    language_code VARCHAR,
    taxonomy_version VARCHAR NOT NULL
);

INSERT INTO warehouse.dim_skill_alias
    (skill_alias_key, skill_key, alias_text, normalized_alias, language_code, taxonomy_version)
SELECT skill_alias_key, skill_key, alias_text, normalized_alias, language_code, taxonomy_version
FROM _migration_dim_skill_alias;

CREATE TABLE warehouse.fact_job_skill (
    analysis_key BIGINT NOT NULL REFERENCES warehouse.fact_job_analysis (analysis_key),
    skill_key BIGINT NOT NULL REFERENCES warehouse.dim_skill (skill_key),
    max_confidence DECIMAL(7, 6)
        CHECK (max_confidence IS NULL OR max_confidence BETWEEN 0 AND 1),
    evidence_count INTEGER NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    job_skill_count SMALLINT NOT NULL DEFAULT 1 CHECK (job_skill_count = 1),
    PRIMARY KEY (analysis_key, skill_key)
);

INSERT INTO warehouse.fact_job_skill
    (analysis_key, skill_key, max_confidence, evidence_count, job_skill_count)
SELECT analysis_key, skill_key, max_confidence, evidence_count, job_skill_count
FROM _migration_fact_job_skill;

CREATE TABLE warehouse.fact_job_skill_evidence (
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

INSERT INTO warehouse.fact_job_skill_evidence
    (evidence_key, analysis_key, skill_key, evidence_position, start_offset,
     end_offset, excerpt, confidence, match_method)
SELECT evidence_key, analysis_key, skill_key, evidence_position, start_offset,
       end_offset, excerpt, confidence, match_method
FROM _migration_fact_job_skill_evidence;

INSERT INTO olap_meta.schema_migrations (version)
VALUES ('002_remove_dim_skill_category')
ON CONFLICT (version) DO NOTHING;

COMMIT;
