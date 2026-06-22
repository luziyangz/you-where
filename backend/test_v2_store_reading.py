# -*- coding: utf-8 -*-
"""
v2 书城与阅读主流程测试
运行方式：
    cd backend
    pytest test_v2_store_reading.py -v
"""

import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from fastapi.testclient import TestClient


_tmpdir = tempfile.mkdtemp()
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = os.path.join(_tmpdir, "v2_store_reading.db")

from app_main import app as fastapi_app  # noqa: E402
from common.db import SessionLocal  # noqa: E402
from common.models import (  # noqa: E402
    ActiveBookLock,
    ActivePairLock,
    Book,
    BookReadProgress,
    BookSwitchRequest,
    PairBlock,
    PairRequest,
    CatalogBook,
    CatalogContent,
    CatalogFavorite,
    CatalogReaderMark,
    CatalogReadProgress,
    Entry,
    Pair,
    SessionModel,
    User,
)
from repo import store_repo  # noqa: E402
from service.catalog_toc import generate_catalog_toc  # noqa: E402
from service import reading_service  # noqa: E402
from service import store_service  # noqa: E402

# 超过 MySQL TEXT(64KB) 上限的正文长度，生产库需 LONGTEXT
_LARGE_TEXT_CHARS = 70_000


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@pytest.fixture(scope="session")
def client():
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture(scope="function")
def seeded_token():
    store_service._gutendex_failure_count = 0
    store_service._gutendex_block_until = 0
    store_service._gutendex_zh_sync_done = False

    db = SessionLocal()
    db.query(ActiveBookLock).delete()
    db.query(ActivePairLock).delete()
    db.query(BookSwitchRequest).delete()
    db.query(PairRequest).delete()
    db.query(PairBlock).delete()
    db.query(Entry).delete()
    db.query(BookReadProgress).delete()
    db.query(Book).delete()
    db.query(CatalogReadProgress).delete()
    db.query(CatalogFavorite).delete()
    db.query(CatalogReaderMark).delete()
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


PARTNER_TOKEN = "tok_store_v2_b"


def _ensure_partner_session() -> None:
    db = SessionLocal()
    if not db.query(SessionModel).filter(SessionModel.token == PARTNER_TOKEN).first():
        db.add(
            SessionModel(
                token=PARTNER_TOKEN,
                user_id="u_b",
                created_at=_utc_now(),
                expires_at=(datetime.now(timezone.utc) + timedelta(days=7))
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            )
        )
        db.commit()
    db.close()


def _create_book_with_partner_approval(client, token_a: str, payload: dict, *, token_b: str = PARTNER_TOKEN) -> dict:
    """创建共读书目并由伙伴 B 同意（加入共读须双方确认）。"""
    _ensure_partner_session()
    created = client.post("/api/v2/books", json=payload, headers=_auth(token_a))
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    if body.get("mode") == "switch_request":
        req_id = body["switch_request"]["request_id"]
        approved = client.post(
            f"/api/v2/pairs/current/book-switch-requests/{req_id}/respond",
            json={"action": "approve"},
            headers=_auth(token_b),
        )
        assert approved.status_code == 200, approved.text
        return approved.json()["data"]["book"]
    if body.get("mode") == "book":
        return body["book"]
    return body


def test_store_list_and_read(client, seeded_token):
    resp = client.get("/api/v2/store/books")
    assert resp.status_code == 200
    assert len(resp.json()["data"]["books"]) >= 1
    assert resp.json()["data"]["categories"]

    history = client.get("/api/v2/store/books?category=history")
    assert history.status_code == 200
    history_books = history.json()["data"]["books"]
    assert history_books
    assert {item["category"] for item in history_books} == {"history"}

    builtin_detail = client.get("/api/v2/store/books/builtin_shiji")
    assert builtin_detail.status_code == 200
    assert builtin_detail.json()["data"]["book"]["has_text"] is True

    detail = client.get("/api/v2/store/books/gutendex_1")
    assert detail.status_code == 200
    assert detail.json()["data"]["book"]["catalog_id"] == "gutendex_1"

    read1 = client.get("/api/v2/store/books/gutendex_1/read?page=1", headers=_auth(seeded_token))
    assert read1.status_code == 200
    assert read1.json()["data"]["total_pages"] == 2


