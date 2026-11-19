import re

import pandas as pd


TITLES_CSV = "/opt/airflow/data/job_titles.csv"


def load_dictionary(conn):
    titles = pd.read_csv(TITLES_CSV).dropna()
    with conn.cursor() as cur:
        for _, row in titles.iterrows():
            cur.execute(
                """
                INSERT INTO dim_job_title (job_title, job_group)
                VALUES (%s, %s)
                ON CONFLICT (job_title) DO UPDATE
                SET job_group = EXCLUDED.job_group
                WHERE dim_job_title.job_group IS DISTINCT FROM EXCLUDED.job_group;
                """,
                (str(row["standard_title"]).strip(), str(row["job_category"]).strip()),
            )
    return len(titles)


def _target_jobs(cur, job_ids):
    if job_ids is None:
        cur.execute(
            """
            SELECT id, job_title, job_title_mapping_id
            FROM jobs_clean
            WHERE job_title_mapping_id IS NULL;
            """
        )
    else:
        cur.execute(
            """
            SELECT id, job_title, job_title_mapping_id
            FROM jobs_clean
            WHERE id = ANY(%s) OR job_title_mapping_id IS NULL;
            """,
            (list(job_ids),),
        )
    return cur.fetchall()


def reconcile_mappings(conn, job_ids=None):
    with conn.cursor() as cur:
        cur.execute("SELECT job_title_id, job_title FROM dim_job_title;")
        titles = cur.fetchall()
        jobs = _target_jobs(cur, job_ids)
        added = 0
        removed = 0
        boundary = chr(92) + "b"

        for job_id, job_title, current_title_id in jobs:
            desired_title_id = None
            title_text = (job_title or "").lower()
            for title_id, keyword in titles:
                pattern = boundary + re.escape(keyword.lower()) + boundary
                if re.search(pattern, title_text):
                    desired_title_id = title_id

            if desired_title_id == current_title_id:
                continue

            cur.execute(
                "UPDATE jobs_clean SET job_title_mapping_id = %s WHERE id = %s;",
                (desired_title_id, job_id),
            )
            if current_title_id is not None:
                removed += 1
            if desired_title_id is not None:
                added += 1

    return {"added": added, "removed": removed}


def main(conn, job_ids=None):
    load_dictionary(conn)
    return reconcile_mappings(conn, job_ids)
