#!/usr/bin/env bash
# 分阶段 k6 压测（需本机安装 k6，且 API 已启动）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LT="$ROOT/scripts/loadtest"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000/api/v2}"

run_phase() {
  local name="$1"
  shift
  echo "==== k6 $name ===="
  k6 run "$@" || { echo "k6 $name 失败"; exit 1; }
}

run_phase "phase1_auth" "$LT/phase1_auth.js" -e "BASE_URL=$BASE_URL"

if [ -z "${TOKEN:-}" ]; then
  echo "提示：phase2-5 需预先登录并 export TOKEN / TOKEN_A / TOKEN_B / BOOK_ID / CATALOG_ID"
  exit 0
fi

run_phase "phase2_pair" "$LT/phase2_pair.js" -e "BASE_URL=$BASE_URL" -e "TOKEN_A=${TOKEN_A:-$TOKEN}" -e "TOKEN_B=${TOKEN_B:-$TOKEN}"
run_phase "phase3_reading" "$LT/phase3_reading.js" -e "BASE_URL=$BASE_URL" -e "TOKEN=$TOKEN" -e "BOOK_ID=${BOOK_ID:-}"
run_phase "phase4_store" "$LT/phase4_store.js" -e "BASE_URL=$BASE_URL" -e "TOKEN=$TOKEN" -e "CATALOG_ID=${CATALOG_ID:-gutendex_1}"
run_phase "phase5_settings" "$LT/phase5_settings.js" -e "BASE_URL=$BASE_URL" -e "TOKEN=$TOKEN"

echo "全部 k6 阶段完成"
