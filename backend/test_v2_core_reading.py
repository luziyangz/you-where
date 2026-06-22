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


def _bind_users(client: TestClient, token_a: str, token_b: str, join_code_b: str) -> None:
    bind = client.post("/api/v2/pairs", json={"join_code": join_code_b}, headers=_auth(token_a))
    assert bind.status_code == 200, bind.text
    body = bind.json()["data"]
    if body.get("mode") == "pair_request":
        req_id = body["pair_request"]["request_id"]
        approved = client.post(
            f"/api/v2/pairs/requests/{req_id}/respond",
            json={"action": "approve"},
            headers=_auth(token_b),
        )
        assert approved.status_code == 200, approved.text


def _unbind_users(client: TestClient, token_a: str, token_b: str) -> None:
    unbind = client.delete("/api/v2/pairs/current", headers=_auth(token_a))
    assert unbind.status_code == 200, unbind.text
    body = unbind.json()["data"]
    if body.get("mode") == "pair_request":
        req_id = body["pair_request"]["request_id"]
        approved = client.post(
            f"/api/v2/pairs/requests/{req_id}/respond",
            json={"action": "approve"},
            headers=_auth(token_b),
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["data"]["status"] == "unbound"
    else:
        assert body.get("status") == "unbound"


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
    bind_body = bind.json()["data"]
    assert bind_body.get("mode") == "pair"
    assert bind_body["pair"]["partner"]["join_code"] == "900002"

    home = client.get("/api/v2/home", headers=_auth(data_a["token"]))
    assert home.status_code == 200
    assert home.json()["data"]["pair"]["partner"]["join_code"] == "900002"


def test_test_user_pair_consent_flows_default_to_success(client):
    login_a = client.post("/api/v2/auth/test-login", json={"role": "a"})
    login_b = client.post("/api/v2/auth/test-login", json={"role": "b"})
    assert login_a.status_code == 200, login_a.text
    assert login_b.status_code == 200, login_b.text

    token_a = login_a.json()["data"]["token"]
    cleanup = client.delete("/api/v2/pairs/current", headers=_auth(token_a))
    assert cleanup.status_code in {200, 404}, cleanup.text

    bind = client.post("/api/v2/pairs", json={"join_code": "900002"}, headers=_auth(token_a))
    assert bind.status_code == 200, bind.text
    assert bind.json()["data"]["mode"] == "pair"

    first = client.post(
        "/api/v2/books",
        json={"title": "测试直通第一本", "author": "系统", "total_pages": 120},
        headers=_auth(token_a),
    )
    assert first.status_code == 200, first.text
    first_body = first.json()["data"]
    assert first_body.get("mode") == "book"
    assert first_body["book"]["title"] == "测试直通第一本"

    switch = client.post(
        "/api/v2/pairs/current/book-switch-requests",
        json={"title": "测试直通第二本", "author": "系统", "total_pages": 80},
        headers=_auth(token_a),
    )
    assert switch.status_code == 200, switch.text
    switch_body = switch.json()["data"]
    assert switch_body.get("mode") == "book"
    assert switch_body["book"]["title"] == "测试直通第二本"

    unbind = client.delete("/api/v2/pairs/current", headers=_auth(token_a))
    assert unbind.status_code == 200, unbind.text
    unbind_body = unbind.json()["data"]
    assert unbind_body["status"] == "unbound"
    assert unbind_body["mode"] == "pair"


def test_test_user_login_can_be_disabled(client, monkeypatch):
    from common.config import settings

    monkeypatch.setattr(settings, "ENABLE_TEST_USERS", False)
    resp = client.post("/api/v2/auth/test-login", json={"role": "a"})
    assert resp.status_code == 404
    assert resp.json()["code"] == 40404


def test_review_login_requires_enable_and_password(client, monkeypatch):
    from common.config import settings

    monkeypatch.setattr(settings, "ENABLE_REVIEW_LOGIN", False)
    monkeypatch.setattr(settings, "WECHAT_REVIEW_ACCOUNT", "reviewer")
    monkeypatch.setattr(settings, "WECHAT_REVIEW_PASSWORD", "secret_review")
    disabled = client.post("/api/v2/auth/review-login", json={"account": "reviewer", "password": "secret_review"})
    assert disabled.status_code == 404
    assert disabled.json()["code"] == 40404

    monkeypatch.setattr(settings, "ENABLE_REVIEW_LOGIN", True)
    wrong = client.post("/api/v2/auth/review-login", json={"account": "reviewer", "password": "wrong"})
    assert wrong.status_code == 401
    assert wrong.json()["code"] == 40104

    ok = client.post("/api/v2/auth/review-login", json={"account": "reviewer", "password": "secret_review"})
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["token"]
    assert data["user"]["join_code"] == "900003"

    db = SessionLocal()
    user = db.query(User).filter(User.open_id == "youzainaye_review_user").one_or_none()
    session = db.query(SessionModel).filter(SessionModel.token == data["token"]).one_or_none()
    db.close()
    assert user is not None
    assert user.nickname == "微信审核员"
    assert session is not None
    assert session.user_id == user.user_id


def test_seeded_hidden_test_user_can_be_bound_by_real_user(client):
    from scripts.seed_test_users import seed_test_users

    result = seed_test_users(reset_active_pairs=True)
    assert result["users"][0]["join_code"] == "900001"
    assert result["users"][1]["join_code"] == "900002"

    token_a = _login(client, "open_core_seed_bind")
    login_b = client.post("/api/v2/auth/test-login", json={"role": "b"})
    assert login_b.status_code == 200, login_b.text
    token_b = login_b.json()["data"]["token"]
    _bind_users(client, token_a, token_b, "900002")

    home = client.get("/api/v2/home", headers=_auth(token_a))
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
    _bind_users(client, ta, tb, meb["join_code"])

    home = client.get("/api/v2/home", headers=_auth(ta))
    assert home.status_code == 200
    assert home.json()["data"]["pair"] is not None

    _unbind_users(client, ta, tb)

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

    _bind_users(client, ta, tb, join_code)

    current_pair = client.get("/api/v2/pairs/current", headers=_auth(ta))
    assert current_pair.status_code == 200
    assert current_pair.json()["data"]["pair"]["partner"]["join_code"] == join_code

    _unbind_users(client, ta, tb)


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
    assert status_codes == [200, 200]
    bodies = [response.json()["data"] for response in responses]
    assert all(item.get("mode") == "pair_request" for item in bodies)

    req_id = bodies[0]["pair_request"]["request_id"]
    approved = client.post(
        f"/api/v2/pairs/requests/{req_id}/respond",
        json={"action": "approve"},
        headers=_auth(tb),
    )
    assert approved.status_code == 200, approved.text

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


def test_pair_bind_blocks_second_outgoing_request_to_another_user(client):
    ta = _login(client, "open_core_pending_a")
    tb = _login(client, "open_core_pending_b")
    tc = _login(client, "open_core_pending_c")
    me_b = client.get("/api/v2/users/me", headers=_auth(tb)).json()["data"]
    me_c = client.get("/api/v2/users/me", headers=_auth(tc)).json()["data"]

    first = client.post("/api/v2/pairs", json={"join_code": me_b["join_code"]}, headers=_auth(ta))
    assert first.status_code == 200, first.text
    first_body = first.json()["data"]
    assert first_body.get("mode") == "pair_request"

    repeat = client.post("/api/v2/pairs", json={"join_code": me_b["join_code"]}, headers=_auth(ta))
    assert repeat.status_code == 200, repeat.text
    repeat_body = repeat.json()["data"]
    assert repeat_body.get("mode") == "pair_request"
    assert repeat_body["pair_request"]["request_id"] == first_body["pair_request"]["request_id"]

    second = client.post("/api/v2/pairs", json={"join_code": me_c["join_code"]}, headers=_auth(ta))
    assert second.status_code == 400, second.text
    body = second.json()
    assert body["code"] == 40015
