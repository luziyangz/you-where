# -*- coding: utf-8 -*-
"""分享摘录 API 测试（非社交：仅我的分享 + 单条查看 + 微信转发数据源）。"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest


def _reload_db_stack() -> None:
    for mod_name in ("app_main", "common.db", "common.config"):
        sys.modules.pop(mod_name, None)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def feed_client():
    """独立 SQLite 环境，避免污染 tests_mysql。"""
    tmpdir = tempfile.mkdtemp()
    os.environ["DB_BACKEND"] = "sqlite"
    os.environ["SQLITE_DB_PATH"] = os.path.join(tmpdir, "v2_feed_test.db")
    _reload_db_stack()

    from fastapi.testclient import TestClient
    from app_main import app as fastapi_app

    with TestClient(fastapi_app) as client:
        yield client


@pytest.fixture(scope="function")
def seeded_token(feed_client):
    from common.db import SessionLocal
    from common.models import (
        ActiveBookLock,
        ActivePairLock,
        Book,
        BookSwitchRequest,
        CatalogBook,
        CatalogContent,
        Entry,
        FeedComment,
        FeedPost,
        Pair,
        SessionModel,
        User,
    )
    from service import store_service

    store_service._gutendex_failure_count = 0
    store_service._gutendex_block_until = 0

    db = SessionLocal()
    db.query(FeedComment).delete()
    db.query(FeedPost).delete()
    db.query(Entry).delete()
    db.query(BookSwitchRequest).delete()
    db.query(ActiveBookLock).delete()
    db.query(ActivePairLock).delete()
    db.query(Book).delete()
    db.query(CatalogContent).delete()
    db.query(CatalogBook).delete()
    db.query(Pair).delete()
    db.query(SessionModel).delete()
    db.query(User).delete()
    db.commit()

    now = _utc_now()
    ua = User(user_id="u_a", open_id="oa", nickname="A", avatar="", join_code="111111", created_at=now)
    ub = User(user_id="u_b", open_id="ob", nickname="B", avatar="", join_code="222222", created_at=now)
    sess = SessionModel(
        token="tok_feed_v2",
        user_id="u_a",
        created_at=now,
        expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    pair = Pair(pair_id="p_1", user_a_id="u_a", user_b_id="u_b", status="active", created_at=now, updated_at=now)
    cbook = CatalogBook(
        catalog_id="gutendex_1",
        source="gutendex",
        source_book_id="1",
        title="测试公版书",
        author="测试作者",
        language="zh",
        cover_url="",
        detail_url="https://example.com",
        text_url="https://example.com/text",
        created_at=now,
        updated_at=now,
    )
    ccontent = CatalogContent(
        catalog_id="gutendex_1",
        content_text="甲" * 1200,
        content_len=1200,
        page_size_chars=1200,
        total_pages=1,
        etag=None,
        last_fetched_at=now,
    )
    db.add_all([ua, ub, sess, pair, cbook, ccontent])
    db.commit()
    db.close()
    yield "tok_feed_v2"


def _create_book_and_entry(client, token):
    created = client.post("/api/v2/books", json={"catalog_id": "gutendex_1"}, headers=_auth(token))
    assert created.status_code == 200
    book_id = created.json()["data"]["book_id"]
    entry_resp = client.post(
        f"/api/v2/books/{book_id}/entries",
        headers=_auth(token),
        json={"page": 1, "note_content": "这一页让我想到彼此陪伴", "mark_finished": False},
    )
    assert entry_resp.status_code == 200
    listed = client.get(f"/api/v2/books/{book_id}/entries?page=1&page_size=10", headers=_auth(token))
    entry_id = listed.json()["data"]["entries"][0]["entry_id"]
    return book_id, entry_id


def test_share_publish_mine_and_view(feed_client, seeded_token):
    book_id, entry_id = _create_book_and_entry(feed_client, seeded_token)

    other = feed_client.post("/api/v2/auth/login", json={"code": "x", "debug_open_id": "ob"})
    assert other.status_code == 200
    token_b = other.json()["data"]["token"]

    publish = feed_client.post(
        f"/api/v2/entries/{entry_id}/publish-to-feed",
        headers=_auth(seeded_token),
        json={"excerpt": "这一页让我想到彼此陪伴", "confirm": True},
    )
    assert publish.status_code == 200
    post_id = publish.json()["data"]["post_id"]
    assert publish.json()["data"]["share_title"]

    mine = feed_client.get("/api/v2/feed/posts/mine", headers=_auth(seeded_token))
    assert mine.status_code == 200
    assert len(mine.json()["data"]["posts"]) == 1

    other_mine = feed_client.get("/api/v2/feed/posts/mine", headers=_auth(token_b))
    assert other_mine.status_code == 200
    assert other_mine.json()["data"]["posts"] == []

    detail = feed_client.get(f"/api/v2/feed/posts/{post_id}", headers=_auth(token_b))
    assert detail.status_code == 200
    assert detail.json()["data"]["excerpt"] == "这一页让我想到彼此陪伴"

    entries = feed_client.get(f"/api/v2/books/{book_id}/entries", headers=_auth(seeded_token))
    assert entries.json()["data"]["entries"][0]["feed_post_id"] == post_id

    deleted = feed_client.delete(f"/api/v2/feed/posts/{post_id}", headers=_auth(seeded_token))
    assert deleted.status_code == 200

    gone = feed_client.get(f"/api/v2/feed/posts/{post_id}", headers=_auth(token_b))
    assert gone.status_code == 404


def test_explore_excludes_self_and_supports_book_filter(feed_client, seeded_token):
    book_id, entry_id = _create_book_and_entry(feed_client, seeded_token)

    publish = feed_client.post(
        f"/api/v2/entries/{entry_id}/publish-to-feed",
        headers=_auth(seeded_token),
        json={"excerpt": "这一页让我想到彼此陪伴", "confirm": True},
    )
    assert publish.status_code == 200

    self_explore = feed_client.get("/api/v2/feed/posts/explore", headers=_auth(seeded_token))
    assert self_explore.status_code == 200
    assert self_explore.json()["data"]["posts"] == []

    other = feed_client.post("/api/v2/auth/login", json={"code": "x", "debug_open_id": "ob"})
    assert other.status_code == 200
    token_b = other.json()["data"]["token"]

    explore = feed_client.get("/api/v2/feed/posts/explore", headers=_auth(token_b))
    assert explore.status_code == 200
    posts = explore.json()["data"]["posts"]
    assert len(posts) == 1
    assert posts[0]["nickname"] == "A"
    assert posts[0]["book_title"] == "测试公版书"

    filtered = feed_client.get("/api/v2/feed/posts/explore?book=不存在", headers=_auth(token_b))
    assert filtered.status_code == 200
    assert filtered.json()["data"]["posts"] == []

    matched = feed_client.get("/api/v2/feed/posts/explore?book=公版", headers=_auth(token_b))
    assert matched.status_code == 200
    assert len(matched.json()["data"]["posts"]) == 1
