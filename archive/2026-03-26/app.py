import hashlib
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# ─────────────────────────── 基础配置 ───────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH  = os.path.join(DATA_DIR, "app.db")

WECHAT_APP_ID     = os.getenv("WECHAT_APP_ID", "")
WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET", "")
TOKEN_EXPIRE_DAYS = 30

# ─────────────────────────── 日志 ───────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("youjinaye")

# ─────────────────────────── 简单内存限流 ────────────────────────

_rl_lock: threading.Lock = threading.Lock()
_rl_store: Dict[str, List[float]] = defaultdict(list)


def check_rate_limit(key: str, max_calls: int = 10, window_seconds: int = 60) -> bool:
    """令牌桶限流，返回 True 表示允许，False 表示超限"""
    now = time.time()
    with _rl_lock:
        bucket = _rl_store[key]
        # 移除窗口外的旧记录
        bucket[:] = [t for t in bucket if now - t < window_seconds]
        if len(bucket) >= max_calls:
            return False
        bucket.append(now)
        return True


# ─────────────────────────── 数据模型 ────────────────────────────

class ApiError(Exception):
    def __init__(self, code: int, message: str, status_code: int = 400):
        self.code       = code
        self.message    = message
        self.status_code = status_code
        super().__init__(message)


class LoginPayload(BaseModel):
    code: str = Field(..., description="wx.login 返回的临时 code")
    debug_open_id: Optional[str] = Field(None, description="本地开发使用的稳定 open_id")


class AgreementPayload(BaseModel):
    accepted: bool = True


class BindPayload(BaseModel):
    join_code: str = Field(..., min_length=6, max_length=6)


class CreateBookPayload(BaseModel):
    """
    创建共读书籍：
    - 真实书源：传 catalog_id（服务端会校验可读正文并计算总页数）
    - 兼容旧模式：手动传 title/author/total_pages
    """

    catalog_id: Optional[str] = Field(None, min_length=1, max_length=64)
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    author: str = Field("", max_length=100)
    total_pages: Optional[int] = Field(None, ge=1, le=50000)


class EntryPayload(BaseModel):
    book_id:           str
    page:              int  = Field(..., ge=1, le=50000)
    note_content:      str  = Field("", max_length=200)
    mark_finished:     bool = False
    client_request_id: Optional[str] = None


class ReplyPayload(BaseModel):
    content: str = Field(..., min_length=1, max_length=200)


class ReadEntriesPayload(BaseModel):
    last_entry_id: Optional[str] = None


# ─────────────────────────── 工具函数 ────────────────────────────

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def calc_days_since(created_at: str) -> int:
    """计算从 created_at 到今天的天数（最少返回 1）"""
    try:
        return max(1, (datetime.now(timezone.utc) - parse_time(created_at)).days + 1)
    except Exception:
        return 1


