"""Build analyst insights data directly from DuckDB OLAP with dim_role_family."""

import json
from decimal import Decimal


def query_analyst_insights_jobbert(connection, project_track: str | None = None, source_code: str = "saramin"):
    source_sql = "'" + source_code.replace("'", "''") + "'"

    # 1. Check source
    source_row = connection.execute(
        f"SELECT source_key FROM warehouse.dim_source WHERE source_code = {source_sql}"
    ).fetchone()
    if source_row is None:
        raise RuntimeError(f"OLAP chưa có source {source_code}.")
    source_key = int(source_row[0])

    track_filter = ""
    if project_track and project_track.lower() != "all":
        track_sql = "'" + project_track.replace("'", "''") + "'"
        track_filter = f"AND j.project_track = {track_sql}"

    # 2. Get all jobs with role family info
    jobs_query = f"""
        SELECT 
            j.job_key,
            j.source_job_key,
            j.title,
            coalesce(rf.role_family_name, j.role_family, 'Needs Review') AS role_family_name,
            coalesce(j.role_decision_status, 'PENDING') AS role_decision_status,
            coalesce(j.role_confidence, 0.0) AS role_confidence,
            j.project_track
        FROM warehouse.dim_job j
        LEFT JOIN warehouse.dim_role_family rf ON j.role_family_key = rf.role_family_key
        WHERE j.source_key = {source_key}
          {track_filter}
          AND j.is_current = TRUE
        ORDER BY j.title, j.source_job_key;
    """
    job_rows = connection.execute(jobs_query).fetchall()
    jobs = {
        int(r[0]): {
            "job_id": str(r[1]),
            "title": r[2] or "",
            "role_family": r[3],
            "decision_status": r[4],
            "confidence": float(r[5]),
        }
        for r in job_rows
    }
    job_keys = set(jobs.keys())

    # 3. Get labels (seniority & skill) for these jobs
    labels_query = f"""
        SELECT 
            b.job_key,
            b.label_type,
            b.label_text
        FROM warehouse.bridge_job_source_label b
        JOIN warehouse.dim_job j ON j.job_key = b.job_key
        WHERE j.source_key = {source_key}
          {track_filter}
          AND j.is_current = TRUE
          AND (b.label_type = 'skill' OR (b.source_field = 'job_levels_arr' AND b.label_type = 'seniority'))
        ORDER BY b.job_key, b.position;
    """
    label_rows = connection.execute(labels_query).fetchall()

    levels_by_job = {k: set() for k in job_keys}
    skills_by_job = {k: set() for k in job_keys}

    for jk, ltype, ltext in label_rows:
        jk = int(jk)
        if jk not in job_keys:
            continue
        if ltype == "seniority":
            levels_by_job[jk].add(ltext)
        elif ltype == "skill":
            skills_by_job[jk].add(ltext.strip())

    # 4. Aggregations:
    # A. Role Family Summary & Jobs
    role_groups_map = {}
    for jk, jdata in jobs.items():
        rf = jdata["role_family"]
        if rf not in role_groups_map:
            role_groups_map[rf] = {
                "role_family": rf,
                "job_count": 0,
                "jobs": [],
                "skills_counter": {},
                "level_skills_counter": {}, # level -> {skill -> count}
                "level_job_counts": {},    # level -> count
            }
        rg = role_groups_map[rf]
        rg["job_count"] += 1
        rg["jobs"].append({
            "job_id": jdata["job_id"],
            "title": jdata["title"],
            "decision_status": jdata["decision_status"],
            "confidence": jdata["confidence"],
            "levels": sorted(levels_by_job[jk]),
            "skills": sorted(skills_by_job[jk]),
        })

        # Count skills for this role family
        for sk in skills_by_job[jk]:
            rg["skills_counter"][sk] = rg["skills_counter"].get(sk, 0) + 1

        # Count skills by level for this role family
        job_levels = levels_by_job[jk] if levels_by_job[jk] else {"Chưa rõ level"}
        for lvl in job_levels:
            rg["level_job_counts"][lvl] = rg["level_job_counts"].get(lvl, 0) + 1
            if lvl not in rg["level_skills_counter"]:
                rg["level_skills_counter"][lvl] = {}
            for sk in skills_by_job[jk]:
                rg["level_skills_counter"][lvl][sk] = rg["level_skills_counter"][lvl].get(sk, 0) + 1

    # Format role groups
    formatted_role_groups = []
    for rf, rg in sorted(role_groups_map.items(), key=lambda x: -x[1]["job_count"]):
        # Top skills for role
        sorted_skills = sorted(
            [{"skill": sk, "job_count": c} for sk, c in rg["skills_counter"].items()],
            key=lambda x: (-x["job_count"], x["skill"])
        )

        # Top skills by level for role
        level_breakdown = []
        for lvl, jcnt in sorted(rg["level_job_counts"].items(), key=lambda x: -x[1]):
            sk_map = rg["level_skills_counter"].get(lvl, {})
            sorted_lvl_skills = sorted(
                [{"skill": sk, "job_count": c} for sk, c in sk_map.items()],
                key=lambda x: (-x["job_count"], x["skill"])
            )
            level_breakdown.append({
                "level": lvl,
                "job_count": jcnt,
                "unique_skill_count": len(sorted_lvl_skills),
                "top_skills": sorted_lvl_skills[:10],
                "all_skills": sorted_lvl_skills,
            })

        formatted_role_groups.append({
            "role_family": rf,
            "job_count": rg["job_count"],
            "unique_skill_count": len(sorted_skills),
            "top_skills": sorted_skills[:12],
            "all_skills": sorted_skills,
            "level_skills": level_breakdown,
            "jobs": sorted(rg["jobs"], key=lambda x: x["title"]),
        })

    # Overall level distribution
    all_levels_counter = {}
    for lvls in levels_by_job.values():
        for l in (lvls if lvls else ["Chưa rõ level"]):
            all_levels_counter[l] = all_levels_counter.get(l, 0) + 1

    return {
        "source_code": source_code,
        "project_track": project_track,
        "total_jobs": len(jobs),
        "model_version": "TechWolf/JobBERT-v3 (Normalized)",
        "method_note": (
            "Nhóm nghề được chuẩn hóa tự động bằng JobBERT V3 (1.024 chiều, gating tau=0.60, delta=0.06). "
            "Các kỹ năng được tổng hợp trực tiếp từ kho dữ liệu đa chiều DuckDB OLAP theo từng nhóm job và cấp bậc level."
        ),
        "role_groups": formatted_role_groups,
        "all_levels": sorted(
            [{"level": l, "job_count": c} for l, c in all_levels_counter.items()],
            key=lambda x: -x["job_count"]
        ),
    }


if __name__ == "__main__":
    import duckdb
    token = "KRasqQEqf0ztz-XMUfGMp8JsaAkYd5eyNuzgjvQ_kSY"
    conn = duckdb.connect()
    conn.execute(f"ATTACH 'quack:127.0.0.1:9494' AS warehouse_remote (token '{token}');")
    conn.execute("USE warehouse_remote;")
    res = query_analyst_insights_jobbert(conn)
    print("Success! Generated insights for", res["total_jobs"], "jobs across", len(res["role_groups"]), "role groups.")
    conn.close()
