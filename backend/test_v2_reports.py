# -*- coding: utf-8 -*-
"""举报/投诉 API 测试。"""

import os
import sys
import tempfile
from datetime import datetime, timezone

import pytest


def _reload_db_stack() -> None:
    for mod_name in ("app_main", "common.db", "common.config"):
        sys.modules.pop(mod_name, None)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def report_client():
    tmpdir = tempfile.mkdtemp()
    os.environ["DB_BACKEND"] = "sqlite"
    os.environ["SQLITE_DB_PATH"] = os.path.join(tmpdir, "v2_report_test.db")
    _reload_db_stack()

    from fastapi.testclient import TestClient
    from app_main import app as fastapi_app

    with TestClient(fastapi_app) as client:
        yield client


@pytest.fixture(scope="function")
def seeded(report_client):
    from common.db import SessionLocal
    from common.models import (
        Book,
        Entry,
        FeedPost,
        Pair,
        Reply,
        SessionModel,
        UgcReport,
        User,
    )

    db = SessionLocal()
    db.query(UgcReport).delete()
    db.query(Reply).delete()
    db.query(FeedPost).delete()
    db.query(Entry).delete()
    db.query(Book).delete()
    db.query(Pair).delete()
    db.query(SessionModel).delete()
    db.query(User).delete()
    db.commit()

    now = _utc_now()
    ua = User(user_id="u_a", open_id="oa", nickname="A", avatar="", join_code="111111", created_at=now)
    ub = User(user_id="u_b", open_id="ob", nickname="B", avatar="", join_code="222222", created_at=now)
    sess = SessionModel(token="tok_a", user_id="u_a", expires_at="2099-01-01T00:00:00Z", created_at=now)
    pair = Pair(pair_id="p1", user_a_id="u_a", user_b_id="u_b", status="active", created_at=now, updated_at=now)
    book = Book(
        book_id="b1",
        pair_id="p1",
        title="测试书",
        author="作者",
        total_pages=100,
        status="reading",
        created_by="u_a",
        created_at=now,
    )
    entry = Entry(
        entry_id="e1",
        book_id="b1",
        user_id="u_b",
        page=10,
        note_content="伙伴的笔记",
        created_at=now,
    )
    reply = Reply(reply_id="r1", entry_id="e1", user_id="u_b", content="伙伴回复", created_at=now)
    post = FeedPost(
        post_id="fp1",
        user_id="u_b",
        entry_id="e1",
        book_title="测试书",
        excerpt="分享摘录",
        status="published",
        created_at=now,
    )
    db.add_all([ua, ub, sess, pair, book, entry, reply, post])
    db.commit()
    db.close()
    return {"token": "tok_a"}


def test_list_report_reasons(report_client):
    resp = report_client.get("/api/v2/reports/reasons")
    assert resp.status_code == 200
    reasons = resp.json()["data"]["reasons"]
    assert any(item["code"] == "illegal" for item in reasons)


def test_submit_feed_report(report_client, seeded):
    resp = report_client.post(
        "/api/v2/reports",
        headers=_auth(seeded["token"]),
        json={
            "target_type": "feed_post",
            "target_id": "fp1",
            "reason_code": "spam",
            "description": "测试举报",
        },
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["report_id"]
    assert body["status"] == "pending"


def test_cannot_report_self_entry(report_client, seeded):
    from common.db import SessionLocal
    from common.models import Entry

    db = SessionLocal()
    now = _utc_now()
    db.add(
        Entry(
            entry_id="e2",
            book_id="b1",
            user_id="u_a",
            page=11,
            note_content="自己的笔记",
            created_at=now,
        )
    )
    db.commit()
    db.close()

    resp = report_client.post(
        "/api/v2/reports",
        headers=_auth(seeded["token"]),
        json={
            "target_type": "entry",
            "target_id": "e2",
            "reason_code": "other",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40041
