-- Read-only audit for the existing jobs/jobs_clean schema.
-- Run after all application tables have been initialized.
-- Ratios identify candidates for review; missing skills do not always mean failure.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '30s';

-- 1. Raw coverage and detail status, grouped by stored source label.
SELECT source,
       COUNT(*) AS raw_jobs,
       COUNT(*) FILTER (WHERE status_crawl_detail IS NOT TRUE) AS pending_detail,
       COUNT(*) FILTER (
           WHERE status_crawl_detail IS TRUE
             AND NULLIF(BTRIM(COALESCE(responsibilities, '')), '') IS NULL
             AND NULLIF(BTRIM(COALESCE(skills, '')), '') IS NULL
             AND NULLIF(BTRIM(COALESCE(benefits, '')), '') IS NULL
       ) AS detail_success_but_all_empty,
       COUNT(*) FILTER (WHERE NULLIF(BTRIM(COALESCE(link, '')), '') IS NULL) AS invalid_link
FROM jobs
GROUP BY source;

-- 2. Raw -> clean reconciliation by unique URL in the current schema.
SELECT r.source,
       COUNT(*) AS raw_jobs,
       COUNT(c.id) AS linked_clean_jobs,
       COUNT(*) FILTER (WHERE c.id IS NULL) AS missing_clean,
       COUNT(*) FILTER (
           WHERE c.id IS NOT NULL AND r.status_crawl_detail IS TRUE
             AND (BTRIM(COALESCE(r.skills, '')) IS DISTINCT FROM BTRIM(COALESCE(c.skills, ''))
               OR BTRIM(COALESCE(r.responsibilities, '')) IS DISTINCT FROM BTRIM(COALESCE(c.responsibilities, ''))
               OR BTRIM(COALESCE(r.benefits, '')) IS DISTINCT FROM BTRIM(COALESCE(c.benefits, '')))
       ) AS raw_clean_detail_differences
FROM jobs r
LEFT JOIN jobs_clean c ON c.link = r.link
GROUP BY r.source;

-- 3. Clean data quality and mapping coverage.
SELECT COUNT(*) AS clean_jobs,
       COUNT(*) FILTER (WHERE NULLIF(BTRIM(COALESCE(j.job_title, '')), '') IS NULL) AS blank_title,
       COUNT(*) FILTER (WHERE j.job_title_mapping_id IS NULL) AS unmapped_title,
       COUNT(*) FILTER (WHERE j.posted_at_id IS NULL) AS missing_posted_date,
       COUNT(*) FILTER (WHERE j.company_id IS NULL) AS missing_company_fk,
       COUNT(*) FILTER (WHERE j.location_id IS NULL) AS missing_location_fk,
       COUNT(*) FILTER (WHERE NULLIF(BTRIM(COALESCE(j.skills, '')), '') IS NULL) AS empty_skill_text,
       COUNT(*) FILTER (
           WHERE NULLIF(BTRIM(COALESCE(j.skills, '')), '') IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM fact_job_skill_mapping f WHERE f.job_id = j.id)
       ) AS skill_text_without_any_mapping,
       COUNT(*) FILTER (
           WHERE NOT EXISTS (SELECT 1 FROM job_level_mapping f WHERE f.job_id = j.id)
       ) AS no_level_mapping
FROM jobs_clean j;

-- 4. Localities that cannot appear in the province-only dropdown.
SELECT l.id, l.raw_location, l.city, l.province, COUNT(j.id) AS affected_jobs
FROM location_mapping l
JOIN jobs_clean j ON j.location_id = l.id
WHERE NULLIF(BTRIM(COALESCE(l.province, '')), '') IS NULL
  AND NULLIF(BTRIM(COALESCE(l.city, '')), '') IS NOT NULL
GROUP BY l.id, l.raw_location, l.city, l.province
ORDER BY affected_jobs DESC;

-- 5. Samples with missing clean or unsynchronized details.
SELECT r.id AS raw_id, c.id AS clean_id, r.link, r.status_crawl_detail,
       LENGTH(COALESCE(r.skills, '')) AS raw_skill_length,
       LENGTH(COALESCE(c.skills, '')) AS clean_skill_length
FROM jobs r
LEFT JOIN jobs_clean c ON c.link = r.link
WHERE c.id IS NULL
   OR (r.status_crawl_detail IS TRUE
       AND BTRIM(COALESCE(r.skills, '')) IS DISTINCT FROM BTRIM(COALESCE(c.skills, '')))
ORDER BY r.id DESC
LIMIT 20;

-- 6. Correct skills-by-category aggregation for comparison with the API.
SELECT d.job_group, s.skill_keyword, COUNT(DISTINCT j.id) AS job_count
FROM jobs_clean j
JOIN dim_job_title d ON d.job_title_id = j.job_title_mapping_id
JOIN fact_job_skill_mapping f ON f.job_id = j.id
JOIN dim_skill s ON s.skill_id = f.skill_id
GROUP BY d.job_group, s.skill_keyword
ORDER BY d.job_group, job_count DESC, s.skill_keyword;

-- 7. Nonexistent tag IDs held in the legacy TEXT[] column.
SELECT j.id AS job_id, tag_id.value AS invalid_tag_id
FROM jobs_clean j
CROSS JOIN LATERAL UNNEST(j.tags_id) AS tag_id(value)
LEFT JOIN tag_mapping t ON t.id::text = tag_id.value
WHERE t.id IS NULL
LIMIT 50;

-- 8. Duplicate FK definitions, regardless of automatically generated name.
SELECT conrelid::regclass AS relation, conkey, confrelid::regclass AS referenced_relation,
       confkey, COUNT(*) AS equivalent_fk_count, ARRAY_AGG(conname) AS constraint_names
FROM pg_constraint
WHERE contype = 'f' AND connamespace = 'public'::regnamespace
GROUP BY conrelid, conkey, confrelid, confkey,
         confupdtype, confdeltype, confmatchtype, condeferrable, condeferred
HAVING COUNT(*) > 1;

-- 9. Table/index inventory for application schema review.
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('jobs', 'jobs_clean', 'company_mapping', 'location_mapping',
                    'date_mapping', 'job_level_mapping', 'fact_job_skill_mapping',
                    'tag_mapping', 'dim_skill', 'dim_job_title')
ORDER BY tablename, indexname;

-- 10. Actual FK definitions (the live schema can differ from CREATE IF NOT EXISTS).
SELECT conrelid::regclass AS relation, conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE contype = 'f'
  AND conrelid IN ('jobs_clean'::regclass, 'job_level_mapping'::regclass,
                  'fact_job_skill_mapping'::regclass)
ORDER BY conrelid::regclass::text, conname;

COMMIT;
