from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from api.v2.common import calc_days_since, get_active_pair, get_current_user, get_partner_id, get_request_id, ok
from common.db import get_db_session
from common.errors import ApiError
from common.models import Book, Entry, Pair, ReadMark, Reply, SessionModel, User


router = APIRouter(tags=["v2-core-reading"])


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _token() -> str:
    return f"tk_{secrets.token_hex(24)}"


def _join_code(seed: str) -> str:
    number = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % 900000 + 100000
    return str(number)


def _user_dict(user: User) -> Dict[str, Any]:
    return {
        "user_id": user.user_id,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "join_code": user.join_code,
        "agreement_accepted_at": user.agreement_accepted_at,
        "join_days": calc_days_since(user.created_at),
    }


def _pair_stats(db: Session, pair_id: str) -> Dict[str, int]:
    shared_books = db.execute(select(func.count(Book.book_id)).where(Book.pair_id == pair_id)).scalar() or 0
    shared_notes = (
        db.execute(select(func.count(Entry.entry_id)).join(Book, Book.book_id == Entry.book_id).where(Book.pair_id == pair_id)).scalar()
        or 0
    )
    return {"shared_books": int(shared_books), "shared_notes": int(shared_notes)}


def _user_max_page(db: Session, book_id: str, user_id: str) -> int:
    value = db.execute(select(func.max(Entry.page)).where(Entry.book_id == book_id, Entry.user_id == user_id)).scalar()
    return int(value or 0)


def _current_book(db: Session, pair_id: str) -> Optional[Book]:
    return db.execute(select(Book).where(and_(Book.pair_id == pair_id, Book.status == "reading")).order_by(desc(Book.created_at))).scalars().first()


def _book_progress(db: Session, book: Book, user_id: str, partner_id: str) -> Dict[str, Any]:
    my_progress = _user_max_page(db, book.book_id, user_id)
    partner_progress = _user_max_page(db, book.book_id, partner_id)
    return {
        "book_id": book.book_id,
        "title": book.title,
        "author": book.author,
        "total_pages": int(book.total_pages or 0),
        "status": book.status,
        "my_progress": my_progress,
        "partner_progress": partner_progress,
        "reading_days": calc_days_since(book.created_at),
        "created_at": book.created_at,
        "finished_at": book.finished_at,
    }


class LoginPayload(BaseModel):
    code: str
    debug_open_id: Optional[str] = None


class AgreementPayload(BaseModel):
    accepted: bool = True


class BindPayload(BaseModel):
    join_code: str = Field(min_length=6, max_length=6)


class ReadEntriesPayload(BaseModel):
    last_entry_id: Optional[str] = None


class ReplyPayload(BaseModel):
    content: str = Field(min_length=1, max_length=200)


class UpdateMePayload(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)


