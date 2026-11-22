#!/usr/bin/env python3
"""Sync normalized role families from OLTP (PostgreSQL) to OLAP (DuckDB).

Flow:
PostgreSQL `jobs` table (single source of truth with role_family, confidence, status)
    -> DuckDB `warehouse.dim_role_family` (new dimension table)
    -> DuckDB `warehouse.dim_job` (role_family, role_family_key, role_confidence, role_decision_status)
    -> DuckDB `warehouse.fact_job_posting` (role_family_key)
"""

import duckdb
import psycopg2

TOKEN = "KRasqQEqf0ztz-XMUfGMp8JsaAkYd5eyNuzgjvQ_kSY"


def main():
    print("[sync] Connecting to PostgreSQL (OLTP)...")
    pg_conn = psycopg2.connect(
        host="127.0.0.1",
        port=5434,
        dbname="it_job_platform",
        user="job_pipeline",
        password="7E9F452ED77284BE21597A40CC7820FD6774B98CF8D28E3A0F3ACCDD628DB53C",
    )

    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT 
                source_job_key,
                role_family,
                role_confidence,
                role_decision_status
            FROM jobs
            WHERE role_family IS NOT NULL;
        """)
        jobs_roles = cur.fetchall()
    pg_conn.close()

    print(f"[sync] Retrieved {len(jobs_roles)} normalized jobs from OLTP.")

    print("[sync] Connecting to DuckDB (OLAP)...")
    duck_conn = duckdb.connect()
    duck_conn.execute(f"ATTACH 'quack:127.0.0.1:9494' AS warehouse_remote (token '{TOKEN}');")
    duck_conn.execute("USE warehouse_remote;")

    # Fetch role_family to key mapping
    role_map = dict(
        duck_conn.execute("SELECT role_family_name, role_family_key FROM warehouse.dim_role_family;").fetchall()
    )

    print("[sync] Updating warehouse.dim_job and warehouse.fact_job_posting in DuckDB...")
    
    # Loop update without FROM clause
    updated_count = 0
    for source_key, fam_name, conf, status in jobs_roles:
        fam_key = role_map.get(fam_name, 99)
        conf_val = float(conf) if conf is not None else 0.0

        escaped_key = source_key.replace("'", "''")
        escaped_fam = fam_name.replace("'", "''")
        escaped_status = status.replace("'", "''")

        dim_sql = f"""
            UPDATE warehouse.dim_job 
            SET role_family_key = {fam_key},
                role_family = '{escaped_fam}',
                role_confidence = {conf_val},
                role_decision_status = '{escaped_status}'
            WHERE source_job_key = '{escaped_key}';
        """
        duck_conn.execute(dim_sql)

        fact_sql = f"""
            UPDATE warehouse.fact_job_posting
            SET role_family_key = {fam_key}
            WHERE job_key IN (SELECT job_key FROM warehouse.dim_job WHERE source_job_key = '{escaped_key}');
        """
        duck_conn.execute(fact_sql)
        updated_count += 1

    print(f"[sync] Successfully updated {updated_count} jobs in DuckDB OLAP.")

    print("\n[sync] Verification in DuckDB OLAP (Direct Query on Dimension):")
    rows = duck_conn.execute("""
        SELECT 
            rf.role_family_name,
            count(j.job_key) as total_jobs,
            round(avg(j.role_confidence), 3) as avg_confidence
        FROM warehouse.dim_job j
        JOIN warehouse.dim_role_family rf ON j.role_family_key = rf.role_family_key
        GROUP BY rf.role_family_name
        ORDER BY total_jobs DESC;
    """).fetchall()

    print(f" {'Role Family (OLAP Dimension)':<45} | {'Job Count':<10} | {'Avg Conf':<10}")
    print("-" * 72)
    for r in rows:
        print(f" {r[0]:<45} | {r[1]:<10} | {r[2]:<10}")

    duck_conn.close()


if __name__ == "__main__":
    main()
