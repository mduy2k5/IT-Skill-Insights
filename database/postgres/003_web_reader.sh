#!/bin/sh
set -eu

: "${JOB_WEB_DB_USER:?JOB_WEB_DB_USER must be set}"
: "${JOB_WEB_DB_PASSWORD:?JOB_WEB_DB_PASSWORD must be set}"

psql -X --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 <<'SQL'
\getenv web_user JOB_WEB_DB_USER
\getenv web_password JOB_WEB_DB_PASSWORD
\getenv writer_user POSTGRES_USER

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'web_user', :'web_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'web_user')
\gexec

SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'web_user', :'web_password')
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'web_user')
\gexec
GRANT USAGE ON SCHEMA public TO :"web_user";
GRANT SELECT ON TABLE job_sources, jobs, companies, job_descriptions,
    job_locations, job_compensations, job_source_labels
    TO :"web_user";

SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT ON TABLES TO %I',
    :'writer_user', :'web_user'
)
\gexec
SQL
