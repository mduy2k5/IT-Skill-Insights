import json
import os
import re
from decimal import Decimal
from pathlib import Path
import unicodedata
from urllib.parse import urlparse

import duckdb
import psycopg2
from flask import Flask, abort, jsonify, render_template, request, url_for
from psycopg2.extras import RealDictCursor

try:
    from analyst_service import query_analyst_insights_jobbert
except ImportError:
    from web.analyst_service import query_analyst_insights_jobbert


app = Flask(__name__)
PROJECT_TRACK = os.environ.get("JOB_PROJECT_TRACK", "data")
WORK_MODES = {"onsite", "remote", "hybrid", "unknown"}
PAGE_SIZE = 12
BENCHMARK_PATH = Path(__file__).resolve().parent / "static" / "data" / "skill_benchmark_v0_1.json"
OLAP_SOURCE_CODE = os.environ.get("JOB_OLAP_SOURCE_CODE", "saramin")
RAW_SKILL_TAXONOMY_VERSION = "source-label-v1"
RAW_SENIORITY_MAPPING_VERSION = "source-label-v1"
ROLE_FAMILY_RULES_PATH = Path(__file__).resolve().parent / "config" / "job_role_families_v0_1.json"
ROLE_FAMILY_RULESET = json.loads(ROLE_FAMILY_RULES_PATH.read_text(encoding="utf-8"))


def get_conn():
    required = (
        "JOB_POSTGRES_HOST",
        "JOB_POSTGRES_DB",
        "JOB_POSTGRES_USER",
        "JOB_POSTGRES_PASSWORD",
    )
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError("Missing database settings: " + ", ".join(missing))
    return psycopg2.connect(
        host=os.environ["JOB_POSTGRES_HOST"],
        port=int(os.environ.get("JOB_POSTGRES_PORT", "5432")),
        dbname=os.environ["JOB_POSTGRES_DB"],
        user=os.environ["JOB_POSTGRES_USER"],
        password=os.environ["JOB_POSTGRES_PASSWORD"],
        connect_timeout=5,
    )


def safe_http_url(value):
    if not value:
        return None
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else None


def olap_sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def get_olap_conn():
    required = ("JOB_OLAP_TOKEN",)
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing OLAP settings: " + ", ".join(missing))

    host = os.environ.get("JOB_OLAP_HOST", "job-olap")
    port = int(os.environ.get("JOB_OLAP_PORT", "9494"))
    token = os.environ["JOB_OLAP_TOKEN"].replace("'", "''")
    connection = duckdb.connect()
    try:
        connection.execute(
            f"ATTACH 'quack:{host}:{port}' AS warehouse_remote "
            f"(TOKEN '{token}', DISABLE_SSL true)"
        )
        connection.execute("CONNECT warehouse_remote")
        return connection
    except Exception:
        connection.close()
        raise


def normalize_title_for_matching(title):
    value = unicodedata.normalize("NFKD", str(title or "").casefold())
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = value.replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def classify_job_family(title):
    normalized_title = normalize_title_for_matching(title)
    matches = []
    matched_terms = []
    for family in ROLE_FAMILY_RULESET["families"]:
        terms = [normalize_title_for_matching(term) for term in family["match_any"]]
        found_terms = [
            term for term in terms
            if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized_title)
        ]
        if found_terms:
            matches.append(family)
            matched_terms.extend(found_terms)

    if len(matches) == 1:
        family = matches[0]
        return {
            "family_id": family["id"],
            "name": family["label"],
            "status": "matched",
            "matched_terms": sorted(set(matched_terms)),
            "candidate_families": [],
        }

    review_group = ROLE_FAMILY_RULESET["review_group"]
    return {
        "family_id": review_group["id"],
        "name": review_group["label"],
        "status": "ambiguous" if matches else "unmatched",
        "matched_terms": sorted(set(matched_terms)),
        "candidate_families": [family["label"] for family in matches],
    }


def normalize_source_skill(value):
    return " ".join(str(value or "").split())


