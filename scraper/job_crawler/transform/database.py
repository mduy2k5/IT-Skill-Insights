import pandas as pd

from scraper.job_crawler.transform.weba_transformer import WebATransformer

# ─────────────────────────────────────────────
# Hàm tiện ích
# ─────────────────────────────────────────────
def lowercase_and_strip(df, column):
    df[column] = df[column].str.lower().str.strip()
    return df

def delete_all_data(conn):
    cur = conn.cursor()
    tables = [
        'fact_job_skill_mapping',
        'job_level_mapping',
        'jobs_clean',
        'company_mapping',
        'location_mapping',
        'level_mapping',
        'tag_mapping',
        'date_mapping',
        'job_type_mapping',
        'dim_skill',
        'dim_job_title'
    ]
    deleted_rows = 0
    for table in tables:
        cur.execute(f"DELETE FROM {table};")
        deleted_rows += cur.rowcount
    return deleted_rows

def insert_company_mapping(conn, df):
    cur = conn.cursor()
    if 'company' not in df.columns or df.empty:
        return 0
    df['raw_name'] = df['company']
    df['clean_name'] = df['company'].str.lower().str.strip()
    inserted = 0
    for _, row in df.iterrows():
        if pd.isna(row['raw_name']):
            continue
        cur.execute("""
        INSERT INTO company_mapping (raw_name, clean_name)
        VALUES (%s, %s)
        ON CONFLICT (clean_name) DO NOTHING;
        """, (row['raw_name'], row['clean_name']))
        inserted += cur.rowcount
    return inserted


def insert_location_mapping(conn, df):
    cur = conn.cursor()
    if 'location' not in df.columns or df.empty:
        return 0
    df['raw_location'] = df['location']
    df['clean_location'] = df['location'].str.lower().str.strip()
    df = WebATransformer.city_province_split(df)
    df[['city', 'province']] = df[['city', 'province']].where(pd.notna(df[['city', 'province']]), None)
    inserted = 0
    for _, row in df.iterrows():
        if pd.isna(row['raw_location']):
            continue
        cur.execute("""
        INSERT INTO location_mapping (raw_location, clean_location, city, province)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (clean_location) DO NOTHING;
        """, (row['raw_location'], row['clean_location'], row['city'], row['province']))
        inserted += cur.rowcount
    return inserted


def insert_level_mapping(conn, df):
    cur = conn.cursor()
    if 'level' not in df.columns or df.empty:
        return 0
    df = WebATransformer.level_split(df)
    inserted = 0
    for _, row in df.iterrows():
        if row['level'] is not None:
            for raw_level in row['level']:
                clean_level = raw_level.lower().strip()
                cur.execute("""
                INSERT INTO level_mapping (raw_level, clean_level)
                VALUES (%s, %s)
                ON CONFLICT (clean_level) DO NOTHING;
                """, (raw_level, clean_level))
                inserted += cur.rowcount
    return inserted

def insert_job_level_mapping(conn, df):
    # Xử lý trực tiếp trong insert_jobs_clean() — giữ lại cho backward compatibility
    return {"added": 0, "removed": 0}


def insert_tag_mapping(conn, df):
    cur = conn.cursor()
    if 'tags' not in df.columns or df.empty:
        return 0
    inserted = 0
    for value in df['tags']:
        if value is None or (not isinstance(value, (list, tuple)) and pd.isna(value)):
            continue
        raw_tags = value if isinstance(value, (list, tuple)) else str(value).split(',')
        for raw_tag in raw_tags:
            if raw_tag is None or pd.isna(raw_tag):
                continue
            raw_tag = str(raw_tag).strip()
            if not raw_tag:
                continue
            clean_tag = raw_tag.lower()
            cur.execute("""
            INSERT INTO tag_mapping (raw_tag, clean_tag)
            VALUES (%s, %s)
            ON CONFLICT (clean_tag) DO NOTHING;
            """, (raw_tag, clean_tag))
            inserted += cur.rowcount
    return inserted


