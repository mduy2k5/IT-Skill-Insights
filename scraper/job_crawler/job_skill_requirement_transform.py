import re

import pandas as pd


SKILLS_CSV = "/opt/airflow/data/job_skills.csv"


def load_dictionary(conn):
    skills = pd.read_csv(SKILLS_CSV).dropna()
    with conn.cursor() as cur:
        for _, row in skills.iterrows():
            cur.execute(
                """
                INSERT INTO dim_skill (skill_keyword, skill_group)
                VALUES (%s, %s)
                ON CONFLICT (skill_keyword) DO UPDATE
                SET skill_group = EXCLUDED.skill_group
                WHERE dim_skill.skill_group IS DISTINCT FROM EXCLUDED.skill_group;
                """,
                (str(row["skill_keyword"]).strip(), str(row["skill_group"]).strip()),
            )
    return len(skills)


def _target_jobs(cur, job_ids):
    if job_ids is None:
        cur.execute(
            """
            SELECT id, skills
            FROM jobs_clean j
            WHERE NOT EXISTS (
                SELECT 1 FROM fact_job_skill_mapping m WHERE m.job_id = j.id
            );
            """
        )
    else:
        cur.execute(
            """
            SELECT id, skills
            FROM jobs_clean j
            WHERE j.id = ANY(%s)
               OR NOT EXISTS (
                    SELECT 1 FROM fact_job_skill_mapping m WHERE m.job_id = j.id
               );
            """,
            (list(job_ids),),
        )
    return cur.fetchall()


def reconcile_mappings(conn, job_ids=None):
    with conn.cursor() as cur:
        cur.execute("SELECT skill_id, skill_keyword FROM dim_skill;")
        skills = cur.fetchall()
        jobs = _target_jobs(cur, job_ids)
        if not jobs:
            return {"added": 0, "removed": 0}

        target_ids = [job_id for job_id, _ in jobs]
        cur.execute(
            "SELECT job_id, skill_id FROM fact_job_skill_mapping WHERE job_id = ANY(%s);",
            (target_ids,),
        )
        existing = {}
        for job_id, skill_id in cur.fetchall():
            existing.setdefault(job_id, set()).add(skill_id)

        added = 0
        removed = 0
        boundary = chr(92) + "b"
        for job_id, requirement in jobs:
            requirement_text = (requirement or "").lower()
            desired = set()
            for skill_id, keyword in skills:
                pattern = boundary + re.escape(keyword.lower()) + boundary
                if re.search(pattern, requirement_text):
                    desired.add(skill_id)

            current = existing.get(job_id, set())
            for skill_id in current - desired:
                cur.execute(
                    "DELETE FROM fact_job_skill_mapping WHERE job_id = %s AND skill_id = %s;",
                    (job_id, skill_id),
                )
                removed += cur.rowcount
            for skill_id in desired - current:
                cur.execute(
                    """
                    INSERT INTO fact_job_skill_mapping (job_id, skill_id)
                    VALUES (%s, %s)
                    ON CONFLICT (job_id, skill_id) DO NOTHING;
                    """,
                    (job_id, skill_id),
                )
                added += cur.rowcount

    return {"added": added, "removed": removed}


def main(conn, job_ids=None):
    load_dictionary(conn)
    return reconcile_mappings(conn, job_ids)