def query_analyst_insights():
    track_sql = olap_sql_literal(PROJECT_TRACK)
    source_sql = olap_sql_literal(OLAP_SOURCE_CODE)
    connection = get_olap_conn()
    try:
        source_row = connection.execute(
            f"""SELECT source_key FROM warehouse.dim_source
                WHERE source_code = {source_sql}"""
        ).fetchone()
        if source_row is None:
            raise RuntimeError(f"OLAP chưa có source {OLAP_SOURCE_CODE}.")
        source_key = int(source_row[0])

        job_rows = connection.execute(
            f"""SELECT job_key, source_job_key, title
                FROM warehouse.dim_job
                WHERE source_key = {source_key}
                  AND project_track = {track_sql}
                  AND is_current = TRUE
                ORDER BY title, source_job_key"""
        ).fetchall()
        jobs = {
            int(row[0]): {"job_id": str(row[1]), "title": row[2] or ""}
            for row in job_rows
        }
        job_keys = set(jobs)

        seniority_rows = connection.execute(
            f"""SELECT seniority_key, source_label, normalized_level
                FROM warehouse.dim_seniority
                WHERE source_key = {source_key}
                  AND mapping_version = {olap_sql_literal(RAW_SENIORITY_MAPPING_VERSION)}"""
        ).fetchall()
        source_label_to_level = {
            row[1]: {"source_label": row[1], "normalized_level": row[2]}
            for row in seniority_rows
        }

        label_rows = connection.execute(
            f"""SELECT labels.job_key, labels.source_field, labels.label_type,
                          labels.label_text
                FROM warehouse.bridge_job_source_label AS labels
                JOIN warehouse.dim_job AS job ON job.job_key = labels.job_key
                WHERE job.source_key = {source_key}
                  AND job.project_track = {track_sql}
                  AND job.is_current = TRUE
                  AND (labels.label_type = 'skill'
                       OR (labels.source_field = 'job_levels_arr'
                           AND labels.label_type = 'seniority'))
                ORDER BY labels.job_key, labels.source_field, labels.position"""
        ).fetchall()
        skill_dimensions = {
            row[0]
            for row in connection.execute(
                f"""SELECT canonical_name FROM warehouse.dim_skill
                    WHERE taxonomy_version = {olap_sql_literal(RAW_SKILL_TAXONOMY_VERSION)}
                      AND is_active = TRUE"""
            ).fetchall()
        }
    finally:
        connection.close()

    levels_by_job = {job_key: set() for job_key in job_keys}
    skills_by_job = {job_key: set() for job_key in job_keys}
    missing_level_labels = set()
    missing_skill_labels = set()
    for job_key, source_field, label_type, label_text in label_rows:
        job_key = int(job_key)
        if job_key not in job_keys:
            continue
        if source_field == "job_levels_arr" and label_type == "seniority":
            level = source_label_to_level.get(label_text)
            if level is None:
                missing_level_labels.add(label_text)
            else:
                levels_by_job[job_key].add(level["source_label"])
        elif label_type == "skill":
            skill_name = normalize_source_skill(label_text)
            if skill_name in skill_dimensions:
                skills_by_job[job_key].add(skill_name)
            else:
                missing_skill_labels.add(skill_name)

    if missing_level_labels:
        raise RuntimeError("Một số nhãn level trong bridge chưa có trong dim_seniority; hãy nạp lại OLAP.")
    if missing_skill_labels:
        raise RuntimeError("Một số nhãn skill trong bridge chưa có trong dim_skill; hãy nạp lại OLAP.")

    family_rules = ROLE_FAMILY_RULESET["families"]
    review_group = ROLE_FAMILY_RULESET["review_group"]
    family_by_id = {family["id"]: family for family in family_rules}
    role_order = [family["id"] for family in family_rules] + [review_group["id"]]
    role_jobs = {}
    level_jobs = {}
    skill_jobs = {}
    role_level_jobs = {}
    role_skill_jobs = {}
    role_classifications = {}
    for job_key, job in jobs.items():
        classification = classify_job_family(job["title"])
        role_classifications[job_key] = classification
        role_id = classification["family_id"]
        role_jobs.setdefault(role_id, []).append(job_key)
        for source_label in levels_by_job[job_key]:
            level_jobs.setdefault(source_label, set()).add(job_key)
            for skill in skills_by_job[job_key]:
                skill_jobs.setdefault(source_label, {}).setdefault(skill, set()).add(job_key)
            if classification["status"] == "matched":
                role_level_jobs.setdefault(role_id, {}).setdefault(source_label, set()).add(job_key)
                for skill in skills_by_job[job_key]:
                    role_skill_jobs.setdefault(role_id, {}).setdefault(source_label, {}).setdefault(skill, set()).add(job_key)

    def summarize_level_skills(level_job_index, level_skill_index):
        result = []
        for source_label, job_key_set in sorted(
            level_job_index.items(), key=lambda item: (-len(item[1]), item[0].casefold())
        ):
            skills = sorted(
                (
                    {"skill": name, "job_count": len(skill_job_key_set)}
                    for name, skill_job_key_set in level_skill_index.get(source_label, {}).items()
                ),
                key=lambda item: (-item["job_count"], item["skill"].casefold()),
            )
            level = source_label_to_level[source_label]
            result.append(
                {
                    "source_label": source_label,
                    "normalized_level": level["normalized_level"],
                    "job_count": len(job_key_set),
                    "job_ids": sorted(jobs[job_key]["job_id"] for job_key in job_key_set),
                    "unique_skill_count": len(skills),
                    "top_skills": skills[:8],
                    "all_skills": skills,
                }
            )
        return result

    role_groups = []
    for role_id in role_order:
        job_keys_for_role = role_jobs.get(role_id)
        if not job_keys_for_role:
            continue
        is_review_group = role_id == review_group["id"]
        role_name = review_group["label"] if is_review_group else family_by_id[role_id]["label"]
        grouped_jobs = sorted(
            job_keys_for_role,
            key=lambda job_key: (jobs[job_key]["title"].casefold(), jobs[job_key]["job_id"]),
        )
        role_groups.append(
            {
                "role_id": role_id,
                "name": role_name,
                "review_required": is_review_group,
                "job_count": len(grouped_jobs),
                "jobs": [
                    {
                        "job_id": jobs[job_key]["job_id"],
                        "title": jobs[job_key]["title"],
                        "source_levels": sorted(levels_by_job[job_key], key=str.casefold),
                        "classification_status": role_classifications[job_key]["status"],
                        "candidate_families": role_classifications[job_key]["candidate_families"],
                    }
                    for job_key in grouped_jobs
                ],
                "skill_levels": [] if is_review_group else summarize_level_skills(
                    role_level_jobs.get(role_id, {}), role_skill_jobs.get(role_id, {})
                ),
            }
        )

    multi_level_job_count = sum(1 for labels in levels_by_job.values() if len(labels) > 1)
    level_rows = summarize_level_skills(level_jobs, skill_jobs)

    return {
        "source_code": OLAP_SOURCE_CODE,
        "project_track": PROJECT_TRACK,
        "job_count": len(jobs),
        "role_family_version": ROLE_FAMILY_RULESET["version"],
        "role_review_job_count": len(role_jobs.get(review_group["id"], [])),
        "role_method": (
            "Chuẩn hóa Unicode, chữ hoa/thường và dấu để dò cụm từ trong bộ quy tắc có version. "
            "Chỉ tự gom khi khớp đúng một họ nghề; không khớp hoặc khớp nhiều họ được đưa vào Cần rà title "
            "và chưa cộng chung skill. Title gốc luôn được giữ để đối chiếu."
        ),
        "role_groups": role_groups,
        "source_level_summary": {
            "unique_job_count": len(jobs),
            "label_membership_count": sum(len(job_labels) for job_labels in levels_by_job.values()),
            "multi_level_job_count": multi_level_job_count,
            "mapping_version": RAW_SENIORITY_MAPPING_VERSION,
            "levels": level_rows,
        },
        "skill_source_note": (
            "Skill lấy từ source tags (skills_arr / extra_skills) đã nạp vào dim_skill; "
            "đây là tag do nguồn cung cấp, không phải kỹ năng GLiNER trích từ mô tả. "
            "Tần suất là số job có tag đó trong từng nhãn level nguồn."
        ),
        "skill_levels": level_rows,
    }


