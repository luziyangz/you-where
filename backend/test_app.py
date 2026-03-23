# -*- coding: utf-8 -*-
"""
你在哪页 后端接口测试套件
运行方式：
    cd backend
    pip install pytest httpx
    pytest test_app.py -v
"""

import os
import tempfile

# ── 必须在导入 app 之前重定向 DB 路径到临时目录 ──────────────────
_tmpdir = tempfile.mkdtemp()

import app as backend_module

backend_module.DATA_DIR = _tmpdir
backend_module.DB_PATH  = os.path.join(_tmpdir, "test_app.db")

from app import (
    _rl_store,
    app as fastapi_app,
    ensure_db,
)

import pytest
from fastapi.testclient import TestClient

# ── pytest fixture：每个测试前清空限流状态，防止 429 串测 ───────────

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """每个测试前清空限流桶，确保登录接口不会被误限"""
    _rl_store.clear()
    yield
    _rl_store.clear()


@pytest.fixture(scope="session", autouse=True)
def init_db():
    """会话级别：仅初始化一次数据库"""
    ensure_db()


# ── 全局 TestClient（不使用上下文管理器以保持会话状态）─────────────

@pytest.fixture(scope="session")
def client():
    with TestClient(fastapi_app) as c:
        yield c


# ────────────────── 辅助函数 ──────────────────