def insert_date_mapping(conn, df):
    cur = conn.cursor()
    if 'posted_at' not in df.columns or df.empty:
        return 0
    df['raw_date'] = df['posted_at']
    df['clean_date'] = pd.to_datetime(df['posted_at'], errors='coerce').dt.date
    df['day']   = pd.to_datetime(df['clean_date'], errors='coerce').dt.day
    df['month'] = pd.to_datetime(df['clean_date'], errors='coerce').dt.month
    df['year']  = pd.to_datetime(df['clean_date'], errors='coerce').dt.year
    inserted = 0
    for _, row in df.iterrows():
        if pd.notna(row['clean_date']):
            cur.execute("""
            INSERT INTO date_mapping (raw_date, clean_date, day, month, year)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (clean_date) DO NOTHING;
            """, (row['raw_date'], row['clean_date'], row['day'], row['month'], row['year']))
            inserted += cur.rowcount
    return inserted


def insert_job_type_mapping(conn, df):
    cur = conn.cursor()
    df['raw_job_type'] = df['job_type']
    df['clean_job_type'] = df['job_type'].str.lower().str.strip()
    inserted = 0
    for _, row in df.iterrows():
        if pd.notna(row['clean_job_type']):
            cur.execute("""
            INSERT INTO job_type_mapping (raw_job_type, clean_job_type)
            VALUES (%s, %s)
            ON CONFLICT (clean_job_type) DO NOTHING;
            """, (row['raw_job_type'], row['clean_job_type']))
            inserted += cur.rowcount
    return inserted


class SourceIdentityConflict(ValueError):
    pass


