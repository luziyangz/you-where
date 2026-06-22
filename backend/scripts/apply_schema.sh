#!/bin/sh
# 在 backend 容器内执行 schema 同步（宿主机无 Python 依赖时勿直接 python scripts/apply_schema_updates.py）
set -eu

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  echo "未找到 docker compose，请安装 Docker Compose 插件。" >&2
  exit 1
}

# 已在容器内（entrypoint 或 docker exec）
if [ -f /.dockerenv ]; then
  exec python scripts/apply_schema_updates.py "$@"
fi

if compose ps backend 2>/dev/null | grep -qE 'Up|running'; then
  exec compose exec backend python scripts/apply_schema_updates.py "$@"
fi

cat >&2 <<'EOF'
无法在宿主机直接运行：未检测到 backend 容器，且当前环境缺少 Python 依赖（如 sqlalchemy）。

请使用以下命令之一：

  cd /opt/you-where-backend
  sudo docker compose exec backend python scripts/apply_schema_updates.py

或：

  sudo sh scripts/apply_schema.sh

说明：容器启动时 entrypoint 已自动执行 schema 同步；手动执行用于发版后确认增量索引/列。
EOF
exit 1
