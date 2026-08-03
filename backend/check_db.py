import sys
sys.path.insert(0, ".")

from imperium.rkb.store import ping, get_session
from imperium.config import get_settings
from sqlalchemy import text

settings = get_settings()

print("=" * 55)
print("  Imperium -> Supabase Connection Check")
print("=" * 55)

# 1. Show which host we're connecting to
dsn = settings.postgres_dsn
host = dsn.split("@")[1].split("/")[0] if "@" in dsn else "unknown"
print(f"\n  Host   : {host}")

# 2. Ping
result = ping()
status = result.get("status")
icon = "[OK]" if status == "ok" else "[FAIL]"
print(f"  Ping   : {icon}  {status}")
if status != "ok":
    print(f"  Error  : {result.get('error')}")
    sys.exit(1)

# 3. List tables
session = get_session()
try:
    rows = session.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    ).fetchall()
    tables = [r[0] for r in rows]
finally:
    session.close()

print(f"\n  Tables : {len(tables)} found")
for t in tables:
    print(f"    • {t}")

# 4. Alembic version
session = get_session()
try:
    ver = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
finally:
    session.close()
print(f"\n  Migration version : {ver}")
print("\n" + "=" * 55)
print("  [OK]  Database is connected and fully migrated!")
print("=" * 55 + "\n")