@router.post("/auth/login")
def login(
    payload: LoginPayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    open_id = (payload.debug_open_id or "").strip() or f"wx_{hashlib.md5(payload.code.encode('utf-8')).hexdigest()}"
    user = db.execute(select(User).where(User.open_id == open_id)).scalar_one_or_none()
    if not user:
        now = _utc_now()
        user = User(
            user_id=_new_id("u"),
            open_id=open_id,
            nickname=f"书友_{open_id[-4:]}",
            avatar="",
            join_code=_join_code(open_id + now),
            agreement_accepted_at=None,
            created_at=now,
        )
        db.add(user)
        db.flush()

    token = _token()
    session = SessionModel(
        token=token,
        user_id=user.user_id,
        created_at=_utc_now(),
        expires_at=(datetime.now(timezone.utc) + timedelta(days=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    db.add(session)
    db.commit()
    data_user = _user_dict(user)
    return ok(
        {
            "token": token,
            "user": data_user,
            "need_agreement": not bool(user.agreement_accepted_at),
        },
        request_id=request_id,
    )


@router.post("/auth/accept-agreement")
def accept_agreement(
    payload: AgreementPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    if not payload.accepted:
        raise ApiError(40002, "请勾选并同意协议后继续", 400)
    user = db.execute(select(User).where(User.user_id == current_user["user_id"])).scalar_one_or_none()
    if not user:
        raise ApiError(40100, "登录状态已失效，请重新登录", 401)
    user.agreement_accepted_at = _utc_now()
    db.commit()
    return ok({"user": _user_dict(user)}, request_id=request_id)


@router.get("/me")
def me(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    return ok(current_user, request_id=request_id)


@router.put("/me")
def update_me(
    payload: UpdateMePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    nickname = (payload.nickname or "").strip()
    if not nickname:
        raise ApiError(40090, "昵称不能为空", 400)
    user = db.execute(select(User).where(User.user_id == current_user["user_id"])).scalar_one_or_none()
    if not user:
        raise ApiError(40100, "登录状态已失效，请重新登录", 401)
    user.nickname = nickname
    db.commit()
    return ok({"user": _user_dict(user)}, request_id=request_id)


@router.get("/me/stats")
def me_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    user_id = current_user["user_id"]
    pair_ids = db.execute(
        select(Pair.pair_id).where(Pair.status.in_(["active", "unbound"]), or_(Pair.user_a_id == user_id, Pair.user_b_id == user_id))
    ).scalars().all()

    total_books = 0
    if pair_ids:
        total_books = db.execute(
            select(func.count(Book.book_id)).where(and_(Book.pair_id.in_(pair_ids), Book.status == "finished"))
        ).scalar() or 0
    page_rows = db.execute(
        select(Entry.book_id, func.max(Entry.page).label("max_page")).where(Entry.user_id == user_id).group_by(Entry.book_id)
    ).all()
    total_pages = sum(int(row.max_page or 0) for row in page_rows)
    total_entries = db.execute(select(func.count(Entry.entry_id)).where(Entry.user_id == user_id)).scalar() or 0
    return ok(
        {
            "total_books": int(total_books),
            "total_pages": int(total_pages),
            "total_entries": int(total_entries),
            "total_days": calc_days_since(current_user.get("created_at", "")),
        },
        request_id=request_id,
    )


@router.get("/home")
def home(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    pair = get_active_pair(db, current_user["user_id"])
    result: Dict[str, Any] = {"user": current_user, "pair": None, "current_book": None}
    if not pair:
        return ok(result, request_id=request_id)

    partner_id = get_partner_id(pair, current_user["user_id"])
    partner = db.execute(select(User).where(User.user_id == partner_id)).scalar_one_or_none()
    stats = _pair_stats(db, pair.pair_id)
    result["pair"] = {
        "pair_id": pair.pair_id,
        "status": pair.status,
        "bind_days": calc_days_since(pair.created_at),
        "partner": {
            "user_id": partner.user_id if partner else "",
            "nickname": partner.nickname if partner else "书友",
            "avatar": partner.avatar if partner else "",
            "join_code": partner.join_code if partner else "",
        },
        **stats,
    }
    book = _current_book(db, pair.pair_id)
    if book:
        result["current_book"] = _book_progress(db, book, current_user["user_id"], partner_id)
    return ok(result, request_id=request_id)


@router.get("/pair/current")
def pair_current(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    pair = get_active_pair(db, current_user["user_id"])
    if not pair:
        return ok({"pair": None}, request_id=request_id)
    partner_id = get_partner_id(pair, current_user["user_id"])
    partner = db.execute(select(User).where(User.user_id == partner_id)).scalar_one_or_none()
    stats = _pair_stats(db, pair.pair_id)
    data: Dict[str, Any] = {
        "pair_id": pair.pair_id,
        "status": pair.status,
        "bind_days": calc_days_since(pair.created_at),
        "partner": {
            "user_id": partner.user_id if partner else "",
            "nickname": partner.nickname if partner else "书友",
            "avatar": partner.avatar if partner else "",
            "join_code": partner.join_code if partner else "",
        },
        **stats,
    }
    book = _current_book(db, pair.pair_id)
    data["current_book"] = _book_progress(db, book, current_user["user_id"], partner_id) if book else None
    return ok({"pair": data}, request_id=request_id)


@router.post("/pair/bind")
def pair_bind(
    payload: BindPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    if payload.join_code == current_user["join_code"]:
        raise ApiError(40013, "不能与自己绑定", 400)
    target = db.execute(select(User).where(User.join_code == payload.join_code)).scalar_one_or_none()
    if not target:
        raise ApiError(40011, "未找到对应用户，请确认对方共读码是否正确", 400)
    if get_active_pair(db, current_user["user_id"]):
        raise ApiError(40012, "你已与其他伙伴共读，请先解绑再绑定新伙伴", 400)
    if get_active_pair(db, target.user_id):
        raise ApiError(40012, "对方已与其他伙伴共读，无法绑定", 400)

    now = _utc_now()
    pair = Pair(pair_id=_new_id("p"), user_a_id=current_user["user_id"], user_b_id=target.user_id, status="active", created_at=now, updated_at=now)
    db.add(pair)
    db.commit()
    return ok(
        {
            "pair_id": pair.pair_id,
            "status": "active",
            "bind_days": 1,
            "partner": {"user_id": target.user_id, "nickname": target.nickname, "avatar": target.avatar},
            "shared_books": 0,
            "shared_notes": 0,
        },
        request_id=request_id,
    )


@router.post("/pair/unbind")
def pair_unbind(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    pair = get_active_pair(db, current_user["user_id"])
    if not pair:
        raise ApiError(40402, "当前没有可解绑的共读关系", 404)
    pair.status = "unbound"
    pair.updated_at = _utc_now()
    db.commit()
    return ok({"pair_id": pair.pair_id, "status": "unbound"}, request_id=request_id)


@router.get("/books")
def books_list(
    status: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    pair = get_active_pair(db, current_user["user_id"])
    if not pair:
        return ok({"books": []}, request_id=request_id)
    stmt = select(Book).where(Book.pair_id == pair.pair_id)
    if status:
        stmt = stmt.where(Book.status == status)
    rows = db.execute(stmt.order_by(desc(Book.created_at))).scalars().all()
    partner_id = get_partner_id(pair, current_user["user_id"])
    books = [_book_progress(db, row, current_user["user_id"], partner_id) for row in rows]
    return ok({"books": books}, request_id=request_id)


@router.get("/books/{book_id}/entries")
def book_entries(
    book_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    book = db.execute(select(Book).where(Book.book_id == book_id)).scalar_one_or_none()
    if not book:
        raise ApiError(40411, "书籍不存在", 404)
    pair = get_active_pair(db, current_user["user_id"])
    if not pair or pair.pair_id != book.pair_id:
        raise ApiError(40302, "无权查看这本书", 403)
    my_progress = _user_max_page(db, book_id, current_user["user_id"])
    partner_id = get_partner_id(pair, current_user["user_id"])
    partner_progress = _user_max_page(db, book_id, partner_id)

    total_entries = db.execute(select(func.count(Entry.entry_id)).where(Entry.book_id == book_id)).scalar() or 0
    offset = (page - 1) * page_size
    rows = (
        db.execute(
            select(Entry)
            .where(Entry.book_id == book_id)
            .order_by(desc(Entry.created_at))
            .offset(offset)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    mark = db.execute(select(ReadMark).where(ReadMark.user_id == current_user["user_id"], ReadMark.book_id == book_id)).scalar_one_or_none()
    if mark:
        unread_count = (
            db.execute(
                select(func.count(Entry.entry_id)).where(
                    Entry.book_id == book_id,
                    Entry.user_id != current_user["user_id"],
                    Entry.created_at > mark.last_read_at,
                )
            ).scalar()
            or 0
        )
    else:
        unread_count = (
            db.execute(
                select(func.count(Entry.entry_id)).where(
                    Entry.book_id == book_id,
                    Entry.user_id != current_user["user_id"],
                )
            ).scalar()
            or 0
        )

    entry_ids = [row.entry_id for row in rows]
    reply_rows = (
        db.execute(select(Reply).where(Reply.entry_id.in_(entry_ids)).order_by(Reply.created_at.asc())).scalars().all()
        if entry_ids
        else []
    )
    replies_by_entry: Dict[str, List[Reply]] = {}
    reply_user_ids = set()
    for item in reply_rows:
        reply_user_ids.add(item.user_id)
        replies_by_entry.setdefault(item.entry_id, []).append(item)

    entry_user_ids = {row.user_id for row in rows}
    all_user_ids = list(entry_user_ids | reply_user_ids)
    users = db.execute(select(User).where(User.user_id.in_(all_user_ids))).scalars().all() if all_user_ids else []
    users_by_id = {u.user_id: u for u in users}

    entries: List[Dict[str, Any]] = []
    for row in rows:
        author = users_by_id.get(row.user_id)
        is_locked = row.user_id != current_user["user_id"] and int(row.page) > my_progress
        is_unread = False
        if row.user_id != current_user["user_id"]:
            if not mark:
                is_unread = True
            elif row.created_at > mark.last_read_at:
                is_unread = True
        replies: List[Dict[str, Any]] = []
        if not is_locked:
            for r in replies_by_entry.get(row.entry_id, []):
                r_user = users_by_id.get(r.user_id)
                replies.append(
                    {
                        "reply_id": r.reply_id,
                        "user_id": r.user_id,
                        "nickname": r_user.nickname if r_user else "书友",
                        "avatar": r_user.avatar if r_user else "",
                        "content": r.content,
                        "created_at": r.created_at,
                    }
                )
        entries.append(
            {
                "entry_id": row.entry_id,
                "user_id": row.user_id,
                "nickname": author.nickname if author else "书友",
                "avatar": author.avatar if author else "",
                "page": row.page,
                "note_content": None if is_locked else row.note_content,
                "is_locked": is_locked,
                "unlock_at_page": row.page if is_locked else None,
                "created_at": row.created_at,
                "replies": replies,
                "is_mine": row.user_id == current_user["user_id"],
                "is_unread": is_unread,
            }
        )
    return ok(
        {
            "book_id": book_id,
            "my_progress": my_progress,
            "partner_progress": partner_progress,
            "unread_count": int(unread_count),
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": int(total_entries),
                "has_more": offset + len(rows) < int(total_entries),
            },
            "entries": entries,
        },
        request_id=request_id,
    )


@router.post("/books/{book_id}/entries/read")
def mark_entries_read(
    book_id: str,
    payload: ReadEntriesPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    book = db.execute(select(Book).where(Book.book_id == book_id)).scalar_one_or_none()
    if not book:
        raise ApiError(40411, "书籍不存在", 404)
    pair = get_active_pair(db, current_user["user_id"])
    if not pair or pair.pair_id != book.pair_id:
        raise ApiError(40302, "无权操作这本书", 403)
    target_time = _utc_now()
    if payload.last_entry_id:
        entry = db.execute(select(Entry).where(Entry.entry_id == payload.last_entry_id, Entry.book_id == book_id)).scalar_one_or_none()
        if entry:
            target_time = entry.created_at
    mark = db.execute(select(ReadMark).where(ReadMark.user_id == current_user["user_id"], ReadMark.book_id == book_id)).scalar_one_or_none()
    if mark:
        mark.last_read_at = target_time
    else:
        db.add(ReadMark(user_id=current_user["user_id"], book_id=book_id, last_read_at=target_time))
    db.commit()
    return ok({"book_id": book_id, "last_read_at": target_time}, request_id=request_id)


@router.post("/entries/{entry_id}/replies")
def reply_entry(
    entry_id: str,
    payload: ReplyPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    entry = db.execute(select(Entry).where(Entry.entry_id == entry_id)).scalar_one_or_none()
    if not entry:
        raise ApiError(40412, "笔记不存在", 404)
    book = db.execute(select(Book).where(Book.book_id == entry.book_id)).scalar_one_or_none()
    pair = get_active_pair(db, current_user["user_id"])
    if not pair or not book or pair.pair_id != book.pair_id:
        raise ApiError(40303, "无权回复这条笔记", 403)
    my_progress = _user_max_page(db, entry.book_id, current_user["user_id"])
    if entry.user_id != current_user["user_id"] and int(entry.page) > my_progress:
        raise ApiError(40031, "这条笔记还未解锁，暂时不能回复", 400)

    reply = Reply(
        reply_id=_new_id("r"),
        entry_id=entry_id,
        user_id=current_user["user_id"],
        content=payload.content.strip(),
        created_at=_utc_now(),
    )
    db.add(reply)
    db.commit()
    return ok({"reply_id": reply.reply_id}, request_id=request_id)