def register_and_login(client, debug_id: str) -> str:
    """注册或登录一个用户，返回 token"""
    resp = client.post("/api/v1/auth/login", json={
        "code":          "test_code",
        "debug_open_id": debug_id
    })
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    data = resp.json()
    assert data["code"] == 0
    return data["data"]["token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_join_code(client, token: str) -> str:
    resp = client.get("/api/v1/me", headers=auth(token))
    assert resp.status_code == 200
    return resp.json()["data"]["join_code"]


def bind_users(client, token_a: str, token_b: str) -> str:
    """用 token_b 的共读码让 token_a 与其绑定，返回 pair_id"""
    code_b = get_join_code(client, token_b)
    resp   = client.post("/api/v1/pair/bind",
                         json={"join_code": code_b},
                         headers=auth(token_a))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["pair_id"]


def add_book(client, token: str, title: str = "测试之书", pages: int = 100) -> str:
    resp = client.post("/api/v1/books",
                       json={"title": title, "author": "测试作者", "total_pages": pages},
                       headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["book_id"]


# ────────────────── 健康检查 ──────────────────

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ────────────────── 登录 & 用户信息 ──────────────────

def test_login_creates_user(client):
    token = register_and_login(client, "open_id_test_001")
    assert len(token) > 10


def test_login_same_user_returns_new_token(client):
    t1 = register_and_login(client, "open_id_same_user")
    t2 = register_and_login(client, "open_id_same_user")
    # 两次登录各自生成新 token，但对应同一用户
    assert t1 != t2


def test_get_me_returns_user_fields(client):
    token = register_and_login(client, "open_id_get_me")
    resp  = client.get("/api/v1/me", headers=auth(token))
    assert resp.status_code == 200
    data  = resp.json()["data"]
    assert "user_id"   in data
    assert "nickname"  in data
    assert "join_code" in data
    assert "join_days" in data
    assert data["join_days"] >= 1


def test_get_me_requires_auth(client):
    resp = client.get("/api/v1/me")
    assert resp.status_code == 401


def test_accept_agreement(client):
    token = register_and_login(client, "open_id_agreement")
    resp  = client.post("/api/v1/auth/accept-agreement",
                        json={"accepted": True},
                        headers=auth(token))
    assert resp.status_code == 200
    user = resp.json()["data"]["user"]
    assert user["agreement_accepted_at"] is not None


# ────────────────── 统计接口 ──────────────────

def test_stats_default_values(client):
    token = register_and_login(client, "open_id_stats_default")
    resp  = client.get("/api/v1/me/stats", headers=auth(token))
    assert resp.status_code == 200
    stats = resp.json()["data"]
    assert stats["total_books"]   == 0
    assert stats["total_pages"]   == 0
    assert stats["total_entries"] == 0
    assert stats["total_days"]    >= 1


# ────────────────── 首页接口 ──────────────────

def test_home_no_pair(client):
    token = register_and_login(client, "open_id_home_nopair")
    resp  = client.get("/api/v1/home", headers=auth(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["pair"]         is None
    assert data["current_book"] is None
    assert "join_days" in data["user"]


# ────────────────── 配对：绑定 & 解绑 ──────────────────

def test_bind_pair(client):
    ta = register_and_login(client, "open_id_bind_a")
    tb = register_and_login(client, "open_id_bind_b")
    pair_id = bind_users(client, ta, tb)
    assert pair_id.startswith("p_")


def test_cannot_bind_self(client):
    ta   = register_and_login(client, "open_id_self_bind")
    code = get_join_code(client, ta)
    resp = client.post("/api/v1/pair/bind",
                       json={"join_code": code},
                       headers=auth(ta))
    assert resp.status_code == 400
    assert resp.json()["code"] == 40013


def test_cannot_bind_with_wrong_code(client):
    ta   = register_and_login(client, "open_id_wrong_code")
    resp = client.post("/api/v1/pair/bind",
                       json={"join_code": "000000"},
                       headers=auth(ta))
    assert resp.status_code == 400
    assert resp.json()["code"] == 40011


def test_pair_current_after_bind(client):
    ta = register_and_login(client, "open_id_current_a")
    tb = register_and_login(client, "open_id_current_b")
    bind_users(client, ta, tb)
    resp = client.get("/api/v1/pair/current", headers=auth(ta))
    assert resp.status_code == 200
    pair = resp.json()["data"]["pair"]
    assert pair is not None
    assert pair["status"]  == "active"
    assert "bind_days"     in pair
    assert "shared_books"  in pair
    assert "shared_notes"  in pair
    assert pair["partner"]["user_id"] is not None


def test_pair_stats_in_home(client):
    ta = register_and_login(client, "open_id_home_pair_a")
    tb = register_and_login(client, "open_id_home_pair_b")
    bind_users(client, ta, tb)
    resp = client.get("/api/v1/home", headers=auth(ta))
    pair = resp.json()["data"]["pair"]
    assert pair is not None
    assert "bind_days"    in pair
    assert "shared_books" in pair
    assert "shared_notes" in pair


def test_unbind_pair(client):
    ta = register_and_login(client, "open_id_unbind_a")
    tb = register_and_login(client, "open_id_unbind_b")
    bind_users(client, ta, tb)
    resp = client.post("/api/v1/pair/unbind", headers=auth(ta))
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "unbound"


def test_unbind_when_no_pair(client):
    ta   = register_and_login(client, "open_id_unbind_no_pair")
    resp = client.post("/api/v1/pair/unbind", headers=auth(ta))
    assert resp.status_code == 404


# ────────────────── 书籍 ──────────────────

def test_add_book_requires_pair(client):
    ta   = register_and_login(client, "open_id_book_no_pair")
    resp = client.post("/api/v1/books",
                       json={"title": "孤独书", "total_pages": 50},
                       headers=auth(ta))
    assert resp.status_code == 403


def test_add_book_success(client):
    ta = register_and_login(client, "open_id_book_ok_a")
    tb = register_and_login(client, "open_id_book_ok_b")
    bind_users(client, ta, tb)
    book_id = add_book(client, ta)
    assert book_id.startswith("b_")


def test_book_contains_reading_days(client):
    ta = register_and_login(client, "open_id_book_days_a")
    tb = register_and_login(client, "open_id_book_days_b")
    bind_users(client, ta, tb)
    resp = client.post("/api/v1/books",
                       json={"title": "进度书", "author": "", "total_pages": 200},
                       headers=auth(ta))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "reading_days" in data
    assert data["reading_days"] >= 1


def test_cannot_add_two_books(client):
    ta = register_and_login(client, "open_id_two_books_a")
    tb = register_and_login(client, "open_id_two_books_b")
    bind_users(client, ta, tb)
    add_book(client, ta, "第一本")
    resp = client.post("/api/v1/books",
                       json={"title": "第二本", "total_pages": 100},
                       headers=auth(ta))
    assert resp.status_code == 400
    assert resp.json()["code"] == 40021


def test_list_books_empty_without_pair(client):
    ta   = register_and_login(client, "open_id_list_nopair")
    resp = client.get("/api/v1/books", headers=auth(ta))
    assert resp.status_code == 200
    assert resp.json()["data"]["books"] == []


def test_get_current_book_after_add(client):
    ta = register_and_login(client, "open_id_current_book_a")
    tb = register_and_login(client, "open_id_current_book_b")
    bind_users(client, ta, tb)
    add_book(client, ta)
    resp = client.get("/api/v1/books/current", headers=auth(ta))
    assert resp.status_code == 200
    book = resp.json()["data"]["book"]
    assert book is not None
    assert book["status"] == "reading"


# ────────────────── 阅读记录/笔记 ──────────────────

def test_create_entry_updates_progress(client):
    ta = register_and_login(client, "open_id_entry_a")
    tb = register_and_login(client, "open_id_entry_b")
    bind_users(client, ta, tb)
    book_id = add_book(client, ta, pages=300)

    resp = client.post("/api/v1/entries",
                       json={"book_id": book_id, "page": 50, "note_content": "很好看"},
                       headers=auth(ta))
    assert resp.status_code == 200
    assert resp.json()["data"]["my_progress"] == 50


def test_entry_page_cannot_go_backward(client):
    ta = register_and_login(client, "open_id_backward_a")
    tb = register_and_login(client, "open_id_backward_b")
    bind_users(client, ta, tb)
    book_id = add_book(client, ta, pages=300)

    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 100},
                headers=auth(ta))
    resp = client.post("/api/v1/entries",
                       json={"book_id": book_id, "page": 50},
                       headers=auth(ta))
    assert resp.status_code == 400
    assert resp.json()["code"] == 40023


def test_entry_idempotent(client):
    ta = register_and_login(client, "open_id_idem_a")
    tb = register_and_login(client, "open_id_idem_b")
    bind_users(client, ta, tb)
    book_id = add_book(client, ta, pages=300)

    payload = {"book_id": book_id, "page": 60, "client_request_id": "req_abc123"}
    r1 = client.post("/api/v1/entries", json=payload, headers=auth(ta))
    r2 = client.post("/api/v1/entries", json=payload, headers=auth(ta))
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["data"]["my_progress"] == r2.json()["data"]["my_progress"]


def test_get_entries_contains_avatar(client):
    ta = register_and_login(client, "open_id_avatar_a")
    tb = register_and_login(client, "open_id_avatar_b")
    bind_users(client, ta, tb)
    book_id = add_book(client, ta, pages=200)
    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 20, "note_content": "有意思"},
                headers=auth(ta))

    resp    = client.get(f"/api/v1/books/{book_id}/entries", headers=auth(ta))
    entries = resp.json()["data"]["entries"]
    assert len(entries) == 1
    assert "avatar"   in entries[0]
    assert "nickname" in entries[0]