def test_public_domain_catalog_books_are_real_readable_entries(client, seeded_token, monkeypatch):
    listed = client.get("/api/v2/store/books?query=%E8%A5%BF%E6%B8%B8%E8%AE%B0")
    assert listed.status_code == 200
    books = listed.json()["data"]["books"]
    pg_book = next((item for item in books if item["catalog_id"] == "pg_23962"), None)
    assert pg_book is not None
    assert pg_book["has_text"] is True
    assert pg_book["category"] == "fiction"

    sample_text = "*** START OF THE PROJECT GUTENBERG EBOOK 西游记 ***\n第一回\n" + ("猴王出世。" * 500)
    sample_text += "\n*** END OF THE PROJECT GUTENBERG EBOOK 西游记 ***"
    monkeypatch.setattr(store_service, "_fetch_url_bytes", lambda url, limit: sample_text.encode("utf-8"))

    detail = client.get("/api/v2/store/books/pg_23962", headers=_auth(seeded_token))
    assert detail.status_code == 200
    assert detail.json()["data"]["book"]["reader_mode"] == "pager"

    page = client.get("/api/v2/store/books/pg_23962/read?page=1", headers=_auth(seeded_token))
    assert page.status_code == 200
    body = page.json()["data"]
    assert body["total_pages"] >= 1
    assert "第一回" in body["content"]
    assert "PROJECT GUTENBERG" not in body["content"]


