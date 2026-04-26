#!/bin/sh
set -eu

if [ "${DB_BACKEND:-mysql}" = "mysql" ]; then
  echo "[entrypoint] waiting for MySQL ${MYSQL_HOST:-mysql}:${MYSQL_PORT:-3306}"
  python - <<'PY'
import os
import time
import pymysql

host = os.getenv("MYSQL_HOST", "mysql")
port = int(os.getenv("MYSQL_PORT", "3306"))
user = os.getenv("MYSQL_USER", "you_where")
password = os.getenv("MYSQL_PASSWORD", "")
database = os.getenv("MYSQL_DB", "you_where")

last_error = None
for _ in range(60):
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=3,
            charset="utf8mb4",
        )
        conn.close()
        print("[entrypoint] MySQL is ready")
        break
    except Exception as exc:
        last_error = exc
        time.sleep(2)
else:
    raise SystemExit(f"MySQL is not ready: {last_error}")
PY

  echo "[entrypoint] applying schema"
  python scripts/apply_schema_updates.py

  if [ "${SEED_TEST_USERS:-0}" = "1" ]; then
    echo "[entrypoint] seeding hidden test users"
    python scripts/seed_test_users.py
  fi
fi

exec "$@"
