# -*- coding: utf-8 -*-
"""
v2 核心接口测试（登录/配对/首页/笔记）
"""

import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient


_tmpdir = tempfile.mkdtemp()
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = os.path.join(_tmpdir, "v2_core.db")

from app_main import app as fastapi_app  # noqa: E402
from common.db import SessionLocal  # noqa: E402
from common.models import ActivePairLock, Pair, SessionModel, User  # noqa: E402
from service import reading_service  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(fastapi_app) as c:
        yield c


def _login(client: TestClient, debug_open_id: str) -> str:
    resp = client.post("/api/v2/auth/login", json={"code": "x", "debug_open_id": debug_open_id})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_login_and_me(client):
    token = _login(client, "open_core_1")
    me = client.get("/api/v2/users/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["data"]["user_id"]


def test_phone_login_with_debug_phone_number(client):
    resp = client.post(
        "/api/v2/auth/phone-login",
        json={
            "code": "x",
            "debug_open_id": "open_phone_1",
            "debug_phone_number": "13800138000",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["token"]
    assert data["user"]["phone_number"] == "13800138000"

    repeat = client.post(
        "/api/v2/auth/phone-login",
        json={
            "code": "x",
            "debug_open_id": "open_phone_1",
            "debug_phone_number": "13800138000",
        },
    )
    assert repeat.status_code == 200
    assert repeat.json()["data"]["user"]["user_id"] == data["user"]["user_id"]


def test_embedded_test_users_can_bind(client):
    login_a = client.post("/api/v2/auth/test-login", json={"role": "a"})
    login_b = client.post("/api/v2/auth/test-login", json={"role": "b"})
    assert login_a.status_code == 200, login_a.text
    assert login_b.status_code == 200, login_b.text

    data_a = login_a.json()["data"]
    data_b = login_b.json()["data"]
    assert data_a["user"]["join_code"] == "900001"
    assert data_b["user"]["join_code"] == "900002"
    assert data_a["need_agreement"] is True
    assert data_b["need_agreement"] is True

    db = SessionLocal()
    user_a = db.query(User).filter(User.open_id == "youzainaye_test_user_a").one_or_none()
    session_a = db.query(SessionModel).filter(SessionModel.token == data_a["token"]).one_or_none()
    db.close()
    assert user_a is not None
    assert user_a.join_code == "900001"
    assert session_a is not None
    assert session_a.user_id == user_a.user_id

    bind = client.post("/api/v2/pairs", json={"join_code": "900002"}, headers=_auth(data_a["token"]))
    assert bind.status_code == 200, bind.text

    home = client.get("/api/v2/home", headers=_auth(data_a["token"]))
    assert home.status_code == 200
    assert home.json()["data"]["pair"]["partner"]["join_code"] == "900002"


def test_test_user_login_can_be_disabled(client, monkeypatch):
    from common.config import settings

    monkeypatch.setattr(settings, "ENABLE_TEST_USERS", False)
    resp = client.post("/api/v2/auth/test-login", json={"role": "a"})
    assert resp.status_code == 404
    assert resp.json()["code"] == 40404


def test_seeded_hidden_test_user_can_be_bound_by_real_user(client):
    from scripts.seed_test_users import seed_test_users

    result = seed_test_users(reset_active_pairs=True)
    assert result["users"][0]["join_code"] == "900001"
    assert result["users"][1]["join_code"] == "900002"

    token = _login(client, "open_core_seed_bind")
    bind = client.post("/api/v2/pairs", json={"join_code": "900002"}, headers=_auth(token))
    assert bind.status_code == 200, bind.text

    home = client.get("/api/v2/home", headers=_auth(token))
    assert home.status_code == 200
    assert home.json()["data"]["pair"]["partner"]["join_code"] == "900002"


def test_legacy_action_routes_are_removed(client):
    removed_routes = [
        ("GET", "/api/v2/me"),
        ("GET", "/api/v2/profile/me"),
        ("POST", "/api/v2/pair/bind"),
        ("POST", "/api/v2/pair/unbind"),
        ("GET", "/api/v2/books/current"),
        ("POST", "/api/v2/entries"),
        ("POST", "/api/v2/books/b_removed/entries/read"),
    ]
    for method, path in removed_routes:
        resp = client.request(method, path, json={})
        assert resp.status_code == 404, f"{method} {path} should not be registered"


def test_pair_bind_home_unbind(client):
    ta = _login(client, "open_core_2a")
    tb = _login(client, "open_core_2b")
    meb = client.get("/api/v2/users/me", headers=_auth(tb)).json()["data"]
    bind = client.post("/api/v2/pairs", json={"join_code": meb["join_code"]}, headers=_auth(ta))
    assert bind.status_code == 200, bind.text

    home = client.get("/api/v2/home", headers=_auth(ta))
    assert home.status_code == 200
    assert home.json()["data"]["pair"] is not None

    unbind = client.delete("/api/v2/pairs/current", headers=_auth(ta))
    assert unbind.status_code == 200
    assert unbind.json()["data"]["status"] == "unbound"

    db = SessionLocal()
    active_locks = db.query(ActivePairLock).filter(ActivePairLock.user_id.in_([meb["user_id"]])).all()
    db.close()
    assert active_locks == []


def test_rest_compatible_user_and_pair_aliases(client):
    ta = _login(client, "open_core_rest_a")
    tb = _login(client, "open_core_rest_b")

    user_b = client.get("/api/v2/users/me", headers=_auth(tb))
    assert user_b.status_code == 200
    join_code = user_b.json()["data"]["join_code"]

    bind = client.post("/api/v2/pairs", json={"join_code": join_code}, headers=_auth(ta))
    assert bind.status_code == 200, bind.text

    current_pair = client.get("/api/v2/pairs/current", headers=_auth(ta))
    assert current_pair.status_code == 200
    assert current_pair.json()["data"]["pair"]["partner"]["join_code"] == join_code

    unbind = client.delete("/api/v2/pairs/current", headers=_auth(ta))
    assert unbind.status_code == 200
    assert unbind.json()["data"]["status"] == "unbound"


def test_pair_bind_rejects_self_and_unknown_code(client):
    token = _login(client, "open_core_self")
    me = client.get("/api/v2/users/me", headers=_auth(token))
    join_code = me.json()["data"]["join_code"]

    self_bind = client.post("/api/v2/pairs", json={"join_code": join_code}, headers=_auth(token))
    assert self_bind.status_code == 400
    assert self_bind.json()["code"] == 40013

    missing = client.post("/api/v2/pairs", json={"join_code": "999999"}, headers=_auth(token))
    assert missing.status_code == 400
    assert missing.json()["code"] == 40011


def test_pair_bind_allows_only_one_success_under_concurrency(client, monkeypatch):
    ta = _login(client, "open_core_concurrent_a")
    tb = _login(client, "open_core_concurrent_b")
    me_a = client.get("/api/v2/users/me", headers=_auth(ta)).json()["data"]
    me_b = client.get("/api/v2/users/me", headers=_auth(tb)).json()["data"]
    join_code = me_b["join_code"]

    original_new_id = reading_service.new_id

    def slow_new_id(prefix: str) -> str:
        time.sleep(0.05)
        return original_new_id(prefix)

    monkeypatch.setattr(reading_service, "new_id", slow_new_id)
    barrier = Barrier(2)

    def bind_once():
        with TestClient(fastapi_app, raise_server_exceptions=False) as isolated_client:
            barrier.wait(timeout=5)
            return isolated_client.post("/api/v2/pairs", json={"join_code": join_code}, headers=_auth(ta))

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: bind_once(), range(2)))

    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [200, 400]

    failed = next(response for response in responses if response.status_code == 400)
    assert failed.json()["code"] == 40012

    db = SessionLocal()
    pairs = db.query(Pair).filter(Pair.status == "active").all()
    locks = db.query(ActivePairLock).filter(ActivePairLock.user_id.in_([me_a["user_id"], me_b["user_id"]])).all()
    db.close()
    matched = [
        pair for pair in pairs
        if {pair.user_a_id, pair.user_b_id} == {me_a["user_id"], me_b["user_id"]}
    ]
    assert len(matched) == 1
    assert len(locks) == 2
