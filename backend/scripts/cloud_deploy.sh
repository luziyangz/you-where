#!/bin/sh
set -eu

APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
HTTP_PORT="${HTTP_PORT:-18080}"
SERVER_IP="${SERVER_IP:-47.99.240.126}"
CONFIGURE_DOCKER_MIRRORS="${CONFIGURE_DOCKER_MIRRORS:-1}"

cd "$APP_DIR"

log() {
  printf '\n[deploy] %s\n' "$1"
}

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "Please run with sudo or root: sudo sh scripts/cloud_deploy.sh"
    exit 1
  fi
}

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 16
    return
  fi
  date +%s%N | sha256sum | awk '{print substr($1,1,32)}'
}

install_base_tools() {
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y ca-certificates curl tar openssl
    return
  fi

  if command -v yum >/dev/null 2>&1; then
    yum install -y ca-certificates curl tar openssl
    return
  fi
}

install_docker_if_needed() {
  if command -v docker >/dev/null 2>&1; then
    log "Docker already installed"
    return
  fi

  log "Installing Docker with Aliyun mirror"
  curl -fsSL https://get.docker.com | sh -s docker --mirror Aliyun
  systemctl enable docker
  systemctl start docker
}

configure_docker_mirrors() {
  if [ "$CONFIGURE_DOCKER_MIRRORS" = "0" ]; then
    log "Skipping Docker registry mirror configuration"
    return
  fi

  log "Configuring Docker registry mirrors"
  mkdir -p /etc/docker
  if [ -f /etc/docker/daemon.json ] && [ ! -f /etc/docker/daemon.json.bak-you-where ]; then
    cp /etc/docker/daemon.json /etc/docker/daemon.json.bak-you-where
  fi
  cat >/etc/docker/daemon.json <<'JSON'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  }
}
JSON
  systemctl daemon-reload || true
  systemctl restart docker
}

install_compose_if_needed() {
  if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
    log "Docker Compose already available"
    return
  fi

  log "Installing Docker Compose plugin"
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y docker-compose-plugin || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y docker-compose-plugin || true
  fi
}

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  echo "Docker Compose is not available. Install docker compose plugin first." >&2
  exit 1
}

ensure_env_file() {
  if [ -f .env ]; then
    log ".env exists, keep current configuration"
    return
  fi

  log "Creating .env with generated MySQL passwords"
  ROOT_PASSWORD="$(random_secret)"
  APP_PASSWORD="$(random_secret)"
  cat >.env <<EOF
DB_BACKEND=mysql
MYSQL_ROOT_PASSWORD=${ROOT_PASSWORD}
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=you_where
MYSQL_PASSWORD=${APP_PASSWORD}
MYSQL_DB=you_where
MYSQL_POOL_SIZE=10
MYSQL_MAX_OVERFLOW=20
HTTP_PORT=${HTTP_PORT}
HTTPS_PORT=18443
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
WECHAT_APP_ID=
WECHAT_APP_SECRET=
WECHAT_REMINDER_TEMPLATE_ID=
STORE_ENABLE_NETWORK=0
ENABLE_TEST_USERS=0
SEED_TEST_USERS=0
EOF
  chmod 600 .env
}

prepare_dirs() {
  mkdir -p nginx/certs nginx/logs
}

deploy_stack() {
  log "Building and starting Docker stack"
  compose pull --ignore-pull-failures || true
  compose up -d --build
}

verify_health() {
  log "Verifying local health endpoint"
  for i in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${HTTP_PORT}/health" >/dev/null 2>&1; then
      echo "Local OK: http://127.0.0.1:${HTTP_PORT}/health"
      echo "Public URL: http://${SERVER_IP}:${HTTP_PORT}/health"
      echo "API base URL: http://${SERVER_IP}:${HTTP_PORT}/api/v2"
      break
    fi
    sleep 2
  done

  if ! curl -fsS "http://127.0.0.1:${HTTP_PORT}/health" >/dev/null 2>&1; then
    echo "Local health check failed. Container status:" >&2
    compose ps >&2 || true
    exit 1
  fi

  log "Checking public endpoint from this server"
  if curl -fsS --connect-timeout 5 "http://${SERVER_IP}:${HTTP_PORT}/health" >/dev/null 2>&1; then
    echo "Public self-check OK: http://${SERVER_IP}:${HTTP_PORT}/health"
    return
  fi

  echo "WARN: local health is OK, but public self-check failed." >&2
  echo "WARN: check Alibaba Cloud security group and OS firewall for TCP ${HTTP_PORT}." >&2
  echo "WARN: some cloud networks do not support visiting the instance public IP from itself; verify from an external client too." >&2
  compose ps >&2 || true
}

need_root
install_base_tools
install_docker_if_needed
configure_docker_mirrors
install_compose_if_needed
ensure_env_file
prepare_dirs
deploy_stack
verify_health
