#!/bin/sh
set -eu

SERVER="${SERVER:-47.99.240.126}"
USER_NAME="${USER_NAME:-root}"
SSH_PORT="${SSH_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:-/opt/you-where-backend}"
KEY_PATH="${KEY_PATH:-}"
SKIP_DEPLOY="${SKIP_DEPLOY:-0}"

case "$REMOTE_DIR" in
  /*) ;;
  *) echo "REMOTE_DIR must be an absolute Linux path" >&2; exit 1 ;;
esac
case "$REMOTE_DIR" in
  *[!A-Za-z0-9._/-]*) echo "REMOTE_DIR contains unsupported characters" >&2; exit 1 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_DIR="$BACKEND_DIR/.deploy"
PACKAGE_PATH="$DEPLOY_DIR/you-where-backend.tar.gz"
TARGET="${USER_NAME}@${SERVER}"

mkdir -p "$DEPLOY_DIR"
rm -f "$PACKAGE_PATH"

echo "[sync] Packaging backend from $BACKEND_DIR"
tar -czf "$PACKAGE_PATH" \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='.env.*.local' \
  --exclude='.env.dev' \
  --exclude='.env.development' \
  --exclude='.env.prod' \
  --exclude='.env.production' \
  --exclude='.env.staging' \
  --exclude='.env.test' \
  --exclude='.env.testing' \
  --exclude='.deploy' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='data' \
  --exclude='nginx/logs' \
  -C "$BACKEND_DIR" .

echo "[sync] Uploading package to ${TARGET}:/tmp/you-where-backend.tar.gz"
if [ -n "$KEY_PATH" ]; then
  scp -P "$SSH_PORT" -i "$KEY_PATH" "$PACKAGE_PATH" "${TARGET}:/tmp/you-where-backend.tar.gz"
else
  scp -P "$SSH_PORT" "$PACKAGE_PATH" "${TARGET}:/tmp/you-where-backend.tar.gz"
fi

REMOTE_COMMAND="set -eu; sudo mkdir -p '$REMOTE_DIR'; sudo tar -xzf /tmp/you-where-backend.tar.gz -C '$REMOTE_DIR'; cd '$REMOTE_DIR'"
if [ "$SKIP_DEPLOY" != "1" ]; then
  REMOTE_COMMAND="$REMOTE_COMMAND; sudo sh scripts/cloud_deploy.sh"
fi

echo "[sync] Running remote deploy command"
if [ -n "$KEY_PATH" ]; then
  ssh -p "$SSH_PORT" -i "$KEY_PATH" "$TARGET" "$REMOTE_COMMAND"
else
  ssh -p "$SSH_PORT" "$TARGET" "$REMOTE_COMMAND"
fi

echo "[sync] Finished. Health URL: http://${SERVER}:18080/health"
