# -*- coding: utf-8 -*-
"""
v2 端到端主流程测试：首页 -> 伙伴 -> 进度 -> 回复
"""

import os
import tempfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


_tmpdir = tempfile.mkdtemp()
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = os.path.join(_tmpdir, "v2_e2e.db")

from app_main import app as fastapi_app  # noqa: E402
from common.db import SessionLocal  # noqa: E402
from common.models import CatalogBook, CatalogContent  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@pytest.fixture(scope="session")
def client():
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture(scope="function")
def seed_catalog():
    db = SessionLocal()
    db.query(CatalogContent).delete()
    db.query(CatalogBook).delete()
    db.commit()
    now = _utc_now()
    db.add(
        CatalogBook(
            catalog_id="gutendex_e2e",
            source="gutendex",
            source_book_id="e2e",
            title="E2E 书",
            author="作者",
            language="zh",
            cover_url="",
            detail_url="https://example.com",
            text_url="https://example.com/text",
            created_at=now,
            updated_at=now,
        )
    )
    db.add(
        CatalogContent(
            catalog_id="gutendex_e2e",
            content_text="甲" * 2400,
            content_len=2400,
            page_size_chars=1200,
            total_pages=2,
            etag=None,
            last_fetched_at=now,
        )
    )
    db.commit()
    db.close()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, open_id: str) -> tuple[str, dict]:
    res = client.post("/api/v2/auth/login", json={"code": "x", "debug_open_id": open_id})
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    return data["token"], data["user"]


def test_e2e_home_partner_progress_reply(client, seed_catalog):
    ta, ua = _login(client, "open_e2e_a")
    tb, _ = _login(client, "open_e2e_b")

    # 伙伴绑定
    bind = client.post("/api/v2/pair/bind", json={"join_code": ua["join_code"]}, headers=_auth(tb))
    assert bind.status_code == 200, bind.text

    # 首页聚合可用
    home = client.get("/api/v2/home", headers=_auth(ta))
    assert home.status_code == 200
    assert home.json()["data"]["pair"] is not None

    # 添加共读书（书城来源）
    create_book = client.post("/api/v2/books", json={"catalog_id": "gutendex_e2e"}, headers=_auth(ta))
    assert create_book.status_code == 200, create_book.text
    book_id = create_book.json()["data"]["book_id"]

    # 双方记录进度，a 写笔记，b 回复
    e1 = client.post(
        "/api/v2/entries",
        json={"book_id": book_id, "page": 1, "note_content": "第一条"},
        headers=_auth(ta),
    )
    assert e1.status_code == 200, e1.text

    e2 = client.post(
        "/api/v2/entries",
        json={"book_id": book_id, "page": 1, "note_content": ""},
        headers=_auth(tb),
    )
    assert e2.status_code == 200, e2.text

    entries = client.get(f"/api/v2/books/{book_id}/entries?page=1&page_size=1", headers=_auth(tb))
    assert entries.status_code == 200, entries.text
    data = entries.json()["data"]
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["page_size"] == 1
    assert data["pagination"]["total"] >= 2
    assert data["pagination"]["has_more"] is True
    entry_rows = data["entries"]
    assert len(entry_rows) == 1

    entries_page2 = client.get(f"/api/v2/books/{book_id}/entries?page=2&page_size=1", headers=_auth(tb))
    assert entries_page2.status_code == 200, entries_page2.text
    page2_data = entries_page2.json()["data"]
    assert page2_data["pagination"]["page"] == 2
    assert len(page2_data["entries"]) == 1
    all_rows = entry_rows + page2_data["entries"]
    target = next(item for item in all_rows if not item["is_mine"])

    reply = client.post(
        f"/api/v2/entries/{target['entry_id']}/replies",
        json={"content": "收到"},
        headers=_auth(tb),
    )
    assert reply.status_code == 200, reply.text

    # 已读标记可写入
    mark = client.post(
        f"/api/v2/books/{book_id}/entries/read",
        json={"last_entry_id": target["entry_id"]},
        headers=_auth(tb),
    )
    assert mark.status_code == 200, mark.text
