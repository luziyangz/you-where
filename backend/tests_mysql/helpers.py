# -*- coding: utf-8 -*-
"""MySQL 集成测试共用辅助函数（延迟导入 SessionLocal，避免缓存错误 engine）。"""

from __future__ import annotations

from datetime import datetime, timezone

from common.db_safety import assert_destructive_db_allowed


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _session():
    from common.db import SessionLocal

    return SessionLocal()


def login(client, open_id: str, nickname: str = "测试"):
    resp = client.post(
        "/api/v2/auth/login",
        json={"code": "test", "debug_open_id": open_id, "nickname": nickname},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    return data["token"], data["user"]


def assert_table_has_row(model, **filters):
    db = _session()
    try:
        q = db.query(model)
        for key, val in filters.items():
            q = q.filter(getattr(model, key) == val)
        assert q.first() is not None, f"{model.__tablename__} 缺少记录: {filters}"
    finally:
        db.close()


def approve_pair_bind(client, auth_header, token_requester: str, token_target: str, join_code: str) -> str:
    """发起绑定并由对方同意，返回 pair_id。"""
    bind = client.post(
        "/api/v2/pairs",
        json={"join_code": join_code},
        headers=auth_header(token_requester),
    )
    assert bind.status_code == 200, bind.text
    body = bind.json()["data"]
    if body.get("mode") == "pair_request":
        req_id = body["pair_request"]["request_id"]
        approved = client.post(
            f"/api/v2/pairs/requests/{req_id}/respond",
            json={"action": "approve"},
            headers=auth_header(token_target),
        )
        assert approved.status_code == 200, approved.text
        pair = approved.json()["data"].get("pair") or {}
        return pair["pair_id"]
    return body["pair_id"]


def approve_unbind(client, auth_header, token_requester: str, token_target: str) -> None:
    """发起解绑并由对方同意。"""
    unbind = client.delete("/api/v2/pairs/current", headers=auth_header(token_requester))
    assert unbind.status_code == 200, unbind.text
    body = unbind.json()["data"]
    if body.get("mode") == "pair_request":
        req_id = body["pair_request"]["request_id"]
        approved = client.post(
            f"/api/v2/pairs/requests/{req_id}/respond",
            json={"action": "approve"},
            headers=auth_header(token_target),
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["data"]["status"] == "unbound"
    else:
        assert body.get("status") == "unbound"


def create_book_with_partner_approval(client, auth_header, token_a: str, token_b: str, payload: dict) -> dict:
    """加入共读须伙伴同意。"""
    created = client.post("/api/v2/books", json=payload, headers=auth_header(token_a))
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    if body.get("mode") == "switch_request":
        req_id = body["switch_request"]["request_id"]
        approved = client.post(
            f"/api/v2/pairs/current/book-switch-requests/{req_id}/respond",
            json={"action": "approve"},
            headers=auth_header(token_b),
        )
        assert approved.status_code == 200, approved.text
        return approved.json()["data"]["book"]
    if body.get("mode") == "book":
        return body["book"]
    return body


def bind_pair(client, auth_header, open_id_a: str, open_id_b: str):
    """登录两名用户并绑定 pair（须对方同意），返回 token 与 user 字典。"""
    token_a, user_a = login(client, open_id_a, "甲")
    token_b, user_b = login(client, open_id_b, "乙")
    pair_id = approve_pair_bind(client, auth_header, token_b, token_a, user_a["join_code"])
    return token_a, token_b, user_a, user_b, pair_id


def seed_catalog_gutendex(db):
    """确保书城有一条可读的公版书。"""
    from common.models import CatalogBook, CatalogContent

    if db.query(CatalogBook).filter(CatalogBook.catalog_id == "gutendex_1").first():
        return
    now = utc_now()
    db.add(
        CatalogBook(
            catalog_id="gutendex_1",
            source="gutendex",
            source_book_id="1",
            title="测试公版书",
            author="Test",
            language="en",
            cover_url="",
            detail_url="",
            text_url="https://example.com/1.txt",
            store_category="fiction",
            created_at=now,
            updated_at=now,
        )
    )
    db.add(
        CatalogContent(
            catalog_id="gutendex_1",
            content_text="第一章\n\n" + ("正文内容。" * 200),
            content_len=1200,
            page_size_chars=600,
            total_pages=2,
            etag=None,
            last_fetched_at=now,
        )
    )
    db.commit()


def _require_test_db_wipe() -> None:
    assert_destructive_db_allowed("tests_mysql 清空业务表")


def _delete_all(model) -> None:
    _require_test_db_wipe()
    db = _session()
    try:
        db.query(model).delete()
        db.commit()
    finally:
        db.close()


def wipe_reading_tables_only():
    _require_test_db_wipe()
    from common.models import (
        ActiveBookLock,
        ActivePairLock,
        Book,
        BookReadProgress,
        BookSwitchRequest,
        Entry,
        Pair,
        PairBlock,
        PairRequest,
        ReadMark,
        Reply,
        SessionModel,
        UgcReport,
        User,
    )

    db = _session()
    try:
        for model in (
            Reply,
            Entry,
            ReadMark,
            BookReadProgress,
            ActiveBookLock,
            BookSwitchRequest,
            PairRequest,
            PairBlock,
            Book,
            ActivePairLock,
            Pair,
            SessionModel,
            User,
        ):
            db.query(model).delete()
        db.commit()
    finally:
        db.close()


def wipe_business_tables():
    _require_test_db_wipe()
    from common.models import (
        ActiveBookLock,
        ActivePairLock,
        Book,
        BookReadProgress,
        BookSwitchRequest,
        CatalogBook,
        CatalogContent,
        CatalogFavorite,
        CatalogReaderMark,
        CatalogReadProgress,
        Entry,
        FeedComment,
        FeedPost,
        Pair,
        PairBlock,
        PairRequest,
        ReadMark,
        ReadingGoal,
        ReminderConfig,
        ReminderDeliveryLog,
        Reply,
        SessionModel,
        User,
    )

    db = _session()
    try:
        for model in (
            FeedComment,
            FeedPost,
            UgcReport,
            BookReadProgress,
            ReminderDeliveryLog,
            ReminderConfig,
            ReadingGoal,
            CatalogReaderMark,
            CatalogFavorite,
            CatalogReadProgress,
            CatalogContent,
            CatalogBook,
            Reply,
            ReadMark,
            Entry,
            ActiveBookLock,
            BookSwitchRequest,
            PairRequest,
            PairBlock,
            Book,
            ActivePairLock,
            Pair,
            SessionModel,
            User,
        ):
            db.query(model).delete()
        db.commit()
    finally:
        db.close()
