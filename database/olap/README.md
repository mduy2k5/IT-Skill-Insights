# Local OLAP warehouse

The development warehouse runs in the `job-olap` Docker Compose service using DuckDB. Its database file lives in the named volume `it_job_olap_data`; removing/recreating the container does not delete the volume.

The image is pinned to DuckDB `2.0.0`. Keep that major version for this database file: DuckDB versions before 2.0 cannot read files created in the 2.0 storage format. Back up the volume before upgrades.

## Apply warehouse migrations

Run migrations before starting the server. Stop the server before applying later migrations so only one process opens the DuckDB file:

```powershell
docker compose --profile olap-tools run --rm --no-deps job-olap-migrate
docker compose --profile olap-tools run --rm --no-deps job-olap-migrate /var/lib/duckdb/it_job_analytics.duckdb -f /opt/olap/migrations/002_remove_dim_skill_category.sql
docker compose up -d job-olap
```

The first command applies the initial schema. The second applies the follow-up migration that removes the unused `category` column from `dim_skill`. Each migration records its version in `olap_meta.schema_migrations`. Stop the DuckDB server before applying later migrations, and do not run DDL from each ETL batch.

## Load verified OLTP jobs

Apply the PostgreSQL export-view migration once. It exposes only currently approved metadata jobs that have a verified, loaded candidate; the raw candidate JSON remains inaccessible to the website/loader role.

```powershell
Get-Content -Raw .\database\postgres\005_olap_verified_export.sql | docker compose exec -T job-postgres sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
```

The one-shot loader uses the `job_web_reader` account for PostgreSQL reads and Quack for DuckDB writes. It preserves raw label/location text, upserts distinct job skill labels into `warehouse.dim_skill` with taxonomy version `source-label-v1`, and upserts each `job_levels_arr` label into `warehouse.dim_seniority` with `mapping_version='source-label-v1'` and `normalized_level=source_label`. This is an identity mapping that retains source labels until a human-reviewed normalization is defined. `fact_job_posting.seniority_key` is set when a job has exactly one distinct level; multi-level jobs keep a NULL fact key and retain all labels in `bridge_job_source_label`. The loader never copies full descriptions, loads a remote job with no location as zero bridge rows, and rebuilds source-coverage mart rows for the selected source/track. Skill names retain their source spelling (with surrounding/repeated whitespace collapsed); `dim_skill` has no category column, and no alias mapping or job-to-canonical-skill fact is created yet.

```powershell
docker compose --profile olap-tools run --build --rm job-olap-loader --source-code saramin --project-track data --dry-run
docker compose --profile olap-tools run --build --rm job-olap-loader --source-code saramin --project-track data --apply
```

The loader is idempotent on source/job, company, location, seniority, label, and raw skill-name keys. It reports the number of distinct raw skill names and seniority labels upserted for the selected source/track. `fact_job_skill`, other description-analysis facts, and crawl-run facts remain empty until their respective workflows are implemented. The Analyst overview reads job, source-level, and raw skill-tag aggregates directly from Quack/OLAP (`dim_job`, `dim_seniority`, `dim_skill`, and `bridge_job_source_label`).

## Connect locally

The Quack endpoint is published only on host loopback at `localhost:9494`. Connect with a DuckDB 2.0 CLI and the token in the ignored `.env` file:

```sql
ATTACH 'quack:localhost' AS warehouse_remote (TOKEN 'value-from-JOB_OLAP_TOKEN');
CONNECT warehouse_remote;
SHOW TABLES FROM warehouse;
```

The server token grants the holder the SQL permissions of the DuckDB server. Keep the port bound to `127.0.0.1`; do not publish it to a public interface.

## Data model notes

- `fact_job_posting` has one row per job and no location key.
- `bridge_job_location` has zero or more rows per job. A remote job with no source location has no bridge rows; `work_mode='remote'` remains on the job/fact.
- Count distinct jobs when grouping through `bridge_job_location`, because one job can list multiple locations.
- The initial schema is empty. ETL from verified OLTP records is a separate step.
