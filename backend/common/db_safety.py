# -*- coding: utf-8 -*-
"""
数据库安全：标识符白名单、LIKE 转义、破坏性操作防护、结构同步校验。

业务代码应优先使用 SQLAlchemy ORM / Core（参数绑定），避免拼接用户输入到 SQL 文本。
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from common.config import settings

# 仅允许字母数字下划线，且不以数字开头（MySQL 未加引号标识符规则）
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

# 显式禁止出现在动态 DDL/DML 文本中的关键字（额外防御）
_FORBIDDEN_SQL_FRAGMENTS = re.compile(
    r"\b(DROP\s+DATABASE|DROP\s+TABLE|TRUNCATE|;\s*DROP|;\s*DELETE\s+FROM\s+\w+\s*;)\b",
    re.IGNORECASE,
)


def allowed_table_names() -> Set[str]:
    from common.models import Base

    return {t.name for t in Base.metadata.sorted_tables}


def assert_safe_identifier(name: str, *, kind: str = "identifier") -> str:
    """校验表名/列名等标识符，防止 SQL 注入拼接。"""
    value = (name or "").strip()
    if not value or not _IDENTIFIER_RE.match(value):
        raise ValueError(f"非法 SQL {kind}: {name!r}")
    return value


def assert_safe_table_name(table: str) -> str:
    safe = assert_safe_identifier(table, kind="表名")
    if safe not in allowed_table_names():
        raise ValueError(f"表名不在模型白名单内: {safe}")
    return safe


def assert_static_ddl_sql(sql: str) -> str:
    """仅用于仓库内写死的 DDL 字符串二次检查。"""
    normalized = " ".join((sql or "").split())
    if _FORBIDDEN_SQL_FRAGMENTS.search(normalized):
        raise ValueError(f"DDL 含禁止片段: {sql[:120]!r}")
    return sql


def escape_like_pattern(raw: str, *, escape_char: str = "\\") -> str:
    """
    转义 LIKE 通配符，供 SQLAlchemy .like(pattern, escape=...) 使用。
    用户搜索词中的 % _ 不再被当作通配符。
    """
    if not raw:
        return ""
    out = []
    for ch in raw:
        if ch in ("%", "_", escape_char):
            out.append(escape_char)
        out.append(ch)
    return "".join(out)


def is_destructive_db_allowed() -> bool:
    """
    是否允许整表清空等破坏性操作。
    生产库默认禁止；测试库或显式 ALLOW_DESTRUCTIVE_DB=1 时允许。
    """
    import os

    if os.getenv("ALLOW_DESTRUCTIVE_DB", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    if settings.DB_BACKEND == "sqlite":
        path = (settings.SQLITE_DB_PATH or "").lower()
        return "test" in path or ":memory:" in path
    db_name = (settings.MYSQL_DB or "").lower()
    if db_name in ("you_where_test", "youzainaye_test"):
        return True
    if "test" in db_name:
        return True
    return False


def assert_destructive_db_allowed(action: str) -> None:
    if not is_destructive_db_allowed():
        raise RuntimeError(
            f"禁止在生产库执行破坏性操作: {action}。"
            f"当前库={settings.MYSQL_DB if settings.DB_BACKEND == 'mysql' else settings.SQLITE_DB_PATH}。"
            "仅测试库可清空，或设置 ALLOW_DESTRUCTIVE_DB=1（慎用）。"
        )


def verify_schema_matches_models(engine: Engine) -> Tuple[bool, List[str]]:
    """
    对比 ORM 模型与数据库实际表结构，用于 apply_schema 后确认同步。
    返回 (是否通过, 问题列表)。
    """
    from common.models import Base

    issues: List[str] = []
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        name = table.name
        if name not in existing:
            issues.append(f"缺少表: {name}")
            continue
        db_cols = {c["name"] for c in inspector.get_columns(name)}
        model_cols = {c.name for c in table.columns}
        missing = model_cols - db_cols
        if missing:
            issues.append(f"表 {name} 缺少列: {sorted(missing)}")

    return (len(issues) == 0, issues)


def log_schema_sync_status(engine: Engine) -> None:
    ok, issues = verify_schema_matches_models(engine)
    if ok:
        print("Schema sync check: OK（模型与数据库表结构一致）")
    else:
        print("Schema sync check: 存在差异（请执行 apply_schema_updates 或 mysql_init.sql）")
        for item in issues:
            print(f"  - {item}")
