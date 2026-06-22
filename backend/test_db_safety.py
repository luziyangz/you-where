# -*- coding: utf-8 -*-
"""数据库安全工具单元测试。"""

import os
import tempfile

import pytest

os.environ.setdefault("DB_BACKEND", "sqlite")
os.environ.setdefault("SQLITE_DB_PATH", os.path.join(tempfile.mkdtemp(), "db_safety_test.db"))

from common.db_safety import (  # noqa: E402
    assert_safe_identifier,
    assert_safe_table_name,
    escape_like_pattern,
    is_destructive_db_allowed,
)


def test_escape_like_pattern():
    assert escape_like_pattern("100%") == "100\\%"
    assert escape_like_pattern("a_b") == "a\\_b"


def test_assert_safe_identifier_rejects_injection():
    with pytest.raises(ValueError):
        assert_safe_identifier("users; DROP TABLE users")
    with pytest.raises(ValueError):
        assert_safe_identifier("")


def test_assert_safe_table_name_whitelist():
    assert assert_safe_table_name("users") == "users"
    with pytest.raises(ValueError):
        assert_safe_table_name("not_a_real_table_xyz")


def test_sqlite_test_path_allows_destructive():
    assert is_destructive_db_allowed() is True
