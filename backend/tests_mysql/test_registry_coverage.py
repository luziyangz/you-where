# -*- coding: utf-8 -*-
"""18 张表与阶段测试的映射登记（防漏表）。"""

# 表名 -> 覆盖该表的 tests_mysql 用例
TABLE_COVERAGE = {
    "users": ["test_phase1_account.py", "test_phase1_reader_options.py"],
    "sessions": ["test_phase1_account.py"],
    "pairs": ["test_phase2_pair.py", "test_phase2_unbind.py", "test_phase3_reading.py"],
    "active_pair_locks": ["test_phase2_pair.py", "test_phase2_unbind.py", "test_phase3_reading.py"],
    "books": ["test_phase3_reading.py"],
    "active_book_locks": ["test_phase3_reading.py"],
    "book_read_progress": ["test_phase4_catalog.py"],
    "book_switch_requests": ["test_phase3_reading.py"],
    "entries": ["test_phase3_reading.py"],
    "replies": ["test_phase3_reading.py"],
    "read_marks": ["test_phase3_reading.py"],
    "catalog_books": ["test_phase4_catalog.py", "test_phase4_import.py"],
    "catalog_contents": ["test_phase4_catalog.py", "test_phase4_import.py"],
    "catalog_read_progress": ["test_phase4_catalog.py"],
    "catalog_favorites": ["test_phase4_catalog.py"],
    "catalog_reader_marks": ["test_phase4_catalog.py"],
    "reading_goals": ["test_phase5_settings.py"],
    "reminder_configs": ["test_phase5_settings.py"],
    "reminder_delivery_logs": ["test_phase5_settings.py"],
    "feed_posts": ["test_phase6_feed.py"],
    "feed_comments": ["test_phase6_feed.py"],
    "ugc_reports": ["test_v2_reports.py"],
}


def test_every_model_table_has_mysql_test():
    from common.models import Base

    tables = sorted(t.name for t in Base.metadata.sorted_tables)
    assert len(tables) == 22
    missing = [t for t in tables if t not in TABLE_COVERAGE]
    assert not missing, missing
    empty = [t for t, files in TABLE_COVERAGE.items() if not files]
    assert not empty, empty
