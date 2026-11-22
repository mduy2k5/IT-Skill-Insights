import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
from web.analyst_service import query_analyst_insights_jobbert

token = "KRasqQEqf0ztz-XMUfGMp8JsaAkYd5eyNuzgjvQ_kSY"
conn = duckdb.connect()
sql_attach = f"ATTACH 'quack:127.0.0.1:9494' AS warehouse_remote (token '{token}');"
conn.execute(sql_attach)
conn.execute("USE warehouse_remote;")

res = query_analyst_insights_jobbert(conn, project_track="all")
print(f"Total jobs: {res['total_jobs']}")
print(f"Role groups count: {len(res['role_groups'])}")
for rg in res["role_groups"][:5]:
    print(f"\n* {rg['role_family']} ({rg['job_count']} jobs, {rg['unique_skill_count']} skills)")
    print("    Top skills:", [s["skill"] + f" ({s['job_count']})" for s in rg["top_skills"][:6]])
    print("    Top levels:", [lvl["level"] + f" ({lvl['job_count']} jobs)" for lvl in rg["level_skills"][:3]])
    for lvl in rg["level_skills"][:2]:
        print(f"      [{lvl['level']}] skills:", [s["skill"] + f" ({s['job_count']})" for s in lvl["top_skills"][:4]])

conn.close()