def test_seed_upserts_public_domain_when_only_pg_catalog_exists():
    """JSON 扩容后，即使库内仅有 pg_* 书目，seed 仍应增量 upsert 公版清单。"""
    db = SessionLocal()
    try:
        db.query(CatalogContent).delete()
        db.query(CatalogBook).delete()
        db.commit()
        now = _utc_now()
        db.add(
            CatalogBook(
                catalog_id="pg_99999",
                source="project_gutenberg",
                source_book_id="99999",
                title="占位公版书",
                author="佚名",
                language="zh",
                cover_url="",
                detail_url="https://www.gutenberg.org/ebooks/99999",
                text_url="https://www.gutenberg.org/cache/epub/99999/pg99999.txt",
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
        inserted = store_service.seed_default_store_books(db)
        ids = set(store_repo.list_catalog_ids(db))
        expected = len(store_service.PUBLIC_DOMAIN_CATALOG_BOOKS)
        assert len(ids) >= expected
        assert inserted >= expected - 1
    finally:
        db.close()


def test_sync_gutendex_chinese_catalog_upserts_books(monkeypatch):
    store_service._gutendex_zh_sync_done = False
    monkeypatch.setattr(store_service, "STORE_ENABLE_NETWORK", True)

    def fake_list_chinese(page: int = 1):
        if page != 1:
            return {"results": []}
        return {
            "results": [
                {
                    "id": 888,
                    "title": "Gutendex测试书",
                    "authors": [{"name": "测试作者"}],
                    "languages": ["zh"],
                    "formats": {"text/plain; charset=utf-8": "https://example.com/text.txt"},
                    "subjects": ["Chinese fiction"],
                    "download_count": 10,
                }
            ],
            "next": None,
        }

    monkeypatch.setattr(store_service, "_gutendex_list_chinese", fake_list_chinese)
    db = SessionLocal()
    try:
        result = store_service.sync_gutendex_chinese_catalog(db, max_pages=1, force=True)
        assert result.get("ok", 0) >= 1
        row = store_repo.get_catalog_book(db, "gutendex_888")
        assert row is not None
        assert row.title == "Gutendex测试书"
    finally:
        db.close()


def test_get_book_detail_does_not_block_on_remote_hydration(client, seeded_token, monkeypatch):
    db = SessionLocal()
    try:
        store_service.seed_default_store_books(db)
    finally:
        db.close()

    def fail_fetch(url, limit):
        raise TimeoutError("should not fetch while loading detail")

    monkeypatch.setattr(store_service, "_fetch_url_bytes", fail_fetch)

    detail = client.get("/api/v2/store/books/pg_23962", headers=_auth(seeded_token))
    assert detail.status_code == 200
    book = detail.json()["data"]["book"]
    assert book["reader_mode"] == "pager"
    assert book["has_text"] is True
    assert book["has_local_text"] is False


def test_gutenberg_ebook_url_uses_https_cache_candidate_first(client, seeded_token, monkeypatch):
    db = SessionLocal()
    try:
        store_service.seed_default_store_books(db)
        db.query(CatalogContent).filter(CatalogContent.catalog_id == "pg_23962").delete()
        row = db.query(CatalogBook).filter(CatalogBook.catalog_id == "pg_23962").one()
        row.text_url = "https://www.gutenberg.org/ebooks/23962.txt.utf-8"
        db.commit()
    finally:
        db.close()

    seen_urls = []
    sample_text = "*** START OF THE PROJECT GUTENBERG EBOOK 西游记 ***\n第一回\n" + ("猴王出世。" * 500)

    def fake_fetch(url, limit):
        seen_urls.append(url)
        return sample_text.encode("utf-8")

    def fake_payload(url, limit):
        seen_urls.append(url)
        return sample_text.encode("utf-8"), "text/plain; charset=utf-8"

    monkeypatch.setattr(store_service, "_fetch_url_payload", fake_payload)

    page = client.get("/api/v2/store/books/pg_23962/read?page=1", headers=_auth(seeded_token))
    assert page.status_code == 200
    assert seen_urls[0] == "https://www.gutenberg.org/cache/epub/23962/pg23962.txt"


def test_catalog_toc_returns_empty_when_remote_text_unavailable(client, seeded_token, monkeypatch):
    db = SessionLocal()
    try:
        store_service.seed_default_store_books(db)
        db.query(CatalogContent).filter(CatalogContent.catalog_id == "pg_23835").delete()
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(store_service, "fetch_plain_catalog_from_url", lambda db, book: False)

    toc = client.get("/api/v2/store/books/pg_23835/toc", headers=_auth(seeded_token))
    assert toc.status_code == 200
    data = toc.json()["data"]
    assert data["catalog_id"] == "pg_23835"
    assert data["chapters"] == []
    assert data["chapter_count"] == 0


def test_catalog_content_accepts_text_beyond_mysql_text_limit(client, seeded_token):
    """回归：长篇 Gutenberg 正文约 60 万字符，MySQL 须为 LONGTEXT。"""
    db = SessionLocal()
    try:
        long_text = "隋唐演義\n\n" + ("正文段落。" * (_LARGE_TEXT_CHARS // 5))
        store_repo.upsert_catalog_content(
            db,
            catalog_id="gutendex_1",
            content_text=long_text,
            page_size_chars=1200,
            total_pages=max(1, len(long_text) // 1200),
            now=_utc_now(),
        )
        db.commit()
        row = store_repo.get_catalog_content(db, "gutendex_1")
        assert row is not None
        assert row.content_len >= _LARGE_TEXT_CHARS
    finally:
        db.close()

    toc = client.get("/api/v2/store/books/gutendex_1/toc", headers=_auth(seeded_token))
    assert toc.status_code == 200
    assert toc.json()["data"]["catalog_id"] == "gutendex_1"


def test_catalog_reading_progress(client, seeded_token):
    put = client.put(
        "/api/v2/store/books/gutendex_1/reading-progress",
        json={"page": 2},
        headers=_auth(seeded_token),
    )
    assert put.status_code == 200
    got = client.get("/api/v2/store/books/gutendex_1/reading-progress", headers=_auth(seeded_token))
    assert got.status_code == 200
    assert got.json()["data"]["last_page"] == 2


def test_catalog_progress_unifies_entry_and_book(client, seeded_token):
    """日记页码高于书城/共读进度时，续读 API 与详情应一致取最大页。"""
    body = _create_book_with_partner_approval(client, seeded_token, {"catalog_id": "gutendex_1"})
    book_id = body["book_id"]

    put = client.put(
        "/api/v2/store/books/gutendex_1/reading-progress",
        json={"page": 1},
        headers=_auth(seeded_token),
    )
    assert put.status_code == 200

    entry = client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 2, "note_content": "第2页笔记"},
        headers=_auth(seeded_token),
    )
    assert entry.status_code == 200

    got = client.get("/api/v2/store/books/gutendex_1/reading-progress", headers=_auth(seeded_token))
    assert got.status_code == 200
    assert got.json()["data"]["last_page"] == 2

    detail = client.get("/api/v2/store/books/gutendex_1", headers=_auth(seeded_token))
    assert detail.status_code == 200
    assert detail.json()["data"]["book"]["reading_progress_page"] == 2

    home = client.get("/api/v2/home", headers=_auth(seeded_token))
    assert home.status_code == 200
    current = home.json()["data"]["current_book"]
    assert current is not None
    assert current["my_progress"] == 2


def test_generate_catalog_toc_unit():
    text = "序言\n\n引子" + "嗯" * 400 + "\n第二章 转折\n\n正文"
    entries = generate_catalog_toc(text, page_size_chars=200)
    titles = [e["title"] for e in entries]
    assert any("序言" in t for t in titles)
    assert any("第二章" in t for t in titles)


def test_catalog_reader_marks_crud(client, seeded_token):
    lst = client.get("/api/v2/store/books/gutendex_1/marks", headers=_auth(seeded_token))
    assert lst.status_code == 200
    assert lst.json()["data"]["marks"] == []

    put = client.put(
        "/api/v2/store/books/gutendex_1/marks",
        json={
            "page": 1,
            "para_index": 0,
            "style": "marker",
            "note": "好句",
            "text_snap": "甲甲甲",
        },
        headers=_auth(seeded_token),
    )
    assert put.status_code == 200

    lst2 = client.get("/api/v2/store/books/gutendex_1/marks", headers=_auth(seeded_token))
    assert lst2.status_code == 200
    marks = lst2.json()["data"]["marks"]
    assert len(marks) == 1
    assert marks[0]["note"] == "好句"
    assert marks[0]["style"] == "marker"

    rm = client.delete(
        "/api/v2/store/books/gutendex_1/marks?page=1&para_index=0",
        headers=_auth(seeded_token),
    )
    assert rm.status_code == 200
    lst3 = client.get("/api/v2/store/books/gutendex_1/marks", headers=_auth(seeded_token))
    assert lst3.json()["data"]["marks"] == []


def test_catalog_toc_endpoint(client, seeded_token):
    db = SessionLocal()
    row = db.query(CatalogContent).filter(CatalogContent.catalog_id == "gutendex_1").one()
    row.content_text = "前言\n\n" + row.content_text + "\nChapter 2\n\n尾部"
    db.commit()
    db.close()

    resp = client.get("/api/v2/store/books/gutendex_1/toc", headers=_auth(seeded_token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["catalog_id"] == "gutendex_1"
    assert data["chapter_count"] >= 2
    pages = [c["page"] for c in data["chapters"]]
    assert pages == sorted(pages)


def test_my_shelf_recent_and_favorite(client, seeded_token):
    put = client.put(
        "/api/v2/store/books/gutendex_1/reading-progress",
        json={"page": 2},
        headers=_auth(seeded_token),
    )
    assert put.status_code == 200
    recent = client.get("/api/v2/store/my-shelf?tab=recent&page=1", headers=_auth(seeded_token))
    assert recent.status_code == 200
    payload = recent.json()["data"]
    assert payload["tab"] == "recent"
    books = payload["books"]
    assert books
    mine = next((b for b in books if b["catalog_id"] == "gutendex_1"), None)
    assert mine is not None
    assert mine.get("reading_progress_page") == 2

    fav_post = client.post("/api/v2/store/books/gutendex_1/favorite", headers=_auth(seeded_token))
    assert fav_post.status_code == 200
    assert fav_post.json()["data"]["favorited"] is True

    detail = client.get("/api/v2/store/books/gutendex_1", headers=_auth(seeded_token))
    assert detail.status_code == 200
    assert detail.json()["data"]["book"]["is_favorited"] is True

    fav_list = client.get("/api/v2/store/my-shelf?tab=favorites&page=1", headers=_auth(seeded_token))
    assert fav_list.status_code == 200
    fav_books = fav_list.json()["data"]["books"]
    assert any(b["catalog_id"] == "gutendex_1" for b in fav_books)

    fav_del = client.delete("/api/v2/store/books/gutendex_1/favorite", headers=_auth(seeded_token))
    assert fav_del.status_code == 200
    detail2 = client.get("/api/v2/store/books/gutendex_1", headers=_auth(seeded_token))
    assert detail2.json()["data"]["book"]["is_favorited"] is False


def test_stats_count_only_truly_finished_books(client, seeded_token):
    """双方读至末页才计入 total_books / completed_books。"""
    other = client.post("/api/v2/auth/login", json={"code": "x", "debug_open_id": "ob"})
    other_token = other.json()["data"]["token"]

    book = _create_book_with_partner_approval(client, seeded_token, {"catalog_id": "gutendex_1"})
    book_id = book["book_id"]

    client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 2, "note_content": ""},
        headers=_auth(seeded_token),
    )
    client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 2, "note_content": ""},
        headers=_auth(other_token),
    )

    stats = client.get("/api/v2/users/me/stats", headers=_auth(seeded_token))
    assert stats.json()["data"]["total_books"] == 1

    goal = client.get("/api/v2/users/me/reading-goal", headers=_auth(seeded_token))
    assert goal.json()["data"]["progress"]["completed_books"] >= 1


def test_import_txt_upload(client, seeded_token):
    body = ("第一章\n\n" + "这是用户上传的中文正文，用于共读导入测试。" * 30).encode("utf-8")
    imported = client.post(
        "/api/v2/store/books/import-txt",
        data={"title": "上传测试书", "author": "测试"},
        files={"file": ("book.txt", body, "text/plain")},
        headers=_auth(seeded_token),
    )
    assert imported.status_code == 200
    payload = imported.json()["data"]
    assert payload["catalog_id"].startswith("utxt_")
    assert payload["total_pages"] >= 1

    page = client.get(
        f"/api/v2/store/books/{payload['catalog_id']}/read?page=1",
        headers=_auth(seeded_token),
    )
    assert page.status_code == 200
    assert "第一章" in page.json()["data"]["content"]


def test_partner_can_read_private_txt_after_joining_pair_book(client, seeded_token):
    _ensure_partner_session()
    body = ("第一章\n\n" + "这是申请方上传后加入共读的私有 TXT。" * 40).encode("utf-8")
    imported = client.post(
        "/api/v2/store/books/import-txt",
        data={"title": "共读私有TXT", "author": "测试"},
        files={"file": ("private.txt", body, "text/plain")},
        headers=_auth(seeded_token),
    )
    assert imported.status_code == 200, imported.text
    catalog_id = imported.json()["data"]["catalog_id"]

    blocked = client.get(f"/api/v2/store/books/{catalog_id}/read?page=1", headers=_auth(PARTNER_TOKEN))
    assert blocked.status_code == 403

    created = _create_book_with_partner_approval(client, seeded_token, {"catalog_id": catalog_id})
    assert created["catalog_id"] == catalog_id

    detail = client.get(f"/api/v2/store/books/{catalog_id}", headers=_auth(PARTNER_TOKEN))
    assert detail.status_code == 200, detail.text
    page = client.get(f"/api/v2/store/books/{catalog_id}/read?page=1", headers=_auth(PARTNER_TOKEN))
    assert page.status_code == 200, page.text
    assert "第一章" in page.json()["data"]["content"]


def test_import_txt_rejects_empty_file(client, seeded_token):
    resp = client.post(
        "/api/v2/store/books/import-txt",
        data={"title": "空文件"},
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=_auth(seeded_token),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40096


def test_import_url_fetches_remote_text(client, seeded_token, monkeypatch):
    text = "第一章\n\n" + ("这是一段可公开访问的完整正文。" * 80)

    def fake_fetch(url, limit):
        assert url == "https://example.org/book.txt"
        return text.encode("utf-8"), "text/plain; charset=utf-8"

    monkeypatch.setattr(store_service, "_validate_public_import_url", lambda url: None)
    monkeypatch.setattr(store_service, "_fetch_url_payload", fake_fetch)

    imported = client.post(
        "/api/v2/store/books/import-url",
        json={
            "title": "远程全文书",
            "author": "作者",
            "read_url": "https://example.org/book.txt",
        },
        headers=_auth(seeded_token),
    )
    assert imported.status_code == 200
    payload = imported.json()["data"]
    assert payload["import_mode"] == "remote_text"
    assert payload["total_pages"] >= 1

    detail = client.get(f"/api/v2/store/books/{payload['catalog_id']}", headers=_auth(seeded_token))
    assert detail.status_code == 200
    assert detail.json()["data"]["book"]["reader_mode"] == "pager"

    page = client.get(f"/api/v2/store/books/{payload['catalog_id']}/read?page=1", headers=_auth(seeded_token))
    assert page.status_code == 200
    assert "第一章" in page.json()["data"]["content"]


def test_import_url_rejects_private_network(client, seeded_token):
    imported = client.post(
        "/api/v2/store/books/import-url",
        json={
            "title": "本机地址",
            "author": "",
            "read_url": "http://127.0.0.1/private.txt",
        },
        headers=_auth(seeded_token),
    )
    assert imported.status_code == 400
    assert imported.json()["code"] == 40098


def test_store_book_detail_pair_action_when_already_in_catalog(client, seeded_token):
    catalog_id = "gutendex_1"

    created = _create_book_with_partner_approval(client, seeded_token, {"catalog_id": catalog_id})

    detail = client.get(f"/api/v2/store/books/{catalog_id}", headers=_auth(seeded_token))
    assert detail.status_code == 200
    book = detail.json()["data"]["book"]
    assert book["in_pair_catalog"] is True
    assert book["pair_action"] == "view"
    assert book["pair_action_label"] == "看进度"
    assert book["is_current_pair_book"] is True

    dup = client.post("/api/v2/books", json={"catalog_id": catalog_id}, headers=_auth(seeded_token))
    assert dup.status_code == 200
    dup_body = dup.json()["data"]
    assert dup_body.get("mode") == "book"
    assert dup_body["book"]["book_id"] == created["book_id"]


def test_book_switch_request_requires_partner_approval(client, seeded_token):
    other_token = "tok_store_v2_b"
    other_sess = SessionModel(
        token=other_token,
        user_id="u_b",
        created_at=_utc_now(),
        expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    db = SessionLocal()
    db.add(other_sess)
    db.commit()
    db.close()

    first = _create_book_with_partner_approval(client, seeded_token, {"catalog_id": "gutendex_1"})
    first_id = first["book_id"]

    blocked = client.post(
        "/api/v2/books",
        json={"title": "新书", "author": "测", "total_pages": 100},
        headers=_auth(seeded_token),
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == 40021

    requested = client.post(
        "/api/v2/pairs/current/book-switch-requests",
        json={"title": "切换后的共读书", "author": "测试", "total_pages": 120},
        headers=_auth(seeded_token),
    )
    assert requested.status_code == 200
    req_id = requested.json()["data"]["switch_request"]["request_id"]

    home_a = client.get("/api/v2/home", headers=_auth(seeded_token))
    assert home_a.json()["data"]["book_switch"]["outgoing"]["request_id"] == req_id

    home_b = client.get("/api/v2/home", headers=_auth(other_token))
    assert home_b.json()["data"]["book_switch"]["incoming"]["request_id"] == req_id

    approved = client.post(
        f"/api/v2/pairs/current/book-switch-requests/{req_id}/respond",
        json={"action": "approve"},
        headers=_auth(other_token),
    )
    assert approved.status_code == 200
    second_id = approved.json()["data"]["book"]["book_id"]
    assert second_id != first_id

    home_after = client.get("/api/v2/home", headers=_auth(seeded_token))
    assert home_after.json()["data"]["current_book"]["book_id"] == second_id
    assert home_after.json()["data"]["current_book"]["title"] == "切换后的共读书"

    db = SessionLocal()
    old = db.query(Book).filter(Book.book_id == first_id).one()
    assert old.status == "switched"
    db.close()

    history = client.get("/api/v2/users/me/reading-history?page=1&page_size=20", headers=_auth(seeded_token))
    assert history.status_code == 200
    old_item = next((x for x in history.json()["data"]["items"] if x["book_id"] == first_id), None)
    assert old_item is not None
    assert old_item["display_status"] == "switched"
    assert old_item["display_label"] == "已切换"


def test_create_book_current_and_entry(client, seeded_token):
    listed = client.get("/api/v2/store/books?category=history")
    assert listed.status_code == 200
    catalog_id = listed.json()["data"]["books"][0]["catalog_id"]

    created = _create_book_with_partner_approval(client, seeded_token, {"catalog_id": catalog_id})
    book_id = created["book_id"]

    current = client.get("/api/v2/pairs/current/books/current", headers=_auth(seeded_token))
    assert current.status_code == 200
    assert current.json()["data"]["book"]["book_id"] == book_id

    db = SessionLocal()
    active_lock = db.query(ActiveBookLock).filter(ActiveBookLock.pair_id == "p_1").one_or_none()
    db.close()
    assert active_lock is not None
    assert active_lock.book_id == book_id

    entry = client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 1, "note_content": "", "client_request_id": "req1"},
        headers=_auth(seeded_token),
    )
    assert entry.status_code == 200
    assert entry.json()["data"]["my_progress"] == 1

    # 相同 client_request_id 重放不应生成重复记录（幂等）
    duplicated = client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 1, "note_content": "重复提交", "client_request_id": "req1"},
        headers=_auth(seeded_token),
    )
    assert duplicated.status_code == 200

    entries = client.get(f"/api/v2/books/{book_id}/entries?page=1&page_size=10", headers=_auth(seeded_token))
    assert entries.status_code == 200
    payload = entries.json()["data"]
    assert payload["pagination"]["total"] == 1
    assert len(payload["entries"]) == 1


