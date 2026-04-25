# -*- coding: utf-8 -*-
"""
v2 我的页接口测试
运行方式：
    cd backend
    pytest test_v2_profile.py -v
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


_tmpdir = tempfile.mkdtemp()
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = os.path.join(_tmpdir, "v2_profile.db")

from app_main import app as fastapi_app  # noqa: E402
from common.db import SessionLocal  # noqa: E402
from common.models import Book, Entry, Pair, SessionModel, User  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@pytest.fixture(scope="function")
def seeded_token():
    db = SessionLocal()
    db.query(Entry).delete()
    db.query(Book).delete()
    db.query(Pair).delete()
    db.query(SessionModel).delete()
    db.query(User).delete()
    db.commit()

    now = _utc_now()
    user_a = User(
        user_id="u_a",
        open_id="oa",
        nickname="甲",
        avatar="",
        join_code="123456",
        agreement_accepted_at=now,
        created_at=now,
    )
    user_b = User(
        user_id="u_b",
        open_id="ob",
        nickname="乙",
        avatar="",
        join_code="654321",
        agreement_accepted_at=now,
        created_at=now,
    )
    token = "tok_test_v2_profile"
    session = SessionModel(
        token=token,
        user_id="u_a",
        created_at=now,
        expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    pair = Pair(
        pair_id="p_1",
        user_a_id="u_a",
        user_b_id="u_b",
        status="active",
        created_at=now,
        updated_at=now,
    )
    book = Book(
        book_id="b_1",
        pair_id="p_1",
        title="测试书",
        author="作者",
        total_pages=200,
        status="finished",
        created_by="u_a",
        created_at=now,
        finished_at=now,
    )
    entry = Entry(
        entry_id="e_1",
        book_id="b_1",
        user_id="u_a",
        page=120,
        note_content="note",
        created_at=now,
        client_request_id="req_1",
    )
    db.add_all([user_a, user_b, session, pair, book, entry])
    db.commit()
    db.close()
    return token


@pytest.fixture(scope="session")
def client():
    with TestClient(fastapi_app) as c:
        yield c


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_profile_requires_auth(client):
    resp = client.get("/api/v2/profile/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == 40100


def test_profile_me_and_stats(client, seeded_token):
    me_resp = client.get("/api/v2/profile/me", headers=_auth(seeded_token))
    assert me_resp.status_code == 200
    me_data = me_resp.json()["data"]
    assert me_data["user"]["user_id"] == "u_a"
    assert me_data["partner"]["user_id"] == "u_b"

    stats_resp = client.get("/api/v2/profile/stats", headers=_auth(seeded_token))
    assert stats_resp.status_code == 200
    stats = stats_resp.json()["data"]
    assert stats["total_books"] == 1
    assert stats["total_entries"] == 1
    assert stats["total_pages"] >= 120


def test_goal_and_reminder_crud(client, seeded_token):
    default_goal = client.get("/api/v2/profile/goals", headers=_auth(seeded_token))
    assert default_goal.status_code == 200
    assert default_goal.json()["data"]["goal"]["period_days"] == 30

    save_goal = client.put(
        "/api/v2/profile/goals",
        json={"period_days": 60, "target_books": 3, "target_days": 30},
        headers=_auth(seeded_token),
    )
    assert save_goal.status_code == 200
    assert save_goal.json()["data"]["goal"]["target_books"] == 3

    save_reminder = client.put(
        "/api/v2/profile/reminders",
        json={"enabled": True, "remind_time": "20:30", "timezone": "Asia/Shanghai"},
        headers=_auth(seeded_token),
    )
    assert save_reminder.status_code == 200
    assert save_reminder.json()["data"]["reminder"]["remind_time"] == "20:30"

    get_reminder = client.get("/api/v2/profile/reminders", headers=_auth(seeded_token))
    assert get_reminder.status_code == 200
    assert get_reminder.json()["data"]["reminder"]["enabled"] is True


def test_history_pagination(client, seeded_token):
    resp = client.get("/api/v2/profile/history?page=1&page_size=1", headers=_auth(seeded_token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["book_id"] == "b_1"
