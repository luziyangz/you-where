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
  python scripts/apply_schema_updates.py || {
    echo "[entrypoint] WARN: schema sync failed; check DB credentials and logs" >&2
    exit 1
  }

  echo "[entrypoint] seeding store catalog metadata"
  python scripts/seed_store_books.py

  if [ "${STORE_ENABLE_NETWORK:-0}" = "1" ]; then
    mkdir -p /app/logs 2>/dev/null || true
    echo "[entrypoint] scheduling Gutendex zh catalog sync in background"
    nohup python scripts/sync_gutendex_zh_catalog.py --max-pages "${GUTENDEX_ZH_SYNC_MAX_PAGES:-30}" >>/app/logs/gutendex_zh_sync.log 2>&1 &
  fi

  # 正文预取耗时长，必须在后台执行，否则会阻塞 uvicorn，导致 backend 不健康、nginx 无法启动
  if [ "${STORE_PREFETCH_CONTENT:-1}" = "1" ]; then
    mkdir -p /app/logs 2>/dev/null || true
    echo "[entrypoint] scheduling public-domain prefetch in background (see /app/logs/catalog_prefetch.log)"
    nohup python scripts/prefetch_catalog_contents.py >>/app/logs/catalog_prefetch.log 2>&1 &
  fi

  if [ "${SEED_TEST_USERS:-0}" = "1" ]; then
    echo "[entrypoint] seeding hidden test users"
    python scripts/seed_test_users.py
  fi
fi

exec "$@"