def format_salary(row):
    if row.get("salary_display"):
        return row["salary_display"]
    minimum = row.get("salary_min")
    maximum = row.get("salary_max")
    currency = (row.get("salary_currency") or "").strip()
    period = (row.get("salary_period") or "").strip()
    if minimum is None and maximum is None:
        return ""

    def amount(value):
        if isinstance(value, Decimal):
            return format(value.normalize(), "f")
        return str(value)

    if minimum is not None and maximum is not None:
        text = f"{amount(minimum)} – {amount(maximum)}"
    elif minimum is not None:
        text = f"Từ {amount(minimum)}"
    else:
        text = f"Đến {amount(maximum)}"
    if currency:
        text += f" {currency}"
    if period:
        text += f" / {period.lower()}"
    return text


def job_filters():
    conditions = ["j.project_track = %s"]
    params = [PROJECT_TRACK]

    query = request.args.get("q", "").strip()
    if len(query) > 120:
        raise ValueError("Từ khóa tìm kiếm tối đa 120 ký tự.")
    if query:
        conditions.append("(j.title ILIKE %s OR c.display_name ILIKE %s)")
        params.extend([f"%{query}%", f"%{query}%"])

    location = request.args.get("location", "").strip()
    if location:
        conditions.append(
            """EXISTS (
                SELECT 1 FROM job_locations loc_filter
                WHERE loc_filter.job_id = j.job_id
                  AND (loc_filter.province_city = %s OR loc_filter.district = %s)
            )"""
        )
        params.extend([location, location])

    work_mode = request.args.get("work_mode", "").strip().lower()
    if work_mode:
        if work_mode not in WORK_MODES:
            raise ValueError("Hình thức làm việc không hợp lệ.")
        conditions.append("j.work_mode = %s")
        params.append(work_mode)

    level = request.args.get("level", "").strip()
    if level:
        conditions.append(
            """EXISTS (
                SELECT 1 FROM job_source_labels level_filter
                WHERE level_filter.job_id = j.job_id
                  AND level_filter.source_field = 'job_levels_arr'
                  AND level_filter.label_type = 'seniority'
                  AND level_filter.label_text = %s
            )"""
        )
        params.append(level)

    return " AND ".join(conditions), params


