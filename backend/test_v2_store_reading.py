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
from common.models import ActiveBookLock, ActivePairLock, Book, CatalogBook, CatalogContent, Entry, Pair, SessionModel, User  # noqa: E402
from service import reading_service  # noqa: E402
from service import store_service  # noqa: E402


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

    db = SessionLocal()
    db.query(ActiveBookLock).delete()
    db.query(ActivePairLock).delete()
    db.query(Entry).delete()
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

    read1 = client.get("/api/v2/store/books/gutendex_1/read?page=1")
    assert read1.status_code == 200
    assert read1.json()["data"]["total_pages"] == 2


def test_create_book_current_and_entry(client, seeded_token):
    listed = client.get("/api/v2/store/books?category=history")
    assert listed.status_code == 200
    catalog_id = listed.json()["data"]["books"][0]["catalog_id"]

    created = client.post("/api/v2/books", json={"catalog_id": catalog_id}, headers=_auth(seeded_token))
    assert created.status_code == 200
    book_id = created.json()["data"]["book_id"]

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

    created = client.post("/api/v2/books", json={"catalog_id": "gutendex_1"}, headers=_auth(seeded_token))
    assert created.status_code == 200
    book_id = created.json()["data"]["book_id"]

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


def test_store_list_uses_page_offset(client, seeded_token, monkeypatch):
    monkeypatch.setattr(store_service, "_gutendex_list_popular", lambda page=1: {"results": []})
    monkeypatch.setattr(store_service, "_gutendex_search_books", lambda query, page=1: {"results": []})

    db = SessionLocal()
    db.query(CatalogBook).delete()
    db.commit()

    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(25):
        timestamp = (base_time + timedelta(minutes=index)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        rows.append(
            CatalogBook(
                catalog_id=f"page_book_{index:02d}",
                source="builtin",
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
    assert page_1_ids[0] == "page_book_24"
    assert page_2_ids == ["page_book_04", "page_book_03", "page_book_02", "page_book_01", "page_book_00"]
    assert not set(page_1_ids) & set(page_2_ids)


def test_store_list_opens_circuit_after_repeated_network_failures(client, seeded_token, monkeypatch):
    call_count = {"value": 0}
    monkeypatch.setattr(store_service, "STORE_ENABLE_NETWORK", True)

    def fail_network(page=1):
        call_count["value"] += 1
        raise TimeoutError("network timeout")

    monkeypatch.setattr(store_service, "_gutendex_list_popular", fail_network)

    for _ in range(store_service.GUTENDEX_FAILURE_THRESHOLD):
        resp = client.get("/api/v2/store/books")
        assert resp.status_code == 200
        assert resp.json()["data"]["network_error"] is True

    def should_not_call(page=1):
        raise AssertionError("circuit should skip Gutendex")

    monkeypatch.setattr(store_service, "_gutendex_list_popular", should_not_call)
    skipped = client.get("/api/v2/store/books")
    assert skipped.status_code == 200
    assert skipped.json()["data"]["network_skipped"] is True
    assert call_count["value"] == store_service.GUTENDEX_FAILURE_THRESHOLD


def test_locked_entry_cannot_be_replied_before_unlock(client, seeded_token):
    other_user = client.post("/api/v2/auth/login", json={"code": "x", "debug_open_id": "ob"})
    assert other_user.status_code == 200
    other_token = other_user.json()["data"]["token"]

    created = client.post("/api/v2/books", json={"catalog_id": "gutendex_1"}, headers=_auth(seeded_token))
    assert created.status_code == 200
    book_id = created.json()["data"]["book_id"]

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
    created = client.post("/api/v2/books", json={"catalog_id": "gutendex_1"}, headers=_auth(seeded_token))
    assert created.status_code == 200
    book_id = created.json()["data"]["book_id"]

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

    failed = next(response for response in responses if response.status_code == 400)
    assert failed.json()["code"] == 40021

    db = SessionLocal()
    active_books = db.query(Book).filter(Book.pair_id == "p_1", Book.status == "reading").all()
    active_locks = db.query(ActiveBookLock).filter(ActiveBookLock.pair_id == "p_1").all()
    db.close()
    assert len(active_books) == 1
    assert len(active_locks) == 1