def test_partner_note_locked_when_ahead(client):
    """伙伴比我读得更多时，其笔记应被锁定"""
    ta = register_and_login(client, "open_id_lock_a")
    tb = register_and_login(client, "open_id_lock_b")
    bind_users(client, ta, tb)
    book_id = add_book(client, ta, pages=300)

    # a 读到第 30 页
    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 30},
                headers=auth(ta))
    # b 读到第 80 页并留了笔记
    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 80, "note_content": "剧情大反转！"},
                headers=auth(tb))

    # a 查看笔记，b 的笔记应被锁定
    resp    = client.get(f"/api/v1/books/{book_id}/entries", headers=auth(ta))
    entries = resp.json()["data"]["entries"]
    b_entry = next(e for e in entries if not e["is_mine"])
    assert b_entry["is_locked"]      is True
    assert b_entry["note_content"]   is None
    assert b_entry["unlock_at_page"] == 80


def test_partner_note_unlocked_when_caught_up(client):
    """a 追上 b 的进度后，b 的笔记应解锁"""
    ta = register_and_login(client, "open_id_unlock_a")
    tb = register_and_login(client, "open_id_unlock_b")
    bind_users(client, ta, tb)
    book_id = add_book(client, ta, pages=300)

    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 80, "note_content": "精彩"},
                headers=auth(tb))
    # a 追上到 80 页
    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 80},
                headers=auth(ta))

    resp    = client.get(f"/api/v1/books/{book_id}/entries", headers=auth(ta))
    entries = resp.json()["data"]["entries"]
    b_entry = next(e for e in entries if not e["is_mine"])
    assert b_entry["is_locked"]    is False
    assert b_entry["note_content"] == "精彩"


