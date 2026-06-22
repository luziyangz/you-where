# -*- coding: utf-8 -*-
"""阶段0：MySQL 连通与 22 张业务表存在。"""

from sqlalchemy import inspect

from common.models import Base

EXPECTED_TABLES = sorted(
    table.name for table in Base.metadata.sorted_tables
)


def test_mysql_has_all_model_tables(mysql_available):
    from common.db import engine

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = [t for t in EXPECTED_TABLES if t not in existing]
    assert not missing, f"MySQL 缺少表: {missing}"
    assert len(EXPECTED_TABLES) == 22