def test_active_book_lock_is_removed_when_both_users_finish(client, seeded_token):
    other_user = client.post("/api/v2/auth/login", json={"code": "x", "debug_open_id": "ob"})
    assert other_user.status_code == 200
    other_token = other_user.json()["data"]["token"]

    created = _create_book_with_partner_approval(client, seeded_token, {"catalog_id": "gutendex_1"})
    book_id = created["book_id"]

    mine = client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 2, "note_content": ""},
        headers=_auth(seeded_token),
    )
    assert mine.status_code == 200

    partner = client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 2, "note_content": ""},
        headers=_auth(other_token),
    )
    assert partner.status_code == 200
    assert partner.json()["data"]["status"] == "finished"

    db = SessionLocal()
    book = db.query(Book).filter(Book.book_id == book_id).one()
    active_lock = db.query(ActiveBookLock).filter(ActiveBookLock.pair_id == "p_1").one_or_none()
    db.close()
    assert book.status == "finished"
    assert active_lock is None


def test_catalog_progress_is_scoped_to_pair_book(client, seeded_token):
    first_body = _create_book_with_partner_approval(client, seeded_token, {"catalog_id": "gutendex_1"})
    first_book_id = first_body["book_id"]

    progress = client.put(
        "/api/v2/store/books/gutendex_1/reading-progress",
        json={"page": 2},
        headers=_auth(seeded_token),
    )
    assert progress.status_code == 200
    assert progress.json()["data"]["last_page"] == 2

    scoped = client.get("/api/v2/store/books/gutendex_1/reading-progress", headers=_auth(seeded_token))
    assert scoped.status_code == 200
    assert scoped.json()["data"]["last_page"] == 2

    _ensure_partner_session()
    unbind_req = client.delete("/api/v2/pairs/current", headers=_auth(seeded_token))
    assert unbind_req.status_code == 200
    unbind_body = unbind_req.json()["data"]
    assert unbind_body.get("mode") == "pair_request"
    unbind_id = unbind_body["pair_request"]["request_id"]
    approve_unbind = client.post(
        f"/api/v2/pairs/requests/{unbind_id}/respond",
        json={"action": "approve"},
        headers=_auth(PARTNER_TOKEN),
    )
    assert approve_unbind.status_code == 200

    db = SessionLocal()
    now = _utc_now()
    token_c = "tok_store_v2_c"
    db.add(User(user_id="u_c", open_id="oc", nickname="C", avatar="", join_code="333333", created_at=now))
    db.add(
        SessionModel(
            token=token_c,
            user_id="u_c",
            created_at=now,
            expires_at=(datetime.now(timezone.utc) + timedelta(days=7))
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        )
    )
    db.commit()
    db.close()

    rebound = client.post("/api/v2/pairs", json={"join_code": "333333"}, headers=_auth(seeded_token))
    assert rebound.status_code == 200
    rebound_body = rebound.json()["data"]
    assert rebound_body.get("mode") == "pair_request"
    rebound_id = rebound_body["pair_request"]["request_id"]
    approve_rebind = client.post(
        f"/api/v2/pairs/requests/{rebound_id}/respond",
        json={"action": "approve"},
        headers=_auth(token_c),
    )
    assert approve_rebind.status_code == 200

    second_body = _create_book_with_partner_approval(
        client, seeded_token, {"catalog_id": "gutendex_1"}, token_b=token_c
    )
    second_book_id = second_body["book_id"]
    assert second_book_id != first_book_id
    assert second_body["my_progress"] == 0

    fresh = client.get("/api/v2/store/books/gutendex_1/reading-progress", headers=_auth(seeded_token))
    assert fresh.status_code == 200
    assert fresh.json()["data"]["last_page"] == 1

    history = client.get("/api/v2/users/me/reading-history?page=1&page_size=10", headers=_auth(seeded_token))
    assert history.status_code == 200
    items = history.json()["data"]["items"]
    by_book = {item["book_id"]: item for item in items}
    assert by_book[first_book_id]["my_progress"] == 2
    assert by_book[first_book_id]["partner_nickname"] == "B"
    assert by_book[second_book_id]["my_progress"] == 0
    assert by_book[second_book_id]["partner_nickname"] == "C"


