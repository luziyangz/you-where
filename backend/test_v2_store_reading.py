# -*- coding: utf-8 -*-
"""
v2 书城与阅读主流程测试
运行方式：
    cd backend
    pytest test_v2_store_reading.py -v
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


_tmpdir = tempfile.mkdtemp()
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = os.path.join(_tmpdir, "v2_store_reading.db")

from app_main import app as fastapi_app  # noqa: E402
from common.db import SessionLocal  # noqa: E402
from common.models import CatalogBook, CatalogContent, Pair, SessionModel, User  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@pytest.fixture(scope="session")
def client():
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture(scope="function")
def seeded_token():
    db = SessionLocal()
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
        token="tok_store_v2",
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
        content_text="甲" * 1200 + "乙" * 1200,
        content_len=2400,
        page_size_chars=1200,
        total_pages=2,
        etag=None,
        last_fetched_at=now,
    )
    db.add_all([ua, ub, sess, pair, cbook, ccontent])
    db.commit()
    db.close()
    return "tok_store_v2"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_store_list_and_read(client, seeded_token):
    resp = client.get("/api/v2/store/books")
    assert resp.status_code == 200
    assert len(resp.json()["data"]["books"]) >= 1

    detail = client.get("/api/v2/store/books/gutendex_1")
    assert detail.status_code == 200
    assert detail.json()["data"]["book"]["catalog_id"] == "gutendex_1"

    read1 = client.get("/api/v2/store/books/gutendex_1/read?page=1")
    assert read1.status_code == 200
    assert read1.json()["data"]["total_pages"] == 2


def test_create_book_current_and_entry(client, seeded_token):
    created = client.post("/api/v2/books", json={"catalog_id": "gutendex_1"}, headers=_auth(seeded_token))
    assert created.status_code == 200
    book_id = created.json()["data"]["book_id"]

    current = client.get("/api/v2/books/current", headers=_auth(seeded_token))
    assert current.status_code == 200
    assert current.json()["data"]["book"]["book_id"] == book_id

    entry = client.post(
        "/api/v2/entries",
        json={"book_id": book_id, "page": 1, "note_content": "", "client_request_id": "req1"},
        headers=_auth(seeded_token),
    )
    assert entry.status_code == 200
    assert entry.json()["data"]["my_progress"] == 1

    # 相同 client_request_id 重放不应生成重复记录（幂等）
    duplicated = client.post(
        "/api/v2/entries",
        json={"book_id": book_id, "page": 1, "note_content": "重复提交", "client_request_id": "req1"},
        headers=_auth(seeded_token),
    )
    assert duplicated.status_code == 200

    entries = client.get(f"/api/v2/books/{book_id}/entries?page=1&page_size=10", headers=_auth(seeded_token))
    assert entries.status_code == 200
    payload = entries.json()["data"]
    assert payload["pagination"]["total"] == 1
    assert len(payload["entries"]) == 1