def insert_jobs_clean(conn, df):
    stats = {"inserted": 0, "updated": 0, "unchanged": 0, "changed_ids": []}
    if df.empty:
        return stats

    with conn.cursor() as cur:
        def lookup_id(table, key_column, value, default=None):
            if value is None or pd.isna(value):
                return default
            cur.execute(
                "SELECT id FROM " + table + " WHERE " + key_column + " = %s",
                (str(value).lower().strip(),),
            )
            result = cur.fetchone()
            return result[0] if result else default

        def text_value(row, name, default=""):
            value = row.get(name)
            if value is None or pd.isna(value):
                return default
            return str(value).strip()

        def items(value):
            if value is None:
                return []
            if isinstance(value, (list, tuple)):
                return [str(item).strip() for item in value if item is not None and not pd.isna(item)]
            if pd.isna(value):
                return []
            return [part.strip() for part in str(value).split(",") if part.strip()]

        default_company = lookup_id("company_mapping", "clean_name", "")
        default_location = lookup_id("location_mapping", "clean_location", "")
        default_job_type = lookup_id("job_type_mapping", "clean_job_type", "")

        for _, row in df.iterrows():
            link = text_value(row, "link")
            if not link:
                raise ValueError("A normalized job is missing its source link.")

            company_id = lookup_id("company_mapping", "clean_name", row.get("company"), default_company)
            location_id = lookup_id("location_mapping", "clean_location", row.get("location"), default_location)
            job_type_id = lookup_id("job_type_mapping", "clean_job_type", row.get("job_type"), default_job_type)

            posted_at_id = None
            posted_at = row.get("posted_at")
            if posted_at is not None and not pd.isna(posted_at):
                clean_date = pd.to_datetime(posted_at, errors="coerce")
                if not pd.isna(clean_date):
                    cur.execute("SELECT id FROM date_mapping WHERE clean_date = %s", (clean_date.date(),))
                    result = cur.fetchone()
                    posted_at_id = result[0] if result else None

            tags_id = []
            for tag in items(row.get("tags")):
                tag_id = lookup_id("tag_mapping", "clean_tag", tag)
                if tag_id is not None:
                    tags_id.append(str(tag_id))

            levels = items(row.get("level"))
            desired_level_ids = set()
            for level in levels:
                level_id = lookup_id("level_mapping", "clean_level", level)
                if level_id is not None:
                    desired_level_ids.add(level_id)

            values = [
                text_value(row, "job_title"),
                company_id,
                text_value(row, "salary"),
                location_id,
                job_type_id,
                text_value(row, "experience"),
                tags_id or None,
                posted_at_id,
                link,
                text_value(row, "logo_link"),
                text_value(row, "source", "job_crawler"),
                text_value(row, "responsibilities"),
                text_value(row, "skills"),
                text_value(row, "benefits"),
            ]

            cur.execute(
                """
                SELECT id, source, job_title, company_id, salary, location_id, job_type_id,
                       experience, tags_id, posted_at_id, link, logo_link,
                       responsibilities, skills, benefits
                FROM jobs_clean
                WHERE link = %s
                FOR UPDATE;
                """,
                (link,),
            )
            existing = cur.fetchone()

            if existing is None:
                cur.execute(
                    """
                    INSERT INTO jobs_clean (
                        job_title, company_id, salary, location_id, job_type_id, experience,
                        tags_id, posted_at_id, link, logo_link, source, responsibilities, skills, benefits
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    values,
                )
                job_id = cur.fetchone()[0]
                stats["inserted"] += 1
                stats["changed_ids"].append(job_id)
                continue

            job_id, existing_source = existing[0], existing[1]
            incoming_source = values[10]
            if (existing_source or "").casefold() != (incoming_source or "").casefold():
                raise SourceIdentityConflict(
                    "Source identity conflict for link " + link
                    + ": existing source=" + str(existing_source)
                    + ", incoming source=" + str(incoming_source)
                )

            # Preserve the stored source spelling so a same-source replay does not rename it.
            values[10] = existing_source
            existing_data = tuple(existing[2:])
            incoming_data = tuple(values[:10] + values[11:])

            detail_status = row.get("status_crawl_detail")
            if detail_status is None or pd.isna(detail_status):
                detail_complete = False
            elif isinstance(detail_status, str):
                detail_complete = detail_status.strip().lower() in ("true", "t", "1", "yes")
            else:
                detail_complete = bool(detail_status)
            if not detail_complete:
                protected_pairs = ((10, 11), (11, 12), (12, 13))
                existing_data_list = list(existing_data)
                for existing_index, incoming_index in protected_pairs:
                    if not values[incoming_index] and existing_data_list[existing_index]:
                        values[incoming_index] = existing_data_list[existing_index]
                incoming_data = tuple(values[:10] + values[11:])

            cur.execute("SELECT level_id FROM job_level_mapping WHERE job_id = %s;", (job_id,))
            existing_level_ids = {level_id for (level_id,) in cur.fetchall()}
            level_changed = desired_level_ids != existing_level_ids
            data_changed = incoming_data != existing_data

            if data_changed:
                cur.execute(
                    """
                    UPDATE jobs_clean
                    SET job_title = %s, company_id = %s, salary = %s, location_id = %s,
                        job_type_id = %s, experience = %s, tags_id = %s, posted_at_id = %s,
                        link = %s, logo_link = %s, responsibilities = %s, skills = %s, benefits = %s
                    WHERE id = %s;
                    """,
                    tuple(values[:10] + values[11:] + [job_id]),
                )

            if data_changed or level_changed:
                stats["updated"] += 1
                stats["changed_ids"].append(job_id)
            else:
                stats["unchanged"] += 1

    return stats

def sync_job_level_mapping(conn, clean_df, job_ids):
    stats = {"added": 0, "removed": 0}
    if not job_ids:
        return stats

    levels_by_link = {}
    for _, row in clean_df.iterrows():
        link = row.get("link")
        if link is None or pd.isna(link):
            continue
        level_value = row.get("level")
        if level_value is None:
            levels = []
        elif isinstance(level_value, (list, tuple)):
            levels = [str(value).strip() for value in level_value if value is not None and not pd.isna(value)]
        elif pd.isna(level_value):
            levels = []
        else:
            levels = [part.strip() for part in str(level_value).split(",") if part.strip()]
        levels_by_link[str(link).strip()] = levels

    with conn.cursor() as cur:
        cur.execute("SELECT id, link FROM jobs_clean WHERE id = ANY(%s);", (list(job_ids),))
        jobs = cur.fetchall()

        for job_id, link in jobs:
            desired_level_ids = set()
            for level in levels_by_link.get(link, []):
                cur.execute(
                    "SELECT id FROM level_mapping WHERE clean_level = %s;",
                    (level.lower().strip(),),
                )
                result = cur.fetchone()
                if result:
                    desired_level_ids.add(result[0])

            cur.execute("SELECT level_id FROM job_level_mapping WHERE job_id = %s;", (job_id,))
            existing_level_ids = {level_id for (level_id,) in cur.fetchall()}

            for level_id in existing_level_ids - desired_level_ids:
                cur.execute(
                    "DELETE FROM job_level_mapping WHERE job_id = %s AND level_id = %s;",
                    (job_id, level_id),
                )
                stats["removed"] += cur.rowcount

            for level_id in desired_level_ids - existing_level_ids:
                cur.execute(
                    """
                    INSERT INTO job_level_mapping (job_id, level_id)
                    VALUES (%s, %s)
                    ON CONFLICT (job_id, level_id) DO NOTHING;
                    """,
                    (job_id, level_id),
                )
                stats["added"] += cur.rowcount

    return stats