def test_store_list_uses_page_offset(client, seeded_token, monkeypatch):
    monkeypatch.setattr(store_service, "_gutendex_list_popular", lambda page=1: {"results": []})
    monkeypatch.setattr(store_service, "_gutendex_search_books", lambda query, page=1: {"results": []})
    monkeypatch.setattr(store_service, "seed_default_store_books", lambda db, force=False: 0)

    db = SessionLocal()
    db.query(CatalogReadProgress).delete()
    db.query(CatalogFavorite).delete()
    db.query(CatalogReaderMark).delete()
    db.query(CatalogBook).delete()
    db.commit()

    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(25):
        timestamp = (base_time + timedelta(minutes=index)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        rows.append(
            CatalogBook(
                catalog_id=f"page_book_{index:02d}",
                source="project_gutenberg",
                source_book_id=f"page_book_{index:02d}",
                title=f"Book {index:02d}",
                author="Tester",
                language="zh",
                cover_url="",
                detail_url="https://example.com",
                text_url="",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    db.add_all(rows)
    db.commit()
    db.close()

    page_1 = client.get("/api/v2/store/books?page=1")
    page_2 = client.get("/api/v2/store/books?page=2")

    assert page_1.status_code == 200
    assert page_2.status_code == 200

    page_1_ids = [item["catalog_id"] for item in page_1.json()["data"]["books"]]
    page_2_ids = [item["catalog_id"] for item in page_2.json()["data"]["books"]]

    assert len(page_1_ids) == 20
    assert len(page_2_ids) == 5
    # 列表按评分（无评分视为 0）降序，同分按 catalog_id 稳定排序
    assert page_1_ids[0] == "page_book_00"
    assert page_2_ids == ["page_book_20", "page_book_21", "page_book_22", "page_book_23", "page_book_24"]
    assert not set(page_1_ids) & set(page_2_ids)


def test_store_list_opens_circuit_after_repeated_network_failures(client, seeded_token, monkeypatch):
    call_count = {"value": 0}
    monkeypatch.setattr(store_service, "STORE_ENABLE_NETWORK", True)

    def fail_network(query, page=1):
        call_count["value"] += 1
        raise TimeoutError("network timeout")

    monkeypatch.setattr(store_service, "_gutendex_search_books", fail_network)

    for _ in range(store_service.GUTENDEX_FAILURE_THRESHOLD):
        resp = client.get("/api/v2/store/books?query=networkprobe")
        assert resp.status_code == 200
        assert resp.json()["data"]["network_error"] is True

    def should_not_call(query, page=1):
        raise AssertionError("circuit should skip Gutendex")

    monkeypatch.setattr(store_service, "_gutendex_search_books", should_not_call)
    skipped = client.get("/api/v2/store/books?query=networkprobe")
    assert skipped.status_code == 200
    assert skipped.json()["data"]["network_skipped"] is True
    assert call_count["value"] == store_service.GUTENDEX_FAILURE_THRESHOLD


def test_locked_entry_cannot_be_replied_before_unlock(client, seeded_token):
    other_user = client.post("/api/v2/auth/login", json={"code": "x", "debug_open_id": "ob"})
    assert other_user.status_code == 200
    other_token = other_user.json()["data"]["token"]

    created = _create_book_with_partner_approval(client, seeded_token, {"catalog_id": "gutendex_1"})
    book_id = created["book_id"]

    first_entry = client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 2, "note_content": "spoiler"},
        headers=_auth(seeded_token),
    )
    assert first_entry.status_code == 200

    progress_entry = client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 1, "note_content": ""},
        headers=_auth(other_token),
    )
    assert progress_entry.status_code == 200

    entries = client.get(f"/api/v2/books/{book_id}/entries?page=1&page_size=10", headers=_auth(other_token))
    assert entries.status_code == 200
    locked_entry = next(item for item in entries.json()["data"]["entries"] if item["user_id"] == "u_a")
    assert locked_entry["is_locked"] is True

    reply = client.post(
        f"/api/v2/entries/{locked_entry['entry_id']}/replies",
        json={"content": "not yet"},
        headers=_auth(other_token),
    )
    assert reply.status_code == 400
    assert reply.json()["code"] == 40031


