import os
from decimal import Decimal
from urllib.parse import urlparse

import psycopg2
from flask import Flask, abort, jsonify, render_template, request, url_for
from psycopg2.extras import RealDictCursor


app = Flask(__name__)
PROJECT_TRACK = os.environ.get("JOB_PROJECT_TRACK", "data")
WORK_MODES = {"onsite", "remote", "hybrid", "unknown"}
PAGE_SIZE = 12


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
                  AND level_filter.label_type = 'seniority'
                  AND level_filter.label_text = %s
            )"""
        )
        params.append(level)

    return " AND ".join(conditions), params


@app.route("/")
def home():
    return render_template("index.html", project_track=PROJECT_TRACK)


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
                           FILTER (WHERE label_type = 'seniority') AS levels
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
                          FILTER (WHERE label_type = 'seniority') AS levels
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
