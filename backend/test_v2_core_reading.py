# -*- coding: utf-8 -*-
"""
v2 核心接口测试（登录/配对/首页/笔记）
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


_tmpdir = tempfile.mkdtemp()
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = os.path.join(_tmpdir, "v2_core.db")

from app_main import app as fastapi_app  # noqa: E402


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
    me = client.get("/api/v2/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["data"]["user_id"]


def test_pair_bind_home_unbind(client):
    ta = _login(client, "open_core_2a")
    tb = _login(client, "open_core_2b")
    meb = client.get("/api/v2/me", headers=_auth(tb)).json()["data"]
    bind = client.post("/api/v2/pair/bind", json={"join_code": meb["join_code"]}, headers=_auth(ta))
    assert bind.status_code == 200, bind.text

    home = client.get("/api/v2/home", headers=_auth(ta))
    assert home.status_code == 200
    assert home.json()["data"]["pair"] is not None

    unbind = client.post("/api/v2/pair/unbind", headers=_auth(ta))
    assert unbind.status_code == 200
    assert unbind.json()["data"]["status"] == "unbound"