def test_create_entry_is_idempotent_under_concurrent_replay(client, seeded_token):
    created = _create_book_with_partner_approval(client, seeded_token, {"catalog_id": "gutendex_1"})
    book_id = created["book_id"]

    barrier = Barrier(2)

    def submit_once():
        with TestClient(fastapi_app, raise_server_exceptions=False) as isolated_client:
            barrier.wait(timeout=5)
            return isolated_client.post(
                f"/api/v2/books/{book_id}/entries",
                json={"page": 1, "note_content": "", "client_request_id": "req-concurrent"},
                headers=_auth(seeded_token),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: submit_once(), range(2)))

    assert all(response.status_code == 200 for response in responses)

    entries = client.get(f"/api/v2/books/{book_id}/entries?page=1&page_size=10", headers=_auth(seeded_token))
    assert entries.status_code == 200
    payload = entries.json()["data"]
    assert payload["pagination"]["total"] == 1


def test_create_book_allows_only_one_success_under_concurrency(client, seeded_token, monkeypatch):
    original_new_id = reading_service.new_id

    def slow_new_id(prefix: str) -> str:
        time.sleep(0.05)
        return original_new_id(prefix)

    monkeypatch.setattr(reading_service, "new_id", slow_new_id)
    barrier = Barrier(2)

    def create_once():
        with TestClient(fastapi_app, raise_server_exceptions=False) as isolated_client:
            barrier.wait(timeout=5)
            return isolated_client.post("/api/v2/books", json={"catalog_id": "gutendex_1"}, headers=_auth(seeded_token))

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: create_once(), range(2)))

    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [200, 400]
    ok_resp = next(response for response in responses if response.status_code == 200)
    fail_resp = next(response for response in responses if response.status_code == 400)
    assert ok_resp.json()["data"].get("mode") == "switch_request"
    assert fail_resp.json()["code"] in {40023, 40024}
    req_id = ok_resp.json()["data"]["switch_request"]["request_id"]

    _ensure_partner_session()
    approved = client.post(
        f"/api/v2/pairs/current/book-switch-requests/{req_id}/respond",
        json={"action": "approve"},
        headers=_auth(PARTNER_TOKEN),
    )
    assert approved.status_code == 200

    db = SessionLocal()
    active_books = db.query(Book).filter(Book.pair_id == "p_1", Book.status == "reading").all()
    active_locks = db.query(ActiveBookLock).filter(ActiveBookLock.pair_id == "p_1").all()
    db.close()
    assert len(active_books) == 1
    assert len(active_locks) == 1


def test_unbind_api_switches_reading_book(client, seeded_token):
    """解绑 API 应将在读书标为 switched，避免误计真读完。"""
    _ensure_partner_session()
    created = _create_book_with_partner_approval(client, seeded_token, {"catalog_id": "gutendex_1"})
    book_id = created["book_id"]

    unbind = client.delete("/api/v2/pairs/current", headers=_auth(seeded_token))
    assert unbind.status_code == 200
    unbind_body = unbind.json()["data"]
    assert unbind_body.get("mode") == "pair_request"
    approve = client.post(
        f"/api/v2/pairs/requests/{unbind_body['pair_request']['request_id']}/respond",
        json={"action": "approve"},
        headers=_auth(PARTNER_TOKEN),
    )
    assert approve.status_code == 200
    assert approve.json()["data"]["status"] == "unbound"

    db = SessionLocal()
    book = db.query(Book).filter(Book.book_id == book_id).one()
    db.close()
    assert book.status == "switched"