@app.route("/")
def home():
    return render_template("index.html", project_track=PROJECT_TRACK)


@app.route("/analyst")
def analyst():
    return render_template("analyst.html", project_track=PROJECT_TRACK)


@app.route("/api/analyst/skill-benchmark")
def api_skill_benchmark():
    try:
        benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return jsonify({"error": "Chưa tải được bộ benchmark kỹ năng."}), 503
    return jsonify(benchmark)


@app.route("/api/analyst/insights")
def api_analyst_insights():
    try:
        conn = get_olap_conn()
        try:
            track = request.args.get("track", PROJECT_TRACK)
            return jsonify(query_analyst_insights_jobbert(conn, project_track=track, source_code=OLAP_SOURCE_CODE))
        finally:
            conn.close()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception:
        app.logger.exception("Analyst could not read the OLAP warehouse")
        return jsonify({"error": "Chưa đọc được dữ liệu Analyst trực tiếp từ OLAP."}), 503


@app.route("/healthz")
def healthz():
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return jsonify({"status": "ok"})
    except Exception:
        return jsonify({"status": "database_unavailable"}), 503


@app.route("/api/filters")
def api_filters():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT DISTINCT loc.province_city
               FROM job_locations loc
               JOIN jobs j ON j.job_id = loc.job_id
               WHERE j.project_track = %s
                 AND loc.province_city IS NOT NULL
                 AND BTRIM(loc.province_city) <> ''
               ORDER BY loc.province_city""",
            (PROJECT_TRACK,),
        )
        locations = [row[0] for row in cur.fetchall()]

        cur.execute(
            """SELECT DISTINCT label.label_text
               FROM job_source_labels label
               JOIN jobs j ON j.job_id = label.job_id
               WHERE j.project_track = %s
                 AND label.source_field = 'job_levels_arr'
                 AND label.label_type = 'seniority'
               ORDER BY label.label_text""",
            (PROJECT_TRACK,),
        )
        levels = [row[0] for row in cur.fetchall()]

    return jsonify({"locations": locations, "levels": levels})


@app.route("/api/jobs")
def api_jobs():
    try:
        where_sql, params = job_filters()
        page = int(request.args.get("page", "1"))
        if page < 1 or page > 10000:
            raise ValueError("Trang phải nằm trong khoảng 1–10000.")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    offset = (page - 1) * PAGE_SIZE
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""SELECT COUNT(*) AS total
                FROM jobs j
                LEFT JOIN companies c ON c.company_id = j.company_id
                WHERE {where_sql}""",
            params,
        )
        total = cur.fetchone()["total"]

        cur.execute(
            f"""SELECT
                    j.job_id,
                    j.title,
                    j.work_mode,
                    j.listing_status,
                    j.published_at,
                    c.display_name AS company_name,
                    loc.province_city,
                    loc.district,
                    comp.display_text AS salary_display,
                    comp.min_amount AS salary_min,
                    comp.max_amount AS salary_max,
                    comp.currency_code AS salary_currency,
                    comp.pay_period AS salary_period,
                    labels.levels
                FROM jobs j
                LEFT JOIN companies c ON c.company_id = j.company_id
                LEFT JOIN LATERAL (
                    SELECT province_city, district
                    FROM job_locations
                    WHERE job_id = j.job_id
                    ORDER BY position
                    LIMIT 1
                ) loc ON TRUE
                LEFT JOIN job_compensations comp ON comp.job_id = j.job_id
                LEFT JOIN LATERAL (
                    SELECT string_agg(DISTINCT label_text, ', ' ORDER BY label_text)
                           FILTER (WHERE source_field = 'job_levels_arr' AND label_type = 'seniority') AS levels
                    FROM job_source_labels
                    WHERE job_id = j.job_id
                ) labels ON TRUE
                WHERE {where_sql}
                ORDER BY j.published_at DESC NULLS LAST, j.created_at DESC
                LIMIT %s OFFSET %s""",
            params + [PAGE_SIZE, offset],
        )
        rows = cur.fetchall()

    jobs = []
    for row in rows:
        job_id = str(row["job_id"])
        jobs.append(
            {
                "job_id": job_id,
                "title": row["title"],
                "company_name": row["company_name"] or "Chưa cập nhật công ty",
                "work_mode": row["work_mode"],
                "listing_status": row["listing_status"],
                "published_at": row["published_at"].isoformat() if row["published_at"] else None,
                "province_city": row["province_city"],
                "district": row["district"],
                "salary": format_salary(row),
                "levels": row["levels"] or "",
                "detail_url": url_for("job_detail", job_id=job_id),
            }
        )

    return jsonify(
        {
            "jobs": jobs,
            "total": total,
            "page": page,
            "per_page": PAGE_SIZE,
            "total_pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
        }
    )


