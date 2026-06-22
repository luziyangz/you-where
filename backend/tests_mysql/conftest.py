# -*- coding: utf-8 -*-
"""
MySQL 集成测试：强制使用测试库凭据，避免 backend/.env 中生产 MYSQL_* 污染。

运行：
  pytest tests_mysql/ -v
  scripts/run_mysql_regression.ps1
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_SKIP_REASON = (
    "MySQL 测试库不可用（{user}@{host}:{port}/{db}）。"
    "请启动: docker compose -f docker-compose.test.yml up -d "
    "或设置 MYSQL_TEST_HOST 等。诊断: python scripts/check_mysql_test_env.py"
)

# 与 docker-compose.test.yml 一致
_TEST_DEFAULTS = {
    "MYSQL_HOST": "127.0.0.1",
    "MYSQL_PORT": "3307",
    "MYSQL_USER": "you_where_test",
    "MYSQL_PASSWORD": "test_app_pw",
    "MYSQL_DB": "you_where_test",
}


def _reload_db_stack() -> None:
    """重建 common.config / common.db，使 engine 使用最新环境变量。"""
    for mod_name in (
        "app_main",
        "common.db",
        "common.config",
    ):
        sys.modules.pop(mod_name, None)


def _apply_mysql_test_env() -> None:
    """强制覆盖 MYSQL_*（不用 setdefault，避免 .env / shell 里的 root@3306）。"""
    os.environ["DB_BACKEND"] = "mysql"
    os.environ["MYSQL_HOST"] = os.getenv("MYSQL_TEST_HOST", _TEST_DEFAULTS["MYSQL_HOST"])
    os.environ["MYSQL_PORT"] = os.getenv("MYSQL_TEST_PORT", _TEST_DEFAULTS["MYSQL_PORT"])
    os.environ["MYSQL_USER"] = os.getenv("MYSQL_TEST_USER", _TEST_DEFAULTS["MYSQL_USER"])
    os.environ["MYSQL_PASSWORD"] = os.getenv(
        "MYSQL_TEST_PASSWORD", _TEST_DEFAULTS["MYSQL_PASSWORD"]
    )
    os.environ["MYSQL_DB"] = os.getenv("MYSQL_TEST_DB", _TEST_DEFAULTS["MYSQL_DB"])
    os.environ["ENABLE_TEST_USERS"] = "1"
    os.environ["SEED_TEST_USERS"] = "0"
    _reload_db_stack()


def _settings():
    _apply_mysql_test_env()
    from common.config import settings

    return settings


def _mysql_reachable() -> bool:
    from sqlalchemy import create_engine, text

    settings = _settings()
    try:
        eng = create_engine(settings.mysql_url, pool_pre_ping=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def _mysql_test_session_env():
    """整个 tests_mysql 会话开始前锁定测试库连接。"""
    _apply_mysql_test_env()
    yield


@pytest.fixture(scope="session", autouse=True)
def _mysql_schema_ready(_mysql_test_session_env):
    """MySQL 可达时先建表/增量补丁，避免 phase0 在 app_client 之前缺表。"""
    if not _mysql_reachable():
        return
    from scripts.apply_schema_updates import main as apply_schema

    apply_schema()


@pytest.fixture(scope="session", autouse=True)
def _mysql_schema_ready(_mysql_test_session_env):
    """MySQL 可用时先建表/补列，避免 phase0 在 app_client 之前检查缺表。"""
    if not _mysql_reachable():
        return
    from scripts.apply_schema_updates import main as apply_schema

    apply_schema()


@pytest.fixture(scope="session", autouse=True)
def _mysql_schema_ready(_mysql_test_session_env):
    """MySQL 可达时先建表/增量补丁，避免 phase0 在 app_client 之前检查缺表。"""
    if not _mysql_reachable():
        return
    from scripts.apply_schema_updates import main as apply_schema

    apply_schema()


@pytest.fixture(scope="session")
def mysql_available():
    s = _settings()
    if not _mysql_reachable():
        pytest.skip(
            _SKIP_REASON.format(
                user=s.MYSQL_USER,
                host=s.MYSQL_HOST,
                port=s.MYSQL_PORT,
                db=s.MYSQL_DB,
            )
        )
    return s


@pytest.fixture(scope="session")
def app_client(mysql_available):
    """Session 级 TestClient，建表并清空业务表。"""
    from scripts.apply_schema_updates import main as apply_schema

    apply_schema()

    from app_main import app as fastapi_app
    from fastapi.testclient import TestClient

    with TestClient(fastapi_app) as client:
        yield client


@pytest.fixture(scope="function")
def clean_reading_tables(mysql_available):
    from tests_mysql.helpers import wipe_reading_tables_only

    wipe_reading_tables_only()
    yield


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_header():
    return _auth


# pytest 收集用例前锁定测试库凭据（早于各 test_*.py 的 import）
_apply_mysql_test_env()
