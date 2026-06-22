#!/usr/bin/env bash
# MySQL 集成回归：启动测试库并运行 tests_mysql/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[mysql-test] 启动 docker compose..."
docker compose -f docker-compose.test.yml up -d

echo "[mysql-test] 等待 MySQL 健康..."
for i in $(seq 1 60); do
  if docker compose -f docker-compose.test.yml exec -T mysql_test \
    mysqladmin ping -h 127.0.0.1 -uroot -ptest_root_pw --silent 2>/dev/null; then
    break
  fi
  sleep 2
  if [ "$i" -eq 60 ]; then
    echo "MySQL 未就绪"
    exit 1
  fi
done

export MYSQL_TEST_HOST="${MYSQL_TEST_HOST:-127.0.0.1}"
export MYSQL_TEST_PORT="${MYSQL_TEST_PORT:-3307}"
export MYSQL_TEST_USER="${MYSQL_TEST_USER:-you_where_test}"
export MYSQL_TEST_PASSWORD="${MYSQL_TEST_PASSWORD:-test_app_pw}"
export MYSQL_TEST_DB="${MYSQL_TEST_DB:-you_where_test}"

echo "[mysql-test] pytest tests_mysql/ ..."
python -m pytest tests_mysql/ -v --tb=short "$@"