@app.route("/jobs/<uuid:job_id>")
def job_detail(job_id):
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT j.job_id, j.title, j.source_url, j.application_url,
                      j.work_mode, j.listing_status, j.published_at, j.expires_at,
                      c.display_name AS company_name, c.logo_url,
                      d.overview_text, d.fetch_status,
                      comp.display_text AS salary_display,
                      comp.min_amount AS salary_min, comp.max_amount AS salary_max,
                      comp.currency_code AS salary_currency, comp.pay_period AS salary_period,
                      labels.levels
               FROM jobs j
               LEFT JOIN companies c ON c.company_id = j.company_id
               LEFT JOIN job_descriptions d ON d.job_id = j.job_id
               LEFT JOIN job_compensations comp ON comp.job_id = j.job_id
               LEFT JOIN LATERAL (
                   SELECT string_agg(DISTINCT label_text, ', ' ORDER BY label_text)
                          FILTER (WHERE source_field = 'job_levels_arr' AND label_type = 'seniority') AS levels
                   FROM job_source_labels
                   WHERE job_id = j.job_id
               ) labels ON TRUE
               WHERE j.job_id = %s AND j.project_track = %s""",
            (str(job_id), PROJECT_TRACK),
        )
        job = cur.fetchone()
        if job is None:
            abort(404)

        cur.execute(
            """SELECT province_city, district, ward, address_line
               FROM job_locations
               WHERE job_id = %s
               ORDER BY position""",
            (str(job_id),),
        )
        locations = cur.fetchall()

    job["salary"] = format_salary(job)
    job["source_url"] = safe_http_url(job["source_url"])
    job["application_url"] = safe_http_url(job["application_url"])
    job["logo_url"] = safe_http_url(job["logo_url"])
    job["published_at"] = job["published_at"].isoformat() if job["published_at"] else None
    job["expires_at"] = job["expires_at"].isoformat() if job["expires_at"] else None
    return render_template(
        "job_detail.html",
        job=job,
        locations=locations,
        project_track=PROJECT_TRACK,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
