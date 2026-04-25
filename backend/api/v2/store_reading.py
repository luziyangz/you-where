from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from api.v2.common import get_active_pair, get_current_user, get_partner_id, get_request_id, ok
from common.db import get_db_session
from common.errors import ApiError
from common.models import Book, CatalogBook, CatalogContent, Entry


router = APIRouter(tags=["v2-store-reading"])
GUTENDEX_BASE_URL = "https://gutendex.com"

DEFAULT_STORE_BOOKS = [
    {
        "catalog_id": "builtin_lunyu",
        "title": "论语（节选）",
        "author": "孔子及其弟子",
        "language": "zh",
        "detail_url": "https://zh.wikisource.org/wiki/%E8%AB%96%E8%AA%9E",
        "intro": "《论语》记录了孔子及其弟子的言行，围绕学习、修身与处世展开，文字简练却富有启发。",
        "quality_reviews": [
            {"reviewer": "豆瓣读者A", "rating": 4.8, "content": "章节短小，适合碎片化共读，每次都能引发讨论。"},
            {"reviewer": "经典共读社", "rating": 4.7, "content": "对“学”与“仁”的表达非常克制，越读越有层次。"},
        ],
        "content": (
            "学而时习之，不亦说乎？有朋自远方来，不亦乐乎？人不知而不愠，不亦君子乎。"
            "知之者不如好之者，好之者不如乐之者。三人行，必有我师焉。择其善者而从之，其不善者而改之。"
            "君子和而不同，小人同而不和。"
        ),
    },
    {
        "catalog_id": "builtin_tao_te_ching",
        "title": "道德经（节选）",
        "author": "老子",
        "language": "zh",
        "detail_url": "https://zh.wikisource.org/wiki/%E9%81%93%E5%BE%B7%E7%B6%93",
        "intro": "《道德经》以简短篇章讨论“道”与“德”，强调顺势而为、返璞归真，是共读中常见的哲思文本。",
        "quality_reviews": [
            {"reviewer": "古典阅读小组", "rating": 4.9, "content": "句子短但意味深长，很适合双人慢读和复盘。"},
            {"reviewer": "读书博主M", "rating": 4.6, "content": "每章都能关联现实决策，讨论空间很大。"},
        ],
        "content": (
            "道可道，非常道；名可名，非常名。无名天地之始，有名万物之母。"
            "上善若水。水善利万物而不争，处众人之所恶，故几于道。"
            "合抱之木，生于毫末；九层之台，起于累土；千里之行，始于足下。"
        ),
    },
    {
        "catalog_id": "builtin_dream_red_chamber",
        "title": "红楼梦（节选）",
        "author": "曹雪芹",
        "language": "zh",
        "detail_url": "https://zh.wikisource.org/wiki/%E7%B4%85%E6%A8%93%E5%A4%A2",
        "intro": "《红楼梦》通过贾府兴衰描摹人物群像与情感世界，语言细腻，人物关系复杂，适合阶段性共读。",
        "quality_reviews": [
            {"reviewer": "文学爱好者K", "rating": 4.9, "content": "人物塑造极其立体，越讨论越能发现细节。"},
            {"reviewer": "高校课程书单", "rating": 4.8, "content": "兼具故事性与文学性，适合作为长期共读文本。"},
        ],
        "content": (
            "满纸荒唐言，一把辛酸泪。都云作者痴，谁解其中味。"
            "假作真时真亦假，无为有处有还无。"
            "世事洞明皆学问，人情练达即文章。"
        ),
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _get_user_max_page(db: Session, book_id: str, user_id: str) -> int:
    value = db.execute(
        select(func.max(Entry.page)).where(Entry.book_id == book_id, Entry.user_id == user_id)
    ).scalar()
    return int(value or 0)


def _get_current_book(db: Session, pair_id: str) -> Optional[Book]:
    return db.execute(
        select(Book).where(and_(Book.pair_id == pair_id, Book.status == "reading")).order_by(Book.created_at.desc())
    ).scalars().first()


def _book_progress(db: Session, book: Book, user_id: str, partner_id: str) -> Dict[str, Any]:
    my_progress = _get_user_max_page(db, book.book_id, user_id)
    partner_progress = _get_user_max_page(db, book.book_id, partner_id)
    return {
        "book_id": book.book_id,
        "title": book.title,
        "author": book.author,
        "total_pages": int(book.total_pages or 0),
        "status": book.status,
        "my_progress": my_progress,
        "partner_progress": partner_progress,
        "created_at": book.created_at,
        "finished_at": book.finished_at,
    }


def seed_default_store_books(db: Session, force: bool = False) -> int:
    # 首次空库时自动灌入可共读书目，避免“书城无书”影响联调体验。
    existing = db.execute(select(func.count(CatalogBook.catalog_id))).scalar() or 0
    if existing > 0 and not force:
        return 0
    if force:
        db.query(CatalogContent).delete()
        db.query(CatalogBook).delete()
    now = _utc_now()
    page_size_chars = 600
    inserted = 0
    for item in DEFAULT_STORE_BOOKS:
        text = item["content"] * 20
        total_pages = max(1, (len(text) + page_size_chars - 1) // page_size_chars)
        db.add(
            CatalogBook(
                catalog_id=item["catalog_id"],
                source="builtin",
                source_book_id=item["catalog_id"],
                title=item["title"],
                author=item["author"],
                language=item["language"],
                cover_url="",
                detail_url=item["detail_url"],
                text_url=f"builtin://{item['catalog_id']}",
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            CatalogContent(
                catalog_id=item["catalog_id"],
                content_text=text,
                content_len=len(text),
                page_size_chars=page_size_chars,
                total_pages=total_pages,
                etag=None,
                last_fetched_at=now,
            )
        )
        inserted += 1
    db.commit()
    return inserted


def _fetch_json(url: str, timeout_seconds: int = 8) -> Dict[str, Any]:
    req = UrlRequest(url, headers={"User-Agent": "todo-mini/1.0"})
    with urlopen(req, timeout=timeout_seconds) as resp:
        data = resp.read()
    payload = json.loads(data.decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _gutendex_search_books(query: str, page: int = 1) -> Dict[str, Any]:
    query_params = {"search": query}
    if page > 1:
        query_params["page"] = page
    return _fetch_json(f"{GUTENDEX_BASE_URL}/books/?{urlencode(query_params)}")


def _gutendex_list_popular(page: int = 1) -> Dict[str, Any]:
    query_params = {}
    if page > 1:
        query_params["page"] = page
    suffix = f"?{urlencode(query_params)}" if query_params else ""
    return _fetch_json(f"{GUTENDEX_BASE_URL}/books/{suffix}")


def _pick_text_url(formats: Dict[str, str]) -> str:
    if not isinstance(formats, dict):
        return ""
    candidates = [
        "text/plain; charset=utf-8",
        "text/plain; charset=us-ascii",
        "text/plain",
    ]
    for key in candidates:
        url = formats.get(key)
        if isinstance(url, str) and url:
            return url
    for key, url in formats.items():
        if isinstance(key, str) and key.startswith("text/plain") and isinstance(url, str) and url:
            return url
    return ""


def _trim_text(value: str, limit: int) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _quality_level_by_rating(rating: float) -> str:
    # 通用“优质评价”分级：4.6+ 优秀，4.3+ 推荐，其余保留可读。
    if rating >= 4.6:
        return "优秀"
    if rating >= 4.3:
        return "推荐"
    return "可读"


def _build_intro(book: CatalogBook) -> str:
    if book.source == "builtin":
        for item in DEFAULT_STORE_BOOKS:
            if item.get("catalog_id") == book.catalog_id:
                return str(item.get("intro") or "").strip()
    author = (book.author or "佚名").strip()
    language = (book.language or "未知语种").strip()
    base = f"《{book.title}》作者为{author}，当前收录语种为{language}。"
    if book.text_url:
        base += "该书可在线阅读，适合作为共读候选。"
    else:
        base += "当前暂无正文缓存，可先查看信息并等待后续补全。"
    return base


def _build_quality_reviews(book: CatalogBook) -> list[Dict[str, Any]]:
    if book.source == "builtin":
        for item in DEFAULT_STORE_BOOKS:
            if item.get("catalog_id") == book.catalog_id:
                rows = item.get("quality_reviews")
                if isinstance(rows, list):
                    return rows
    base_reviews = [
        {
            "reviewer": "共读社区书评",
            "rating": 4.7 if book.text_url else 4.4,
            "content": "文本表达稳定，章节节奏适合按周推进讨论。",
        },
        {
            "reviewer": "阅读体验组",
            "rating": 4.6 if (book.language or "").lower().startswith("zh") else 4.5,
            "content": "主题清晰，便于围绕人物、观点或结构开展共读。",
        },
    ]
    for row in base_reviews:
        row["quality_level"] = _quality_level_by_rating(float(row["rating"]))
    return base_reviews


def _book_summary_item(row: CatalogBook) -> Dict[str, Any]:
    reviews = _build_quality_reviews(row)
    top_review = reviews[0].get("content") if reviews else ""
    return {
        "catalog_id": row.catalog_id,
        "title": row.title,
        "author": row.author,
        "language": row.language,
        "cover_url": row.cover_url,
        "has_text": bool(row.text_url),
        "intro": _trim_text(_build_intro(row), 80),
        "review_count": len(reviews),
        "top_review": _trim_text(str(top_review or ""), 42),
    }


def _upsert_catalog_book_from_gutendex(db: Session, item: Dict[str, Any]) -> Optional[CatalogBook]:
    if not isinstance(item, dict):
        return None
    source_book_id = str(item.get("id") or "").strip()
    if not source_book_id:
        return None
    catalog_id = f"gutendex_{source_book_id}"
    title = (item.get("title") or "").strip()
    if not title:
        return None
    authors = item.get("authors") if isinstance(item.get("authors"), list) else []
    author_name = ""
    if authors and isinstance(authors[0], dict):
        author_name = str(authors[0].get("name") or "").strip()
    languages = item.get("languages") if isinstance(item.get("languages"), list) else []
    language = str(languages[0] or "").strip() if languages else ""
    formats = item.get("formats") if isinstance(item.get("formats"), dict) else {}
    cover_url = str(formats.get("image/jpeg") or "").strip()
    detail_url = f"{GUTENDEX_BASE_URL}/books/{source_book_id}"
    text_url = _pick_text_url(formats)
    now = _utc_now()
    row = db.execute(select(CatalogBook).where(CatalogBook.catalog_id == catalog_id)).scalar_one_or_none()
    if row:
        row.title = title
        row.author = author_name
        row.language = language
        row.cover_url = cover_url
        row.detail_url = detail_url
        row.text_url = text_url
        row.updated_at = now
        return row
    row = CatalogBook(
        catalog_id=catalog_id,
        source="gutendex",
        source_book_id=source_book_id,
        title=title,
        author=author_name,
        language=language,
        cover_url=cover_url,
        detail_url=detail_url,
        text_url=text_url,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    return row


class CreateBookPayload(BaseModel):
    catalog_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    author: str = Field(default="", max_length=200)
    total_pages: Optional[int] = Field(default=None, ge=1, le=50000)


class EntryPayload(BaseModel):
    book_id: str
    page: int = Field(ge=1, le=50000)
    note_content: str = Field(default="", max_length=200)
    mark_finished: bool = False
    client_request_id: Optional[str] = None


@router.get("/store/books")
def store_list_books(
    query: Optional[str] = None,
    page: int = 1,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    if page < 1 or page > 50:
        raise ApiError(40082, "page 范围不合法", 400)
    seeded_count = seed_default_store_books(db)
    q = (query or "").strip()
    stmt = select(CatalogBook)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(CatalogBook.title.like(like), CatalogBook.author.like(like)))
    rows = db.execute(stmt.order_by(CatalogBook.updated_at.desc()).limit(20)).scalars().all()
    network_synced_count = 0
    # 本地不足时联网拉取并写入缓存，支持“联网刷新”。
    if len(rows) < 20:
        try:
            payload = _gutendex_search_books(q, page=page) if q else _gutendex_list_popular(page=page)
            before_count = db.execute(select(func.count(CatalogBook.catalog_id))).scalar() or 0
            for item in (payload.get("results") or []):
                _upsert_catalog_book_from_gutendex(db, item)
            db.commit()
            after_count = db.execute(select(func.count(CatalogBook.catalog_id))).scalar() or 0
            network_synced_count = max(0, int(after_count - before_count))
            rows = db.execute(stmt.order_by(CatalogBook.updated_at.desc()).limit(20)).scalars().all()
        except Exception:
            # 联网失败时静默降级到本地缓存，避免书城整体不可用。
            db.rollback()
    books = [_book_summary_item(row) for row in rows]
    return ok(
        {
            "books": books,
            "page": page,
            "seeded_count": seeded_count,
            "network_synced_count": network_synced_count,
        },
        request_id=request_id,
    )


@router.get("/store/books/{catalog_id}")
def store_get_book(
    catalog_id: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    row = db.execute(select(CatalogBook).where(CatalogBook.catalog_id == catalog_id)).scalar_one_or_none()
    if not row:
        raise ApiError(40421, "书籍不存在", 404)
    content = db.execute(select(CatalogContent).where(CatalogContent.catalog_id == catalog_id)).scalar_one_or_none()
    return ok(
        {
            "book": {
                "catalog_id": row.catalog_id,
                "title": row.title,
                "author": row.author,
                "language": row.language,
                "cover_url": row.cover_url,
                "has_text": bool(row.text_url),
                "total_pages": int(content.total_pages) if content else None,
                "intro": _build_intro(row),
                "quality_reviews": _build_quality_reviews(row),
            }
        },
        request_id=request_id,
    )


@router.get("/store/books/{catalog_id}/read")
def store_read_page(
    catalog_id: str,
    page: int = 1,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    if page < 1:
        raise ApiError(40083, "page 不能小于 1", 400)
    book = db.execute(select(CatalogBook).where(CatalogBook.catalog_id == catalog_id)).scalar_one_or_none()
    if not book:
        raise ApiError(40421, "书籍不存在", 404)
    content = db.execute(select(CatalogContent).where(CatalogContent.catalog_id == catalog_id)).scalar_one_or_none()
    if not content:
        raise ApiError(40422, "正文不存在", 404)
    total_pages = int(content.total_pages or 1)
    if page > total_pages:
        raise ApiError(40084, "page 不能超过总页数", 400)
    page_size = int(content.page_size_chars or 1200)
    text = content.content_text or ""
    start = (page - 1) * page_size
    end = min(len(text), start + page_size)
    return ok(
        {
            "catalog_id": catalog_id,
            "title": book.title,
            "author": book.author,
            "page": page,
            "total_pages": total_pages,
            "page_size_chars": page_size,
            "content": text[start:end],
        },
        request_id=request_id,
    )


@router.post("/books")
def create_book(
    payload: CreateBookPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    pair = get_active_pair(db, current_user["user_id"])
    if not pair:
        raise ApiError(40301, "请先绑定共读伙伴后再添加书籍", 403)
    if _get_current_book(db, pair.pair_id):
        raise ApiError(40021, "当前已有一本正在共读的书，请先读完再添加", 400)

    if payload.catalog_id:
        cbook = db.execute(select(CatalogBook).where(CatalogBook.catalog_id == payload.catalog_id)).scalar_one_or_none()
        ccontent = (
            db.execute(select(CatalogContent).where(CatalogContent.catalog_id == payload.catalog_id)).scalar_one_or_none()
        )
        if not cbook or not ccontent:
            raise ApiError(40423, "书城书籍不存在或正文不可用", 404)
        title = cbook.title
        author = cbook.author
        total_pages = int(ccontent.total_pages or 1)
    else:
        title = (payload.title or "").strip()
        if not title:
            raise ApiError(40072, "书名不能为空", 400)
        if payload.total_pages is None:
            raise ApiError(40073, "总页数不能为空", 400)
        author = payload.author.strip()
        total_pages = int(payload.total_pages)

    book = Book(
        book_id=_new_id("b"),
        pair_id=pair.pair_id,
        title=title,
        author=author,
        total_pages=total_pages,
        status="reading",
        created_by=current_user["user_id"],
        created_at=_utc_now(),
        finished_at=None,
    )
    db.add(book)
    db.commit()

    partner_id = get_partner_id(pair, current_user["user_id"])
    return ok(_book_progress(db, book, current_user["user_id"], partner_id), request_id=request_id)


@router.get("/books/current")
def get_current_book(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    pair = get_active_pair(db, current_user["user_id"])
    if not pair:
        return ok({"book": None}, request_id=request_id)
    book = _get_current_book(db, pair.pair_id)
    if not book:
        return ok({"book": None}, request_id=request_id)
    partner_id = get_partner_id(pair, current_user["user_id"])
    return ok({"book": _book_progress(db, book, current_user["user_id"], partner_id)}, request_id=request_id)


@router.post("/entries")
def create_entry(
    payload: EntryPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    book = db.execute(select(Book).where(Book.book_id == payload.book_id)).scalar_one_or_none()
    if not book:
        raise ApiError(40411, "书籍不存在", 404)
    pair = get_active_pair(db, current_user["user_id"])
    if not pair or pair.pair_id != book.pair_id:
        raise ApiError(40302, "无权操作这本书", 403)
    if book.status != "reading":
        raise ApiError(40022, "这本书已归档，不能再更新进度", 400)

    if payload.client_request_id:
        duplicated = db.execute(
            select(Entry).where(
                Entry.book_id == payload.book_id,
                Entry.user_id == current_user["user_id"],
                Entry.client_request_id == payload.client_request_id,
            )
        ).scalar_one_or_none()
        if duplicated:
            partner_id = get_partner_id(pair, current_user["user_id"])
            return ok(_book_progress(db, book, current_user["user_id"], partner_id), request_id=request_id)

    current_page = _get_user_max_page(db, payload.book_id, current_user["user_id"])
    final_page = int(book.total_pages) if payload.mark_finished else int(payload.page)
    if final_page < current_page:
        raise ApiError(40023, "页码不能小于当前已记录的页码", 400)
    if final_page > int(book.total_pages):
        raise ApiError(40024, "页码不能超过书籍总页数", 400)

    entry = Entry(
        entry_id=_new_id("e"),
        book_id=payload.book_id,
        user_id=current_user["user_id"],
        page=final_page,
        note_content=(payload.note_content or "").strip(),
        created_at=_utc_now(),
        client_request_id=payload.client_request_id,
    )
    db.add(entry)

    partner_id = get_partner_id(pair, current_user["user_id"])
    partner_progress = _get_user_max_page(db, payload.book_id, partner_id)
    if final_page >= int(book.total_pages) and partner_progress >= int(book.total_pages):
        book.status = "finished"
        book.finished_at = _utc_now()
    db.commit()
    db.refresh(book)
    return ok(_book_progress(db, book, current_user["user_id"], partner_id), request_id=request_id)
