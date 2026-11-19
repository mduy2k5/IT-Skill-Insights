BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(100) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS company_mapping (
    id SERIAL PRIMARY KEY,
    raw_name TEXT,
    clean_name TEXT,
    location_id TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_company_clean ON company_mapping (clean_name);
INSERT INTO company_mapping (raw_name, clean_name)
VALUES ('', '')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS location_mapping (
    id SERIAL PRIMARY KEY,
    raw_location TEXT,
    clean_location TEXT,
    city TEXT,
    province TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_location_clean ON location_mapping (clean_location);
INSERT INTO location_mapping (raw_location, clean_location)
VALUES ('', '')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS level_mapping (
    id SERIAL PRIMARY KEY,
    raw_level TEXT,
    clean_level TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_level_clean ON level_mapping (clean_level);
INSERT INTO level_mapping (raw_level, clean_level)
VALUES ('', '')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS job_level_mapping (
    job_id INTEGER,
    level_id INTEGER,
    PRIMARY KEY (job_id, level_id)
);

CREATE TABLE IF NOT EXISTS tag_mapping (
    id SERIAL PRIMARY KEY,
    raw_tag TEXT,
    clean_tag TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tag_clean ON tag_mapping (clean_tag);
INSERT INTO tag_mapping (raw_tag, clean_tag)
VALUES ('', '')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS date_mapping (
    id SERIAL PRIMARY KEY,
    raw_date TEXT,
    clean_date DATE,
    day INT,
    month INT,
    year INT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_date_clean ON date_mapping (clean_date);

CREATE TABLE IF NOT EXISTS job_type_mapping (
    id SERIAL PRIMARY KEY,
    raw_job_type TEXT,
    clean_job_type TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_type_clean ON job_type_mapping (clean_job_type);
INSERT INTO job_type_mapping (raw_job_type, clean_job_type)
VALUES ('', '')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS jobs_clean (
    id SERIAL PRIMARY KEY,
    job_title TEXT,
    company_id INTEGER,
    salary TEXT,
    location_id INTEGER,
    job_type_id INTEGER,
    experience TEXT,
    tags_id TEXT[],
    posted_at_id INTEGER,
    link TEXT UNIQUE,
    logo_link TEXT,
    responsibilities TEXT,
    skills TEXT,
    benefits TEXT,
    source TEXT DEFAULT 'job_crawler',
    job_title_mapping_id INTEGER
);

CREATE TABLE IF NOT EXISTS dim_skill (
    skill_id SERIAL PRIMARY KEY,
    skill_keyword VARCHAR(100) UNIQUE NOT NULL,
    skill_group VARCHAR(100) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_keyword ON dim_skill (skill_keyword);

CREATE TABLE IF NOT EXISTS fact_job_skill_mapping (
    job_id INT REFERENCES jobs_clean(id) ON DELETE CASCADE,
    skill_id INT REFERENCES dim_skill(skill_id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, skill_id)
);

CREATE TABLE IF NOT EXISTS dim_job_title (
    job_title_id SERIAL PRIMARY KEY,
    job_title VARCHAR(255) UNIQUE NOT NULL,
    job_group VARCHAR(100) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_title ON dim_job_title (job_title);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'jobs_clean'::regclass
          AND confrelid = 'dim_job_title'::regclass
          AND contype = 'f'
    ) THEN
        ALTER TABLE jobs_clean
            ADD CONSTRAINT fk_job_title_mapping
            FOREIGN KEY (job_title_mapping_id) REFERENCES dim_job_title(job_title_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'jobs_clean'::regclass
          AND confrelid = 'company_mapping'::regclass
          AND contype = 'f'
    ) THEN
        ALTER TABLE jobs_clean
            ADD CONSTRAINT fk_company
            FOREIGN KEY (company_id) REFERENCES company_mapping(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'jobs_clean'::regclass
          AND confrelid = 'location_mapping'::regclass
          AND contype = 'f'
    ) THEN
        ALTER TABLE jobs_clean
            ADD CONSTRAINT fk_location
            FOREIGN KEY (location_id) REFERENCES location_mapping(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'jobs_clean'::regclass
          AND confrelid = 'job_type_mapping'::regclass
          AND contype = 'f'
    ) THEN
        ALTER TABLE jobs_clean
            ADD CONSTRAINT fk_job_type
            FOREIGN KEY (job_type_id) REFERENCES job_type_mapping(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'jobs_clean'::regclass
          AND confrelid = 'date_mapping'::regclass
          AND contype = 'f'
    ) THEN
        ALTER TABLE jobs_clean
            ADD CONSTRAINT fk_posted_at
            FOREIGN KEY (posted_at_id) REFERENCES date_mapping(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'job_level_mapping'::regclass
          AND confrelid = 'jobs_clean'::regclass
          AND contype = 'f'
    ) THEN
        ALTER TABLE job_level_mapping
            ADD CONSTRAINT fk_job
            FOREIGN KEY (job_id) REFERENCES jobs_clean(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'job_level_mapping'::regclass
          AND confrelid = 'level_mapping'::regclass
          AND contype = 'f'
    ) THEN
        ALTER TABLE job_level_mapping
            ADD CONSTRAINT fk_level
            FOREIGN KEY (level_id) REFERENCES level_mapping(id);
    END IF;
END $$;

INSERT INTO schema_migrations (version)
VALUES ('001_transform_schema')
ON CONFLICT (version) DO NOTHING;

COMMIT;