def test_book_auto_finished(client):
    """双方都标记读完后，书籍状态应自动变为 finished"""
    ta = register_and_login(client, "open_id_finish_a")
    tb = register_and_login(client, "open_id_finish_b")
    bind_users(client, ta, tb)
    book_id = add_book(client, ta, pages=50)

    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 50, "mark_finished": True},
                headers=auth(ta))
    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 50, "mark_finished": True},
                headers=auth(tb))

    resp  = client.get("/api/v1/books?status=finished", headers=auth(ta))
    books = resp.json()["data"]["books"]
    assert any(b["book_id"] == book_id for b in books)
    finished = next(b for b in books if b["book_id"] == book_id)
    assert finished["status"] == "finished"


# ────────────────── 回复 ──────────────────

def test_reply_to_entry(client):
    ta = register_and_login(client, "open_id_reply_a")
    tb = register_and_login(client, "open_id_reply_b")
    bind_users(client, ta, tb)
    book_id = add_book(client, ta, pages=200)

    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 30, "note_content": "不错"},
                headers=auth(ta))
    # b 追上进度
    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 30},
                headers=auth(tb))

    entries  = client.get(f"/api/v1/books/{book_id}/entries", headers=auth(tb)).json()["data"]["entries"]
    a_entry  = next(e for e in entries if not e["is_mine"])
    entry_id = a_entry["entry_id"]

    resp = client.post(f"/api/v1/entries/{entry_id}/replies",
                       json={"content": "我也这么觉得"},
                       headers=auth(tb))
    assert resp.status_code == 200
    assert resp.json()["data"]["reply_id"].startswith("r_")


def test_reply_appears_in_entries(client):
    """回复后，再次拉取笔记列表，回复应出现在对应 entry 下"""
    ta = register_and_login(client, "open_id_reply_appear_a")
    tb = register_and_login(client, "open_id_reply_appear_b")
    bind_users(client, ta, tb)
    book_id = add_book(client, ta, pages=200)

    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 30, "note_content": "好句"},
                headers=auth(ta))
    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 30},
                headers=auth(tb))

    entries  = client.get(f"/api/v1/books/{book_id}/entries", headers=auth(tb)).json()["data"]["entries"]
    a_entry  = next(e for e in entries if not e["is_mine"])
    entry_id = a_entry["entry_id"]

    client.post(f"/api/v1/entries/{entry_id}/replies",
                json={"content": "深有同感"},
                headers=auth(tb))

    entries2 = client.get(f"/api/v1/books/{book_id}/entries", headers=auth(ta)).json()["data"]["entries"]
    a_entry2 = next(e for e in entries2 if e["entry_id"] == entry_id)
    assert len(a_entry2["replies"]) == 1
    assert a_entry2["replies"][0]["content"] == "深有同感"


def test_cannot_reply_locked_entry(client):
    """未追上进度时，不能回复被锁定的笔记"""
    ta = register_and_login(client, "open_id_locked_reply_a")
    tb = register_and_login(client, "open_id_locked_reply_b")
    bind_users(client, ta, tb)
    book_id = add_book(client, ta, pages=300)

    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 100, "note_content": "大结局"},
                headers=auth(tb))
    client.post("/api/v1/entries",
                json={"book_id": book_id, "page": 50},
                headers=auth(ta))

    entries  = client.get(f"/api/v1/books/{book_id}/entries", headers=auth(ta)).json()["data"]["entries"]
    b_entry  = next(e for e in entries if not e["is_mine"])
    entry_id = b_entry["entry_id"]

    resp = client.post(f"/api/v1/entries/{entry_id}/replies",
                       json={"content": "好奇"},
                       headers=auth(ta))
    assert resp.status_code == 400
    assert resp.json()["code"] == 40031
