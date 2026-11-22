import duckdb
from pathlib import Path

token = "KRasqQEqf0ztz-XMUfGMp8JsaAkYd5eyNuzgjvQ_kSY"
conn = duckdb.connect()
sql_attach = f"ATTACH 'quack:127.0.0.1:9494' AS warehouse_remote (token '{token}');"
conn.execute(sql_attach)

conn.execute("USE warehouse_remote;")

migration_sql = Path("database/olap/migrations/003_add_role_family_dimension.sql").read_text(encoding="utf-8")

print("Applying 003_add_role_family_dimension.sql to DuckDB OLAP...")
conn.execute(migration_sql)
print("Migration 003 executed successfully!")

print("\nVerify dim_role_family:")
rows = conn.execute("SELECT * FROM warehouse.dim_role_family LIMIT 5;").fetchall()
for r in rows:
    print(r)

conn.close()