def make_request_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(6)


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # 每次新连接都启用 WAL 与内存临时表，提升并发读写性能
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    conn.execute("PRAGMA temp_store=memory")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_db() -> None:
    """初始化数据库表结构与性能索引"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_conn()
    conn.executescript(
        """
        -- ── 用户表 ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS users (
            user_id                TEXT PRIMARY KEY,
            open_id                TEXT NOT NULL UNIQUE,
            nickname               TEXT NOT NULL,
            avatar                 TEXT NOT NULL DEFAULT '',
            join_code              TEXT NOT NULL UNIQUE,
            agreement_accepted_at  TEXT,
            created_at             TEXT NOT NULL
        );

        -- ── 会话表 ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS sessions (
            token       TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            expires_at  TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        -- ── 共读关系表 ────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS pairs (
            pair_id    TEXT PRIMARY KEY,
            user_a_id  TEXT NOT NULL,
            user_b_id  TEXT NOT NULL,
            status     TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- ── 书籍表 ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS books (
            book_id     TEXT PRIMARY KEY,
            pair_id     TEXT NOT NULL,
            title       TEXT NOT NULL,
            author      TEXT NOT NULL,
            total_pages INTEGER NOT NULL,
            status      TEXT NOT NULL,
            created_by  TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            finished_at TEXT
        );

        -- ── 书城书目表（公版书源）──────────────────────────────────
        CREATE TABLE IF NOT EXISTS catalog_books (
            catalog_id     TEXT PRIMARY KEY,
            source         TEXT NOT NULL,
            source_book_id TEXT NOT NULL,
            title          TEXT NOT NULL,
            author         TEXT NOT NULL DEFAULT '',
            language       TEXT NOT NULL DEFAULT '',
            cover_url      TEXT NOT NULL DEFAULT '',
            detail_url     TEXT NOT NULL DEFAULT '',
            text_url       TEXT NOT NULL DEFAULT '',
            created_at     TEXT NOT NULL,
            updated_at     TEXT NOT NULL
        );

        -- ── 书籍正文缓存（纯文本）──────────────────────────────────
        CREATE TABLE IF NOT EXISTS catalog_contents (
            catalog_id        TEXT PRIMARY KEY,
            content_text      TEXT NOT NULL,
            content_len       INTEGER NOT NULL,
            page_size_chars   INTEGER NOT NULL,
            total_pages       INTEGER NOT NULL,
            etag              TEXT,
            last_fetched_at   TEXT NOT NULL
        );

        -- ── 阅读记录/笔记表 ──────────────────────────────────────
        CREATE TABLE IF NOT EXISTS entries (
            entry_id          TEXT PRIMARY KEY,
            book_id           TEXT NOT NULL,
            user_id           TEXT NOT NULL,
            page              INTEGER NOT NULL,
            note_content      TEXT NOT NULL,
            created_at        TEXT NOT NULL,
            client_request_id TEXT
        );

        -- ── 回复表 ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS replies (
            reply_id   TEXT PRIMARY KEY,
            entry_id   TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        -- ── 已读标记表（用于计算未读数量） ─────────────────────────
        CREATE TABLE IF NOT EXISTS read_marks (
            user_id     TEXT NOT NULL,
            book_id     TEXT NOT NULL,
            last_read_at TEXT NOT NULL,
            PRIMARY KEY (user_id, book_id)
        );

        -- ── 性能索引 ──────────────────────────────────────────────
        CREATE INDEX IF NOT EXISTS idx_sessions_token    ON sessions(token);
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id  ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_pairs_user_a      ON pairs(user_a_id, status);
        CREATE INDEX IF NOT EXISTS idx_pairs_user_b      ON pairs(user_b_id, status);
        CREATE INDEX IF NOT EXISTS idx_books_pair_status ON books(pair_id, status);
        CREATE INDEX IF NOT EXISTS idx_books_pair_created ON books(pair_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_entries_book_user ON entries(book_id, user_id);
        CREATE INDEX IF NOT EXISTS idx_entries_book_time ON entries(book_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_entries_client_req ON entries(book_id, user_id, client_request_id);
        CREATE INDEX IF NOT EXISTS idx_replies_entry     ON replies(entry_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_catalog_books_title  ON catalog_books(title);
        CREATE INDEX IF NOT EXISTS idx_catalog_books_author ON catalog_books(author);
        """
    )
    conn.commit()

    # ── 兼容迁移：为 books 表补充 catalog_id 字段（旧库上不存在时才添加） ──
    try:
        cols = conn.execute("PRAGMA table_info(books)").fetchall()
        col_names = {row["name"] for row in cols}
        if "catalog_id" not in col_names:
            conn.execute("ALTER TABLE books ADD COLUMN catalog_id TEXT")
            conn.commit()
    except Exception as exc:
        # 不阻塞启动：字段迁移失败仅记录日志
        logger.warning("books 表添加 catalog_id 失败：%s", exc)

    conn.close()
    logger.info("数据库初始化完成，路径：%s", DB_PATH)


# ─────────────────────────── 统一响应 ────────────────────────────

def ok(data: Any = None, message: str = "ok", request_id: Optional[str] = None) -> JSONResponse:
    return JSONResponse(
        {
            "code":       0,
            "message":    message,
            "data":       data if data is not None else {},
            "request_id": request_id or make_request_id(),
        }
    )


# ─────────────────────────── 数据库查询封装 ──────────────────────

def fetch_user_by_id(conn: sqlite3.Connection, user_id: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def fetch_user_by_open_id(conn: sqlite3.Connection, open_id: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM users WHERE open_id = ?", (open_id,)).fetchone()


def fetch_user_by_join_code(conn: sqlite3.Connection, join_code: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM users WHERE join_code = ?", (join_code,)).fetchone()


def row_to_user(row: sqlite3.Row) -> Dict[str, Any]:
    """将 user 数据库行转为 API 返回对象，含 join_days"""
    return {
        "user_id":                row["user_id"],
        "nickname":               row["nickname"],
        "avatar":                 row["avatar"],
        "join_code":              row["join_code"],
        "agreement_accepted_at":  row["agreement_accepted_at"],
        "join_days":              calc_days_since(row["created_at"]),
    }


def generate_join_code(conn: sqlite3.Connection) -> str:
    while True:
        join_code = str(secrets.randbelow(900000) + 100000)
        exists = conn.execute("SELECT 1 FROM users WHERE join_code = ?", (join_code,)).fetchone()
        if not exists:
            return join_code


def get_active_pair(conn: sqlite3.Connection, user_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM pairs
        WHERE status = 'active' AND (user_a_id = ? OR user_b_id = ?)
        LIMIT 1
        """,
        (user_id, user_id),
    ).fetchone()


def get_pair_partner_id(pair_row: sqlite3.Row, user_id: str) -> str:
    return pair_row["user_b_id"] if pair_row["user_a_id"] == user_id else pair_row["user_a_id"]


def get_current_book(conn: sqlite3.Connection, pair_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM books
        WHERE pair_id = ? AND status = 'reading'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (pair_id,),
    ).fetchone()


def get_user_max_page(conn: sqlite3.Connection, book_id: str, user_id: str) -> int:
    row = conn.execute(
        "SELECT MAX(page) AS max_page FROM entries WHERE book_id = ? AND user_id = ?",
        (book_id, user_id),
    ).fetchone()
    return int(row["max_page"] or 0)


def get_book_progress(
    conn: sqlite3.Connection,
    book_row: sqlite3.Row,
    current_user_id: str,
    partner_user_id: str,
) -> Dict[str, Any]:
    """返回书籍进度信息，含双人进度、百分比、进度差文案、共读天数"""
    my_page      = get_user_max_page(conn, book_row["book_id"], current_user_id)
    partner_page = get_user_max_page(conn, book_row["book_id"], partner_user_id)
    total_pages  = int(book_row["total_pages"])
    my_percent      = round(my_page / total_pages * 100, 1) if total_pages else 0
    partner_percent = round(partner_page / total_pages * 100, 1) if total_pages else 0
    delta = my_page - partner_page
    if delta == 0:
        summary = "你和伙伴进度同步中"
    elif delta > 0:
        summary = f"你领先 {delta} 页"
    else:
        summary = f"你落后 {abs(delta)} 页"

    return {
        "book_id":                 book_row["book_id"],
        "title":                   book_row["title"],
        "author":                  book_row["author"],
        "status":                  book_row["status"],
        "total_pages":             total_pages,
        "my_progress":             my_page,
        "partner_progress":        partner_page,
        "my_progress_percent":     my_percent,
        "partner_progress_percent": partner_percent,
        "progress_summary":        summary,
        "reading_days":            calc_days_since(book_row["created_at"]),
    }


def get_pair_stats(conn: sqlite3.Connection, pair_id: str) -> Dict[str, int]:
    """返回共读关系的聚合统计：共同书籍数、交流笔记数"""
    books_cnt = conn.execute(
        "SELECT COUNT(*) AS cnt FROM books WHERE pair_id = ?",
        (pair_id,),
    ).fetchone()["cnt"]
    notes_cnt = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM entries e
        JOIN books b ON e.book_id = b.book_id
        WHERE b.pair_id = ?
        """,
        (pair_id,),
    ).fetchone()["cnt"]
    return {"shared_books": int(books_cnt or 0), "shared_notes": int(notes_cnt or 0)}


def finalize_book_if_finished(
    conn: sqlite3.Connection, book_row: sqlite3.Row, pair_row: sqlite3.Row
) -> None:
    """当双方都达到总页数时，自动将书籍状态更新为 finished"""
    total_pages  = int(book_row["total_pages"])
    user_a_page  = get_user_max_page(conn, book_row["book_id"], pair_row["user_a_id"])
    user_b_page  = get_user_max_page(conn, book_row["book_id"], pair_row["user_b_id"])
    if user_a_page >= total_pages and user_b_page >= total_pages:
        conn.execute(
            "UPDATE books SET status = 'finished', finished_at = ? WHERE book_id = ?",
            (utc_now(), book_row["book_id"]),
        )
        conn.commit()
        logger.info("书籍 %s 已被双方读完，自动归档", book_row["book_id"])


# ─────────────────────────── 书城（catalog）封装 ───────────────────────────

CATALOG_SOURCE_GUTENDEX = "gutendex"
CATALOG_PAGE_SIZE_CHARS = 1200  # 阅读页 = 固定字符数分页，保证双方一致


def make_catalog_id(source: str, source_book_id: str) -> str:
    return f"{source}_{source_book_id}"


def _safe_str(value: Any, max_len: int = 200) -> str:
    s = (value or "").strip() if isinstance(value, str) else str(value or "")
    s = s.replace("\u0000", "")
    return s[:max_len]


def upsert_catalog_book_from_gutendex(conn: sqlite3.Connection, gut_book: Dict[str, Any]) -> Dict[str, Any]:
    source_book_id = str(gut_book.get("id") or "").strip()
    if not source_book_id.isdigit():
        raise ApiError(50042, "外部书源数据异常（缺少 id）", 500)

    title = _safe_str(gut_book.get("title") or "", 200)
    if not title:
        raise ApiError(50043, "外部书源数据异常（缺少 title）", 500)

    authors = gut_book.get("authors") or []
    author_name = ""
    if isinstance(authors, list) and authors:
        author_name = _safe_str((authors[0] or {}).get("name") or "", 200)

    languages = gut_book.get("languages") or []
    language = ""
    if isinstance(languages, list) and languages:
        language = _safe_str(languages[0] or "", 16)

    formats = gut_book.get("formats") or {}
    text_url = _gutendex_pick_text_url(formats if isinstance(formats, dict) else {}) or ""

    cover_url = ""
    if isinstance(formats, dict):
        cover_url = _safe_str(formats.get("image/jpeg") or "", 512)

    detail_url = f"https://www.gutenberg.org/ebooks/{source_book_id}"
    catalog_id = make_catalog_id(CATALOG_SOURCE_GUTENDEX, source_book_id)
    now = utc_now()

    conn.execute(
        """
        INSERT INTO catalog_books
        (catalog_id, source, source_book_id, title, author, language, cover_url, detail_url, text_url, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(catalog_id) DO UPDATE SET
          title=excluded.title,
          author=excluded.author,
          language=excluded.language,
          cover_url=excluded.cover_url,
          detail_url=excluded.detail_url,
          text_url=excluded.text_url,
          updated_at=excluded.updated_at
        """,
        (
            catalog_id,
            CATALOG_SOURCE_GUTENDEX,
            source_book_id,
            title,
            author_name,
            language,
            cover_url,
            detail_url,
            text_url,
            now,
            now,
        ),
    )
    conn.commit()

    return {
        "catalog_id": catalog_id,
        "source": CATALOG_SOURCE_GUTENDEX,
        "source_book_id": source_book_id,
        "title": title,
        "author": author_name,
        "language": language,
        "cover_url": cover_url,
        "detail_url": detail_url,
        "text_url": text_url,
    }


def get_catalog_book(conn: sqlite3.Connection, catalog_id: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM catalog_books WHERE catalog_id = ?", (catalog_id,)).fetchone()


def get_or_fetch_catalog_book(conn: sqlite3.Connection, catalog_id: str) -> sqlite3.Row:
    row = get_catalog_book(conn, catalog_id)
    if row:
        return row

    # 目前仅支持 gutendex_* 的 catalog_id
    if not catalog_id.startswith(f"{CATALOG_SOURCE_GUTENDEX}_"):
        raise ApiError(40431, "书城书籍不存在", 404)
    source_book_id = catalog_id.split("_", 1)[1]
    gut_book = gutendex_get_book(source_book_id)
    upsert_catalog_book_from_gutendex(conn, gut_book)
    row2 = get_catalog_book(conn, catalog_id)
    if not row2:
        raise ApiError(50044, "书城入库失败", 500)
    return row2


def get_catalog_content(conn: sqlite3.Connection, catalog_id: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM catalog_contents WHERE catalog_id = ?", (catalog_id,)).fetchone()


def cache_catalog_content(conn: sqlite3.Connection, catalog_id: str, text: str) -> sqlite3.Row:
    clean = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    clean = clean.strip("\ufeff")  # 移除 BOM（避免分页错位）
    content_len = len(clean)
    if content_len < 200:
        raise ApiError(50045, "正文内容过短，暂不支持在线阅读", 500)

    page_size = CATALOG_PAGE_SIZE_CHARS
    total_pages = max(1, (content_len + page_size - 1) // page_size)
    now = utc_now()
    conn.execute(
        """
        INSERT INTO catalog_contents
        (catalog_id, content_text, content_len, page_size_chars, total_pages, etag, last_fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(catalog_id) DO UPDATE SET
          content_text=excluded.content_text,
          content_len=excluded.content_len,
          page_size_chars=excluded.page_size_chars,
          total_pages=excluded.total_pages,
          last_fetched_at=excluded.last_fetched_at
        """,
        (catalog_id, clean, content_len, page_size, total_pages, None, now),
    )
    conn.commit()
    row = get_catalog_content(conn, catalog_id)
    if not row:
        raise ApiError(50046, "正文缓存失败", 500)
    return row


def ensure_catalog_content(conn: sqlite3.Connection, catalog_row: sqlite3.Row) -> sqlite3.Row:
    catalog_id = catalog_row["catalog_id"]
    cached = get_catalog_content(conn, catalog_id)
    if cached:
        return cached

    text_url = (catalog_row["text_url"] or "").strip()
    if not text_url:
        raise ApiError(40071, "该书暂无可用的纯文本正文链接", 400)
    text = _http_get_text(text_url, timeout_seconds=15)
    return cache_catalog_content(conn, catalog_id, text)


# ─────────────────────────── 鉴权依赖 ────────────────────────────

def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(40100, "请先登录", 401)

    token = authorization.replace("Bearer ", "", 1).strip()
    conn  = get_conn()
    session = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    if not session:
        conn.close()
        raise ApiError(40100, "登录状态已失效，请重新登录", 401)

    if parse_time(session["expires_at"]) < datetime.now(timezone.utc):
        conn.close()
        raise ApiError(40100, "登录状态已失效，请重新登录", 401)

    user = fetch_user_by_id(conn, session["user_id"])
    conn.close()
    if not user:
        raise ApiError(40401, "用户不存在", 404)
    return row_to_user(user)


def get_request_id(x_request_id: Optional[str] = Header(None)) -> str:
    return x_request_id or make_request_id()


# ─────────────────────────── 微信登录 ─────────────────────────────

def exchange_wechat_code(login_code: str, debug_open_id: Optional[str] = None) -> str:
    """换取 open_id；未配置微信密钥时走 debug 模式"""
    if not WECHAT_APP_ID or not WECHAT_APP_SECRET:
        if debug_open_id:
            return debug_open_id
        return "debug_" + hashlib.sha256(login_code.encode("utf-8")).hexdigest()[:24]

    query = urlencode(
        {
            "appid":      WECHAT_APP_ID,
            "secret":     WECHAT_APP_SECRET,
            "js_code":    login_code,
            "grant_type": "authorization_code",
        }
    )
    url = f"https://api.weixin.qq.com/sns/jscode2session?{query}"
    with urlopen(url, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    open_id = payload.get("openid")
    if not open_id:
        raise ApiError(40001, "登录凭证无效，请重试", 400)
    return open_id


# ─────────────────────────── 外部书源（Gutendex） ───────────────────────────

GUTENDEX_BASE_URL = "https://gutendex.com"


def _http_get_json(url: str, timeout_seconds: int = 12) -> Dict[str, Any]:
    req = UrlRequest(
        url,
        headers={
            # 兼容部分站点对 UA 的限制
            "User-Agent": "youzainaye/1.0 (+https://example.local)",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urlopen(req, timeout=timeout_seconds) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def _http_get_text(url: str, timeout_seconds: int = 15, max_bytes: int = 2_000_000) -> str:
    """
    拉取纯文本正文。
    - 限制体积，避免一次性拉超大文件导致内存/延迟问题
    - 优先按 UTF-8 解码；失败时退回 latin-1（尽量不炸）
    """
    req = UrlRequest(
        url,
        headers={
            "User-Agent": "youzainaye/1.0 (+https://example.local)",
            "Accept": "text/plain,*/*;q=0.8",
        },
        method="GET",
    )
    with urlopen(req, timeout=timeout_seconds) as resp:
        raw = resp.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ApiError(50041, "正文过大，暂不支持在线阅读", 500)
    try:
        return raw.decode("utf-8")
    except Exception:
        return raw.decode("latin-1", errors="replace")


def _gutendex_pick_text_url(formats: Dict[str, str]) -> Optional[str]:
    """
    从 Gutendex formats 中选择最适合的纯文本链接。
    规则：优先 text/plain（尽量避开 .zip），其次兼容带 charset 的 key。
    """
    if not formats:
        return None

    candidates: List[str] = []
    for k, v in formats.items():
        lk = (k or "").lower()
        if not v:
            continue
        if lk.startswith("text/plain"):
            candidates.append(v)

    if not candidates:
        return None

    def score(u: str) -> int:
        lu = u.lower()
        s = 0
        if ".zip" in lu:
            s -= 10
        if lu.endswith(".txt"):
            s += 3
        if "utf-8" in lu or "utf8" in lu:
            s += 1
        return s

    candidates.sort(key=score, reverse=True)
    return candidates[0]


def gutendex_search_books(query: str, page: int = 1) -> Dict[str, Any]:
    query = (query or "").strip()
    if not query:
        raise ApiError(40061, "搜索关键词不能为空", 400)
    if page < 1 or page > 50:
        raise ApiError(40062, "page 范围不合法", 400)

    params = urlencode({"search": query, "page": page})
    url = f"{GUTENDEX_BASE_URL}/books?{params}"
    return _http_get_json(url, timeout_seconds=12)


def gutendex_list_popular(page: int = 1) -> Dict[str, Any]:
    if page < 1 or page > 50:
        raise ApiError(40062, "page 范围不合法", 400)
    params = urlencode({"sort": "popular", "page": page})
    url = f"{GUTENDEX_BASE_URL}/books?{params}"
    return _http_get_json(url, timeout_seconds=12)


def gutendex_get_book(source_book_id: str) -> Dict[str, Any]:
    source_book_id = (source_book_id or "").strip()
    if not source_book_id.isdigit():
        raise ApiError(40063, "source_book_id 不合法", 400)
    url = f"{GUTENDEX_BASE_URL}/books/{source_book_id}"
    return _http_get_json(url, timeout_seconds=12)


def create_or_login_user(payload: LoginPayload) -> Dict[str, Any]:
    conn    = get_conn()
    open_id = exchange_wechat_code(payload.code, payload.debug_open_id)
    user    = fetch_user_by_open_id(conn, open_id)
    now     = utc_now()

    if not user:
        join_code = generate_join_code(conn)
        nickname  = f"书友_{join_code[-4:]}"
        user_id   = generate_id("u")
        conn.execute(
            """
            INSERT INTO users (user_id, open_id, nickname, avatar, join_code, agreement_accepted_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, open_id, nickname, "", join_code, None, now),
        )
        conn.commit()
        user = fetch_user_by_open_id(conn, open_id)
        logger.info("新用户注册 user_id=%s", user_id)

    token      = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)).replace(microsecond=0)
    conn.execute(
        """
        INSERT INTO sessions (token, user_id, expires_at, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (token, user["user_id"], expires_at.isoformat().replace("+00:00", "Z"), now),
    )
    conn.commit()
    data = {
        "token":          token,
        "user":           row_to_user(user),
        "need_agreement": user["agreement_accepted_at"] is None,
    }
    conn.close()
    return data


# ─────────────────────────── FastAPI 应用 ────────────────────────

@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    ensure_db()
    logger.info("你在哪页后端服务启动完成")
    yield


app = FastAPI(title="你在哪页 后端服务", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_and_time_requests(request: Request, call_next):
    """记录每个请求的路径、方法、状态码和耗时"""
    start    = time.time()
    response = await call_next(request)
    elapsed  = round((time.time() - start) * 1000, 1)
    logger.info(
        "method=%s path=%s status=%d latency_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code":       exc.code,
            "message":    exc.message,
            "data":       {},
            "request_id": make_request_id(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("未捕获异常: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "code":       50000,
            "message":    "服务开小差了，请稍后再试",
            "data":       {},
            "request_id": make_request_id(),
        },
    )


# ─────────────────────────── API 端点 ────────────────────────────

@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok", "version": "1.1.0"}


@app.post("/api/v1/auth/login")
def login(
    payload:    LoginPayload,
    request:    Request,
    request_id: str = Depends(get_request_id),
) -> JSONResponse:
    # 对登录接口做速率限制：同一 IP 每分钟最多 20 次
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"login:{client_ip}", max_calls=20, window_seconds=60):
        raise ApiError(42900, "操作过于频繁，请稍后再试", 429)
    return ok(create_or_login_user(payload), request_id=request_id)


@app.post("/api/v1/auth/accept-agreement")
def accept_agreement(
    payload:      AgreementPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    if not payload.accepted:
        raise ApiError(40002, "请勾选并同意协议后继续", 400)

    conn = get_conn()
    conn.execute(
        "UPDATE users SET agreement_accepted_at = ? WHERE user_id = ?",
        (utc_now(), current_user["user_id"]),
    )
    conn.commit()
    user = fetch_user_by_id(conn, current_user["user_id"])
    conn.close()
    return ok({"user": row_to_user(user)}, request_id=request_id)


@app.get("/api/v1/me")
def get_me(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    """返回当前用户信息，含 join_days"""
    return ok(current_user, request_id=request_id)


@app.get("/api/v1/me/stats")
def get_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    """返回个人统计：已读完本数、总页数、总笔记条数、共读天数"""
    conn = get_conn()

    finished_books = conn.execute(
        """
        SELECT COUNT(DISTINCT b.book_id) AS total_books
        FROM books b
        JOIN pairs p ON p.pair_id = b.pair_id
        WHERE b.status = 'finished' AND (p.user_a_id = ? OR p.user_b_id = ?)
        """,
        (current_user["user_id"], current_user["user_id"]),
    ).fetchone()

    page_rows = conn.execute(
        """
        SELECT book_id, MAX(page) AS max_page
        FROM entries
        WHERE user_id = ?
        GROUP BY book_id
        """,
        (current_user["user_id"],),
    ).fetchall()
    total_pages = sum(int(row["max_page"] or 0) for row in page_rows)

    entries_count = conn.execute(
        "SELECT COUNT(*) AS total_entries FROM entries WHERE user_id = ?",
        (current_user["user_id"],),
    ).fetchone()

    # 取用户注册时间计算共读天数
    user_row   = conn.execute(
        "SELECT created_at FROM users WHERE user_id = ?",
        (current_user["user_id"],),
    ).fetchone()
    total_days = calc_days_since(user_row["created_at"]) if user_row else 1

    conn.close()

    return ok(
        {
            "total_books":   int(finished_books["total_books"] or 0),
            "total_pages":   total_pages,
            "total_entries": int(entries_count["total_entries"] or 0),
            "total_days":    total_days,
        },
        request_id=request_id,
    )


@app.get("/api/v1/home")
def get_home(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    """首页聚合接口：user + pair（含伙伴信息和配对统计）+ current_book"""
    conn   = get_conn()
    pair   = get_active_pair(conn, current_user["user_id"])
    result: Dict[str, Any] = {
        "user":         current_user,
        "pair":         None,
        "current_book": None,
    }
    if pair:
        partner_id = get_pair_partner_id(pair, current_user["user_id"])
        partner    = fetch_user_by_id(conn, partner_id)
        stats      = get_pair_stats(conn, pair["pair_id"])
        result["pair"] = {
            "pair_id":      pair["pair_id"],
            "status":       pair["status"],
            "bind_days":    calc_days_since(pair["created_at"]),
            "partner": {
                "user_id":  partner["user_id"],
                "nickname": partner["nickname"],
                "avatar":   partner["avatar"],
                "join_code": partner["join_code"],
            },
            **stats,
        }
        current_book = get_current_book(conn, pair["pair_id"])
        if current_book:
            result["current_book"] = get_book_progress(conn, current_book, current_user["user_id"], partner_id)
    conn.close()
    return ok(result, request_id=request_id)


@app.get("/api/v1/pair/current")
def get_current_pair(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    """获取当前共读关系，含伙伴信息、配对统计和当前书籍进度"""
    conn = get_conn()
    pair = get_active_pair(conn, current_user["user_id"])
    if not pair:
        conn.close()
        return ok({"pair": None}, request_id=request_id)

    partner_id   = get_pair_partner_id(pair, current_user["user_id"])
    partner      = fetch_user_by_id(conn, partner_id)
    stats        = get_pair_stats(conn, pair["pair_id"])
    current_book = get_current_book(conn, pair["pair_id"])

    pair_data: Dict[str, Any] = {
        "pair_id":   pair["pair_id"],
        "status":    pair["status"],
        "bind_days": calc_days_since(pair["created_at"]),
        "partner": {
            "user_id":  partner["user_id"],
            "nickname": partner["nickname"],
            "avatar":   partner["avatar"],
            "join_code": partner["join_code"],
        },
        **stats,
    }
    if current_book:
        pair_data["current_book"] = get_book_progress(
            conn, current_book, current_user["user_id"], partner_id
        )
    else:
        pair_data["current_book"] = None

    conn.close()
    return ok({"pair": pair_data}, request_id=request_id)


@app.post("/api/v1/pair/bind")
def bind_pair(
    payload:      BindPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request:      Request         = None,
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    """通过 6 位共读码绑定伙伴"""
    conn = get_conn()
    if payload.join_code == current_user["join_code"]:
        conn.close()
        raise ApiError(40013, "不能与自己绑定", 400)

    target_user = fetch_user_by_join_code(conn, payload.join_code)
    if not target_user:
        conn.close()
        raise ApiError(40011, "未找到对应用户，请确认对方共读码是否正确", 400)

    current_pair = get_active_pair(conn, current_user["user_id"])
    target_pair  = get_active_pair(conn, target_user["user_id"])
    if current_pair:
        conn.close()
        raise ApiError(40012, "你已与其他伙伴共读，请先解绑再绑定新伙伴", 400)
    if target_pair:
        conn.close()
        raise ApiError(40012, "对方已与其他伙伴共读，无法绑定", 400)

    pair_id = generate_id("p")
    now     = utc_now()
    conn.execute(
        """
        INSERT INTO pairs (pair_id, user_a_id, user_b_id, status, created_at, updated_at)
        VALUES (?, ?, ?, 'active', ?, ?)
        """,
        (pair_id, current_user["user_id"], target_user["user_id"], now, now),
    )
    conn.commit()
    logger.info(
        "绑定成功 pair_id=%s user_a=%s user_b=%s",
        pair_id, current_user["user_id"], target_user["user_id"],
    )
    conn.close()
    return ok(
        {
            "pair_id":   pair_id,
            "status":    "active",
            "bind_days": 1,
            "partner": {
                "user_id":  target_user["user_id"],
                "nickname": target_user["nickname"],
                "avatar":   target_user["avatar"],
            },
            "shared_books": 0,
            "shared_notes": 0,
        },
        request_id=request_id,
    )


@app.post("/api/v1/pair/unbind")
def unbind_pair(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    conn = get_conn()
    pair = get_active_pair(conn, current_user["user_id"])
    if not pair:
        conn.close()
        raise ApiError(40402, "当前没有可解绑的共读关系", 404)

    conn.execute(
        "UPDATE pairs SET status = 'unbound', updated_at = ? WHERE pair_id = ?",
        (utc_now(), pair["pair_id"]),
    )
    conn.commit()
    logger.info("解绑 pair_id=%s by user=%s", pair["pair_id"], current_user["user_id"])
    conn.close()
    return ok({"pair_id": pair["pair_id"], "status": "unbound"}, request_id=request_id)


@app.post("/api/v1/books")
def create_book(
    payload:      CreateBookPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    conn = get_conn()
    pair = get_active_pair(conn, current_user["user_id"])
    if not pair:
        conn.close()
        raise ApiError(40301, "请先绑定共读伙伴后再添加书籍", 403)

    current_book = get_current_book(conn, pair["pair_id"])
    if current_book:
        conn.close()
        raise ApiError(40021, "当前已有一本正在共读的书，请先读完再添加", 400)

    book_id = generate_id("b")
    now     = utc_now()
    catalog_id: Optional[str] = (payload.catalog_id or "").strip() or None

    # 真实书源模式：必须可拉取正文并分页成功，才能创建共读书（避免“随便加假书”）
    if catalog_id:
        catalog_row = get_or_fetch_catalog_book(conn, catalog_id)
        content_row = ensure_catalog_content(conn, catalog_row)
        title = (catalog_row["title"] or "").strip()
        author = (catalog_row["author"] or "").strip()
        total_pages = int(content_row["total_pages"] or 1)
        if not title or total_pages < 1:
            conn.close()
            raise ApiError(50047, "书源数据异常，无法创建共读书", 500)

        conn.execute(
            """
            INSERT INTO books (book_id, pair_id, title, author, total_pages, status, created_by, created_at, catalog_id)
            VALUES (?, ?, ?, ?, ?, 'reading', ?, ?, ?)
            """,
            (book_id, pair["pair_id"], title, author, total_pages, current_user["user_id"], now, catalog_id),
        )
    else:
        # 兼容旧模式：手动输入
        title = (payload.title or "").strip()
        if not title:
            conn.close()
            raise ApiError(40072, "书名不能为空", 400)
        if payload.total_pages is None:
            conn.close()
            raise ApiError(40073, "总页数不能为空", 400)

        conn.execute(
            """
            INSERT INTO books (book_id, pair_id, title, author, total_pages, status, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, 'reading', ?, ?)
            """,
            (book_id, pair["pair_id"], title, payload.author.strip(), int(payload.total_pages), current_user["user_id"], now),
        )
    conn.commit()
    book       = conn.execute("SELECT * FROM books WHERE book_id = ?", (book_id,)).fetchone()
    partner_id = get_pair_partner_id(pair, current_user["user_id"])
    data       = get_book_progress(conn, book, current_user["user_id"], partner_id)
    conn.close()
    logger.info("添加书籍 book_id=%s title=%s pair_id=%s", book_id, data["title"], pair["pair_id"])
    return ok(data, request_id=request_id)


@app.get("/api/v1/books/current")
def get_reading_book(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    conn = get_conn()
    pair = get_active_pair(conn, current_user["user_id"])
    if not pair:
        conn.close()
        return ok({"book": None}, request_id=request_id)

    book = get_current_book(conn, pair["pair_id"])
    if not book:
        conn.close()
        return ok({"book": None}, request_id=request_id)

    partner_id = get_pair_partner_id(pair, current_user["user_id"])
    data       = get_book_progress(conn, book, current_user["user_id"], partner_id)
    conn.close()
    return ok({"book": data}, request_id=request_id)


@app.get("/api/v1/books")
def list_books(
    status:       Optional[str]    = None,
    current_user: Dict[str, Any]   = Depends(get_current_user),
    request_id:   str               = Depends(get_request_id),
) -> JSONResponse:
    conn = get_conn()
    pair = get_active_pair(conn, current_user["user_id"])
    if not pair:
        conn.close()
        return ok({"books": []}, request_id=request_id)

    params: List[Any] = [pair["pair_id"]]
    sql = "SELECT * FROM books WHERE pair_id = ?"
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"

    rows       = conn.execute(sql, tuple(params)).fetchall()
    partner_id = get_pair_partner_id(pair, current_user["user_id"])
    books      = [get_book_progress(conn, row, current_user["user_id"], partner_id) for row in rows]
    conn.close()
    return ok({"books": books}, request_id=request_id)


# ─────────────────────────── 书城 & 在线翻阅（公版书） ───────────────────────────

@app.get("/api/v1/store/books")
def store_list_books(
    query: Optional[str] = None,
    page: int = 1,
    request_id: str = Depends(get_request_id),
) -> JSONResponse:
    """
    书城搜索（公版书）：返回可用于详情与阅读的 catalog_id。
    - 本地库优先：优先从 catalog_books 模糊搜索
    - 不足时：调用 Gutendex 补齐并写回本地库
    """
    q = (query or "").strip()
    if page < 1 or page > 50:
        raise ApiError(40082, "page 范围不合法", 400)

    conn = get_conn()

    # 1) 本地命中：有 query 则模糊搜索；无 query 则给最近缓存/热门
    if q:
        like = f"%{q}%"
        local_rows = conn.execute(
            """
            SELECT * FROM catalog_books
            WHERE title LIKE ? OR author LIKE ?
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            (like, like),
        ).fetchall()
    else:
        local_rows = conn.execute(
            """
            SELECT * FROM catalog_books
            ORDER BY updated_at DESC
            LIMIT 20
            """
        ).fetchall()

    books: List[Dict[str, Any]] = []
    seen: set = set()
    for row in local_rows:
        seen.add(row["catalog_id"])
        books.append(
            {
                "catalog_id": row["catalog_id"],
                "title": row["title"],
                "author": row["author"],
                "language": row["language"],
                "cover_url": row["cover_url"],
                "detail_url": row["detail_url"],
                "has_text": bool(row["text_url"]),
            }
        )

    # 2) 外部补齐（兜底）：有 query 走搜索；无 query 拉热门
    if len(books) < 20:
        try:
            payload = gutendex_search_books(q, page=page) if q else gutendex_list_popular(page=page)
            results = payload.get("results") or []
            if isinstance(results, list):
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    cat = upsert_catalog_book_from_gutendex(conn, item)
                    if cat["catalog_id"] in seen:
                        continue
                    seen.add(cat["catalog_id"])
                    books.append(
                        {
                            "catalog_id": cat["catalog_id"],
                            "title": cat["title"],
                            "author": cat["author"],
                            "language": cat["language"],
                            "cover_url": cat["cover_url"],
                            "detail_url": cat["detail_url"],
                            "has_text": bool(cat["text_url"]),
                        }
                    )
                    if len(books) >= 20:
                        break
        except ApiError:
            # 外部失败不影响本地命中（降级）
            pass
        except Exception as exc:
            logger.warning("书城外部搜索失败: %s", exc)

    conn.close()
    return ok({"books": books, "page": page}, request_id=request_id)


@app.get("/api/v1/store/books/{catalog_id}")
def store_get_book(
    catalog_id: str,
    request_id: str = Depends(get_request_id),
) -> JSONResponse:
    conn = get_conn()
    row = get_or_fetch_catalog_book(conn, catalog_id)
    content = get_catalog_content(conn, catalog_id)
    conn.close()
    return ok(
        {
            "book": {
                "catalog_id": row["catalog_id"],
                "title": row["title"],
                "author": row["author"],
                "language": row["language"],
                "cover_url": row["cover_url"],
                "detail_url": row["detail_url"],
                "has_text": bool(row["text_url"]),
                "total_pages": int(content["total_pages"]) if content else None,
            }
        },
        request_id=request_id,
    )


@app.get("/api/v1/store/books/{catalog_id}/read")
def store_read_page(
    catalog_id: str,
    page: int = 1,
    request_id: str = Depends(get_request_id),
) -> JSONResponse:
    if page < 1:
        raise ApiError(40083, "page 不能小于 1", 400)

    conn = get_conn()
    catalog_row = get_or_fetch_catalog_book(conn, catalog_id)
    content_row = ensure_catalog_content(conn, catalog_row)
    total_pages = int(content_row["total_pages"])
    page_size = int(content_row["page_size_chars"])

    if page > total_pages:
        conn.close()
        raise ApiError(40084, "page 不能超过总页数", 400)

    text = content_row["content_text"]
    start = (page - 1) * page_size
    end = min(len(text), start + page_size)
    snippet = text[start:end]

    conn.close()
    return ok(
        {
            "catalog_id": catalog_id,
            "title": catalog_row["title"],
            "author": catalog_row["author"],
            "page": page,
            "total_pages": total_pages,
            "page_size_chars": page_size,
            "content": snippet,
        },
        request_id=request_id,
    )


@app.post("/api/v1/entries")
def create_entry(
    payload:      EntryPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    conn = get_conn()
    book = conn.execute("SELECT * FROM books WHERE book_id = ?", (payload.book_id,)).fetchone()
    if not book:
        conn.close()
        raise ApiError(40411, "书籍不存在", 404)

    pair = get_active_pair(conn, current_user["user_id"])
    if not pair or pair["pair_id"] != book["pair_id"]:
        conn.close()
        raise ApiError(40302, "无权操作这本书", 403)

    if book["status"] != "reading":
        conn.close()
        raise ApiError(40022, "这本书已归档，不能再更新进度", 400)

    # 幂等性检查：防止网络重试导致重复提交
    if payload.client_request_id:
        duplicated = conn.execute(
            """
            SELECT * FROM entries
            WHERE book_id = ? AND user_id = ? AND client_request_id = ?
            LIMIT 1
            """,
            (payload.book_id, current_user["user_id"], payload.client_request_id),
        ).fetchone()
        if duplicated:
            partner_id = get_pair_partner_id(pair, current_user["user_id"])
            data       = get_book_progress(conn, book, current_user["user_id"], partner_id)
            conn.close()
            return ok(data, request_id=request_id)

    current_page = get_user_max_page(conn, payload.book_id, current_user["user_id"])
    final_page   = int(book["total_pages"]) if payload.mark_finished else payload.page

    if final_page < current_page:
        conn.close()
        raise ApiError(40023, "页码不能小于当前已记录的页码", 400)
    if final_page > int(book["total_pages"]):
        conn.close()
        raise ApiError(40024, "页码不能超过书籍总页数", 400)

    entry_id = generate_id("e")
    conn.execute(
        """
        INSERT INTO entries (entry_id, book_id, user_id, page, note_content, created_at, client_request_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry_id,
            payload.book_id,
            current_user["user_id"],
            final_page,
            payload.note_content.strip(),
            utc_now(),
            payload.client_request_id,
        ),
    )
    conn.commit()
    finalize_book_if_finished(conn, book, pair)
    refreshed_book = conn.execute("SELECT * FROM books WHERE book_id = ?", (payload.book_id,)).fetchone()
    partner_id     = get_pair_partner_id(pair, current_user["user_id"])
    data           = get_book_progress(conn, refreshed_book, current_user["user_id"], partner_id)
    conn.close()
    return ok(data, request_id=request_id)


@app.get("/api/v1/books/{book_id}/entries")
def get_book_entries(
    book_id:      str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    """获取书籍笔记列表，含锁定状态、未读计数、作者头像"""
    conn = get_conn()
    book = conn.execute("SELECT * FROM books WHERE book_id = ?", (book_id,)).fetchone()
    if not book:
        conn.close()
        raise ApiError(40411, "书籍不存在", 404)

    pair = get_active_pair(conn, current_user["user_id"])
    if not pair or pair["pair_id"] != book["pair_id"]:
        conn.close()
        raise ApiError(40302, "无权查看这本书", 403)

    partner_id      = get_pair_partner_id(pair, current_user["user_id"])
    my_progress     = get_user_max_page(conn, book_id, current_user["user_id"])
    partner_progress = get_user_max_page(conn, book_id, partner_id)

    rows = conn.execute(
        """
        SELECT * FROM entries
        WHERE book_id = ?
        ORDER BY created_at DESC
        """,
        (book_id,),
    ).fetchall()

    last_read_row = conn.execute(
        "SELECT last_read_at FROM read_marks WHERE user_id = ? AND book_id = ?",
        (current_user["user_id"], book_id),
    ).fetchone()
    last_read_at = last_read_row["last_read_at"] if last_read_row else None

    unread_count = 0
    entries: List[Dict[str, Any]] = []
    for row in rows:
        author    = fetch_user_by_id(conn, row["user_id"])
        is_locked = row["user_id"] != current_user["user_id"] and int(row["page"]) > my_progress

        if last_read_at and row["user_id"] != current_user["user_id"] and parse_time(row["created_at"]) > parse_time(last_read_at):
            unread_count += 1
        elif not last_read_at and row["user_id"] != current_user["user_id"]:
            unread_count += 1

        reply_rows = conn.execute(
            "SELECT * FROM replies WHERE entry_id = ? ORDER BY created_at ASC",
            (row["entry_id"],),
        ).fetchall()
        replies: List[Dict[str, Any]] = []
        if not is_locked:
            for reply_row in reply_rows:
                reply_author = fetch_user_by_id(conn, reply_row["user_id"])
                replies.append(
                    {
                        "reply_id":  reply_row["reply_id"],
                        "user_id":   reply_row["user_id"],
                        "nickname":  reply_author["nickname"] if reply_author else "书友",
                        "avatar":    reply_author["avatar"]   if reply_author else "",
                        "content":   reply_row["content"],
                        "created_at": reply_row["created_at"],
                    }
                )

        entries.append(
            {
                "entry_id":      row["entry_id"],
                "user_id":       row["user_id"],
                "nickname":      author["nickname"] if author else "书友",
                "avatar":        author["avatar"]   if author else "",
                "page":          row["page"],
                "note_content":  None if is_locked else row["note_content"],
                "is_locked":     is_locked,
                "unlock_at_page": row["page"] if is_locked else None,
                "created_at":    row["created_at"],
                "replies":       replies,
                "is_mine":       row["user_id"] == current_user["user_id"],
            }
        )

    # 更新已读标记，重置未读计数
    conn.execute(
        """
        INSERT INTO read_marks (user_id, book_id, last_read_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, book_id) DO UPDATE SET last_read_at = excluded.last_read_at
        """,
        (current_user["user_id"], book_id, utc_now()),
    )
    conn.commit()
    conn.close()

    return ok(
        {
            "book_id":          book_id,
            "my_progress":      my_progress,
            "partner_progress": partner_progress,
            "unread_count":     unread_count,
            "entries":          entries,
        },
        request_id=request_id,
    )


@app.post("/api/v1/books/{book_id}/entries/read")
def mark_book_entries_read(
    book_id:       str,
    payload:       ReadEntriesPayload,
    current_user:  Dict[str, Any] = Depends(get_current_user),
    request_id:    str             = Depends(get_request_id),
) -> JSONResponse:
    """显式标记书籍笔记已读（供小程序前端同步未读状态）"""
    conn = get_conn()
    book = conn.execute("SELECT * FROM books WHERE book_id = ?", (book_id,)).fetchone()
    if not book:
        conn.close()
        raise ApiError(40411, "书籍不存在", 404)

    pair = get_active_pair(conn, current_user["user_id"])
    if not pair or pair["pair_id"] != book["pair_id"]:
        conn.close()
        raise ApiError(40302, "无权操作这本书", 403)

    target_time = utc_now()
    if payload.last_entry_id:
        row = conn.execute(
            """
            SELECT created_at FROM entries
            WHERE entry_id = ? AND book_id = ?
            LIMIT 1
            """,
            (payload.last_entry_id, book_id),
        ).fetchone()
        if row:
            target_time = row["created_at"]

    conn.execute(
        """
        INSERT INTO read_marks (user_id, book_id, last_read_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, book_id) DO UPDATE SET last_read_at = excluded.last_read_at
        """,
        (current_user["user_id"], book_id, target_time),
    )
    conn.commit()
    conn.close()
    return ok({"book_id": book_id, "last_read_at": target_time}, request_id=request_id)


@app.post("/api/v1/entries/{entry_id}/replies")
def reply_entry(
    entry_id:     str,
    payload:      ReplyPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id:   str             = Depends(get_request_id),
) -> JSONResponse:
    conn  = get_conn()
    entry = conn.execute("SELECT * FROM entries WHERE entry_id = ?", (entry_id,)).fetchone()
    if not entry:
        conn.close()
        raise ApiError(40412, "笔记不存在", 404)

    book = conn.execute("SELECT * FROM books WHERE book_id = ?", (entry["book_id"],)).fetchone()
    pair = get_active_pair(conn, current_user["user_id"])
    if not pair or pair["pair_id"] != book["pair_id"]:
        conn.close()
        raise ApiError(40303, "无权回复这条笔记", 403)

    my_progress = get_user_max_page(conn, entry["book_id"], current_user["user_id"])
    if entry["user_id"] != current_user["user_id"] and int(entry["page"]) > my_progress:
        conn.close()
        raise ApiError(40031, "这条笔记还未解锁，暂时不能回复", 400)

    reply_id = generate_id("r")
    conn.execute(
        """
        INSERT INTO replies (reply_id, entry_id, user_id, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (reply_id, entry_id, current_user["user_id"], payload.content.strip(), utc_now()),
    )
    conn.commit()
    conn.close()
    return ok({"reply_id": reply_id}, request_id=request_id)
