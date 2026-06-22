# -*- coding: utf-8 -*-
"""诊断 MySQL 集成测试环境（不修改数据）。"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DEFAULTS = {
    "MYSQL_HOST": "127.0.0.1",
    "MYSQL_PORT": "3307",
    "MYSQL_USER": "you_where_test",
    "MYSQL_PASSWORD": "test_app_pw",
    "MYSQL_DB": "you_where_test",
}


def _apply_test_env() -> None:
    os.environ["DB_BACKEND"] = "mysql"
    os.environ["MYSQL_HOST"] = os.getenv("MYSQL_TEST_HOST", _TEST_DEFAULTS["MYSQL_HOST"])
    os.environ["MYSQL_PORT"] = os.getenv("MYSQL_TEST_PORT", _TEST_DEFAULTS["MYSQL_PORT"])
    os.environ["MYSQL_USER"] = os.getenv("MYSQL_TEST_USER", _TEST_DEFAULTS["MYSQL_USER"])
    os.environ["MYSQL_PASSWORD"] = os.getenv(
        "MYSQL_TEST_PASSWORD", _TEST_DEFAULTS["MYSQL_PASSWORD"]
    )
    os.environ["MYSQL_DB"] = os.getenv("MYSQL_TEST_DB", _TEST_DEFAULTS["MYSQL_DB"])
    for mod in ("common.config", "common.db"):
        sys.modules.pop(mod, None)


_apply_test_env()


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


def _docker_daemon_ok() -> bool:
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    host = os.environ["MYSQL_HOST"]
    port = int(os.environ["MYSQL_PORT"])
    user = os.environ["MYSQL_USER"]
    db = os.environ["MYSQL_DB"]
    print("=== MySQL 集成测试环境诊断 ===")
    print(f"目标: {user}@{host}:{port}/{db}")
    print("(已强制使用测试库凭据，忽略 backend/.env 中的 root@3306)")
    print()

    docker_ok = _docker_daemon_ok()
    print(f"[Docker 守护进程] {'正常' if docker_ok else '不可用'}")
    if not docker_ok:
        print("  → 请先启动 Docker Desktop，再执行:")
        print("     docker compose -f docker-compose.test.yml up -d")
    print()

    port_ok = _port_open(host, port)
    print(f"[TCP {host}:{port}] {'可连接' if port_ok else '不可连接'}")
    print()

    if not port_ok:
        print("结论: 无法跑 tests_mysql/（用例会 skip）。")
        return 1

    try:
        from sqlalchemy import create_engine, text

        from common.config import settings

        print(f"[连接串] {settings.MYSQL_USER}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}")
        eng = create_engine(settings.mysql_url, pool_pre_ping=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        print("[MySQL 登录] 成功")
        print("结论: 可执行  python -m pytest tests_mysql/ -v")
        return 0
    except Exception as exc:
        print(f"[MySQL 登录] 失败: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
