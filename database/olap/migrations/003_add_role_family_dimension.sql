-- 003_add_role_family_dimension.sql
-- Add dim_role_family and link to dim_job and fact_job_posting

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS warehouse.dim_role_family (
    role_family_key BIGINT PRIMARY KEY,
    role_family_name VARCHAR NOT NULL UNIQUE,
    category_group VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Pre-populate with standard role families using explicit integer keys
INSERT INTO warehouse.dim_role_family (role_family_key, role_family_name, category_group)
VALUES
    (1, 'Software Engineering (Backend)', 'Engineering'),
    (2, 'Software Engineering (Fullstack / Web)', 'Engineering'),
    (3, 'Software Engineering (Frontend)', 'Engineering'),
    (4, 'Software Engineering (Mobile)', 'Engineering'),
    (5, 'Software Engineering (AI / ML)', 'Data & AI'),
    (6, 'Data Engineering', 'Data & AI'),
    (7, 'Data Analysis & Business Intelligence', 'Data & AI'),
    (8, 'Database Administration', 'Data & AI'),
    (9, 'DevOps & DevSecOps', 'Cloud & Infrastructure'),
    (10, 'Cloud, Systems & Network Infrastructure', 'Cloud & Infrastructure'),
    (11, 'Information Security / Cybersecurity', 'Security'),
    (12, 'Software Testing / QA / QC', 'Quality Assurance'),
    (13, 'Business Analysis', 'Product & Analysis'),
    (14, 'IT Project Management / Product Management', 'Management'),
    (15, 'IT Architecture & Strategy', 'Strategy & Architecture'),
    (16, 'Enterprise Applications (ERP / CRM)', 'Enterprise Solutions'),
    (17, 'IT Support & Systems Operations', 'Operations & Support'),
    (18, 'IT Operations & Integration Services', 'Operations & Support'),
    (19, 'IT Sales & Presales', 'Business & Sales'),
    (99, 'Needs Review', 'Uncategorized')
ON CONFLICT (role_family_name) DO NOTHING;

-- Add role family attributes to dim_job
ALTER TABLE warehouse.dim_job ADD COLUMN IF NOT EXISTS role_family_key BIGINT;
ALTER TABLE warehouse.dim_job ADD COLUMN IF NOT EXISTS role_family VARCHAR;
ALTER TABLE warehouse.dim_job ADD COLUMN IF NOT EXISTS role_confidence DOUBLE;
ALTER TABLE warehouse.dim_job ADD COLUMN IF NOT EXISTS role_decision_status VARCHAR;

-- Add role_family_key to fact_job_posting for dimensional slicing
ALTER TABLE warehouse.fact_job_posting ADD COLUMN IF NOT EXISTS role_family_key BIGINT;

-- Record migration
INSERT INTO olap_meta.schema_migrations (version)
VALUES ('003_add_role_family_dimension')
ON CONFLICT (version) DO NOTHING;

COMMIT;
