from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from common.config import settings
from common.errors import ApiError
from common.locks import acquire_named_locks
from common.models import ActiveBookLock, ActivePairLock, Book, Entry, Pair, ReadMark, ReadingGoal, ReminderConfig, Reply
from repo import reading_repo as repo


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def calc_days_since(created_at: str) -> int:
    try:
        start = datetime.fromisoformat((created_at or "").replace("Z", "+00:00"))
    except Exception:
        return 1
    return max(1, (datetime.now(timezone.utc) - start).days + 1)


def partner_id(pair, user_id: str) -> str:
    return pair.user_b_id if pair.user_a_id == user_id else pair.user_a_id


def user_dict(user) -> Dict[str, Any]:
    return {
        "user_id": user.user_id,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "join_code": user.join_code,
        "phone_number": user.phone_number,
        "agreement_accepted_at": user.agreement_accepted_at,
        "join_days": calc_days_since(user.created_at),
    }


def pair_stats(db: Session, pair_id: str) -> Dict[str, int]:
    from sqlalchemy import func, select
    from common.models import Entry as EntryModel

    shared_books = repo.count_books_for_pairs(db, [pair_id])
    shared_notes = int(
        db.execute(
            select(func.count(EntryModel.entry_id)).join(Book, Book.book_id == EntryModel.book_id).where(Book.pair_id == pair_id)
        ).scalar()
        or 0
    )
    return {"shared_books": shared_books, "shared_notes": shared_notes}


def book_progress(db: Session, book: Book, user_id: str, target_partner_id: str) -> Dict[str, Any]:
    return {
        "book_id": book.book_id,
        "title": book.title,
        "author": book.author,
        "total_pages": int(book.total_pages or 0),
        "status": book.status,
        "my_progress": repo.get_user_max_page(db, book.book_id, user_id),
        "partner_progress": repo.get_user_max_page(db, book.book_id, target_partner_id),
        "reading_days": calc_days_since(book.created_at),
        "created_at": book.created_at,
        "finished_at": book.finished_at,
    }


def update_current_user(db: Session, user_id: str, nickname: str) -> Dict[str, Any]:
    nickname = (nickname or "").strip()
    if not nickname:
        raise ApiError(40090, "昵称不能为空", 400)
    user = repo.get_user_by_id(db, user_id)
    if not user:
        raise ApiError(40100, "登录状态已失效，请重新登录", 401)
    user.nickname = nickname
    db.commit()
    return {"user": user_dict(user)}


def get_current_user_profile(db: Session, current_user: Dict[str, Any]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    partner = None
    if pair:
        target_partner_id = partner_id(pair, current_user["user_id"])
        partner_row = repo.get_user_by_id(db, target_partner_id)
        if partner_row:
            partner = {
                "user_id": partner_row.user_id,
                "nickname": partner_row.nickname,
                "avatar": partner_row.avatar,
                "join_code": partner_row.join_code,
            }
    return {"user": current_user, "partner": partner}


def get_current_user_stats(db: Session, current_user: Dict[str, Any]) -> Dict[str, Any]:
    user_id = current_user["user_id"]
    pair_ids = repo.list_pair_ids_for_user(db, user_id)
    total_pages = sum(int(row.max_page or 0) for row in repo.list_user_book_max_pages(db, user_id))
    return {
        "total_books": repo.count_books_for_pairs(db, pair_ids, status="finished"),
        "total_pages": int(total_pages),
        "total_entries": repo.count_entries_for_user(db, user_id),
        "total_days": calc_days_since(current_user.get("created_at", "")),
    }


def get_reading_history(db: Session, user_id: str, page: int, page_size: int) -> Dict[str, Any]:
    if page < 1 or page > 200:
        raise ApiError(40082, "page 范围不合法", 400)
    if page_size < 1 or page_size > 50:
        raise ApiError(40083, "page_size 范围不合法", 400)
    pair_ids = repo.list_pair_ids_for_user(db, user_id)
    if not pair_ids:
        return {"items": [], "page": page, "page_size": page_size, "has_more": False}
    total_count = repo.count_books_for_pairs(db, pair_ids)
    rows = repo.list_books_for_pairs(db, pair_ids, offset=(page - 1) * page_size, limit=page_size)
    items = []
    for book in rows:
        items.append(
            {
                "book_id": book.book_id,
                "title": book.title,
                "author": book.author,
                "total_pages": int(book.total_pages or 0),
                "my_progress": repo.get_user_max_page(db, book.book_id, user_id),
                "status": book.status,
                "finished_at": book.finished_at,
                "created_at": book.created_at,
            }
        )
    return {"items": items, "page": page, "page_size": page_size, "has_more": page * page_size < int(total_count)}


def get_current_pair(db: Session, current_user: Dict[str, Any]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        return {"pair": None}
    target_partner_id = partner_id(pair, current_user["user_id"])
    partner = repo.get_user_by_id(db, target_partner_id)
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
        **pair_stats(db, pair.pair_id),
    }
    book = repo.get_current_book(db, pair.pair_id)
    data["current_book"] = book_progress(db, book, current_user["user_id"], target_partner_id) if book else None
    return {"pair": data}


def create_pair(db: Session, current_user: Dict[str, Any], join_code: str) -> Dict[str, Any]:
    if join_code == current_user["join_code"]:
        raise ApiError(40013, "不能与自己绑定", 400)
    target = repo.get_user_by_join_code(db, join_code)
    if not target:
        raise ApiError(40011, "未找到对应用户，请确认对方共读码是否正确", 400)

    with acquire_named_locks(f"bind-user:{current_user['user_id']}", f"bind-user:{target.user_id}"):
        repo.lock_users(db, [current_user["user_id"], target.user_id])
        if repo.get_active_pair(db, current_user["user_id"]):
            raise ApiError(40012, "你已与其他伙伴共读，请先解绑再绑定新伙伴", 400)
        if repo.get_active_pair(db, target.user_id):
            raise ApiError(40012, "对方已与其他伙伴共读，无法绑定", 400)

        now = utc_now()
        pair_id_value = new_id("p")
        pair = Pair(
            pair_id=pair_id_value,
            user_a_id=current_user["user_id"],
            user_b_id=target.user_id,
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(pair)
        db.add_all(
            [
                ActivePairLock(user_id=current_user["user_id"], pair_id=pair_id_value, created_at=now),
                ActivePairLock(user_id=target.user_id, pair_id=pair_id_value, created_at=now),
            ]
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ApiError(40012, "你或对方已有正在生效的共读关系", 400)
        return {
            "pair_id": pair.pair_id,
            "status": "active",
            "bind_days": 1,
            "partner": {"user_id": target.user_id, "nickname": target.nickname, "avatar": target.avatar},
            "shared_books": 0,
            "shared_notes": 0,
        }


def delete_current_pair(db: Session, current_user: Dict[str, Any]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        raise ApiError(40402, "当前没有可解绑的共读关系", 404)
    pair.status = "unbound"
    pair.updated_at = utc_now()
    db.query(ActivePairLock).filter(ActivePairLock.pair_id == pair.pair_id).delete(synchronize_session=False)
    db.query(ActiveBookLock).filter(ActiveBookLock.pair_id == pair.pair_id).delete(synchronize_session=False)
    db.commit()
    return {"pair_id": pair.pair_id, "status": "unbound"}


def get_home(db: Session, current_user: Dict[str, Any]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    result: Dict[str, Any] = {"user": current_user, "pair": None, "current_book": None}
    if not pair:
        return result
    target_partner_id = partner_id(pair, current_user["user_id"])
    partner = repo.get_user_by_id(db, target_partner_id)
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
        **pair_stats(db, pair.pair_id),
    }
    book = repo.get_current_book(db, pair.pair_id)
    if book:
        result["current_book"] = book_progress(db, book, current_user["user_id"], target_partner_id)
    return result


def list_books(db: Session, current_user: Dict[str, Any], status: Optional[str]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        return {"books": []}
    target_partner_id = partner_id(pair, current_user["user_id"])
    return {
        "books": [
            book_progress(db, row, current_user["user_id"], target_partner_id)
            for row in repo.list_books_for_pair(db, pair.pair_id, status=status)
        ]
    }


def create_book(db: Session, current_user: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        raise ApiError(40301, "请先绑定共读伙伴后再添加书籍", 403)
    with acquire_named_locks(f"create-book:{pair.pair_id}"):
        locked_pair = repo.get_pair_for_update(db, pair.pair_id)
        if not locked_pair or locked_pair.status != "active":
            raise ApiError(40301, "请先绑定共读伙伴后再添加书籍", 403)
        active_lock = repo.get_active_book_lock(db, pair.pair_id)
        if active_lock:
            locked_book = repo.get_book_by_id(db, active_lock.book_id)
            if locked_book and locked_book.status == "reading":
                raise ApiError(40021, "当前已有一本正在共读的书，请先读完再添加", 400)
            db.delete(active_lock)
            db.flush()
        if repo.get_current_book(db, pair.pair_id):
            raise ApiError(40021, "当前已有一本正在共读的书，请先读完再添加", 400)

        if payload.get("catalog_id"):
            cbook, ccontent = repo.get_catalog_book_with_content(db, payload["catalog_id"])
            if not cbook or not ccontent:
                raise ApiError(40423, "书城书籍不存在或正文不可用", 404)
            title = cbook.title
            author = cbook.author
            total_pages = int(ccontent.total_pages or 1)
        else:
            title = (payload.get("title") or "").strip()
            if not title:
                raise ApiError(40072, "书名不能为空", 400)
            if payload.get("total_pages") is None:
                raise ApiError(40073, "总页数不能为空", 400)
            author = (payload.get("author") or "").strip()
            total_pages = int(payload["total_pages"])

        book = Book(
            book_id=new_id("b"),
            pair_id=pair.pair_id,
            title=title,
            author=author,
            total_pages=total_pages,
            status="reading",
            created_by=current_user["user_id"],
            created_at=utc_now(),
            finished_at=None,
        )
        db.add(book)
        db.add(ActiveBookLock(pair_id=pair.pair_id, book_id=book.book_id, created_at=book.created_at))
        db.commit()
        target_partner_id = partner_id(pair, current_user["user_id"])
        return book_progress(db, book, current_user["user_id"], target_partner_id)


def get_current_pair_book(db: Session, current_user: Dict[str, Any]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        return {"book": None}
    book = repo.get_current_book(db, pair.pair_id)
    if not book:
        return {"book": None}
    return {"book": book_progress(db, book, current_user["user_id"], partner_id(pair, current_user["user_id"]))}


def create_entry(
    db: Session,
    current_user: Dict[str, Any],
    book_id: str,
    page: int,
    note_content: str,
    mark_finished: bool,
    client_request_id: Optional[str],
) -> Dict[str, Any]:
    book = repo.get_book_by_id(db, book_id)
    if not book:
        raise ApiError(40411, "书籍不存在", 404)
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair or pair.pair_id != book.pair_id:
        raise ApiError(40302, "无权操作这本书", 403)
    if book.status != "reading":
        raise ApiError(40022, "这本书已归档，不能再更新进度", 400)

    duplicated = repo.get_duplicate_entry(db, book_id, current_user["user_id"], client_request_id)
    if duplicated:
        return book_progress(db, book, current_user["user_id"], partner_id(pair, current_user["user_id"]))

    current_page = repo.get_user_max_page(db, book_id, current_user["user_id"])
    final_page = int(book.total_pages) if mark_finished else int(page)
    if final_page < current_page:
        raise ApiError(40023, "页码不能小于当前已记录的页码", 400)
    if final_page > int(book.total_pages):
        raise ApiError(40024, "页码不能超过书籍总页数", 400)

    entry = Entry(
        entry_id=new_id("e"),
        book_id=book_id,
        user_id=current_user["user_id"],
        page=final_page,
        note_content=(note_content or "").strip(),
        created_at=utc_now(),
        client_request_id=client_request_id,
    )
    db.add(entry)

    target_partner_id = partner_id(pair, current_user["user_id"])
    partner_progress = repo.get_user_max_page(db, book_id, target_partner_id)
    if final_page >= int(book.total_pages) and partner_progress >= int(book.total_pages):
        book.status = "finished"
        book.finished_at = utc_now()
        db.query(ActiveBookLock).filter(ActiveBookLock.pair_id == book.pair_id, ActiveBookLock.book_id == book.book_id).delete(
            synchronize_session=False
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicated = repo.get_duplicate_entry(db, book_id, current_user["user_id"], client_request_id)
        if duplicated:
            book = repo.get_book_by_id(db, book_id)
            return book_progress(db, book, current_user["user_id"], target_partner_id)
        raise
    db.refresh(book)
    return book_progress(db, book, current_user["user_id"], target_partner_id)


def list_book_entries(db: Session, current_user: Dict[str, Any], book_id: str, page: int, page_size: int) -> Dict[str, Any]:
    book = repo.get_book_by_id(db, book_id)
    if not book:
        raise ApiError(40411, "书籍不存在", 404)
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair or pair.pair_id != book.pair_id:
        raise ApiError(40302, "无权查看这本书", 403)
    my_progress = repo.get_user_max_page(db, book_id, current_user["user_id"])
    target_partner_id = partner_id(pair, current_user["user_id"])
    partner_progress = repo.get_user_max_page(db, book_id, target_partner_id)
    total_entries = repo.count_entries_for_book(db, book_id)
    offset = (page - 1) * page_size
    rows = repo.list_entries_for_book(db, book_id, offset, page_size)
    mark = repo.get_read_mark(db, current_user["user_id"], book_id)
    unread_count = repo.count_unread_entries(db, book_id, current_user["user_id"], mark.last_read_at if mark else None)

    entry_ids = [row.entry_id for row in rows]
    reply_rows = repo.list_replies_for_entries(db, entry_ids)
    replies_by_entry: Dict[str, List[Reply]] = {}
    reply_user_ids = set()
    for item in reply_rows:
        reply_user_ids.add(item.user_id)
        replies_by_entry.setdefault(item.entry_id, []).append(item)
    entry_user_ids = {row.user_id for row in rows}
    users_by_id = {user.user_id: user for user in repo.list_users_by_ids(db, list(entry_user_ids | reply_user_ids))}

    entries: List[Dict[str, Any]] = []
    for row in rows:
        author = users_by_id.get(row.user_id)
        is_locked = row.user_id != current_user["user_id"] and int(row.page) > my_progress
        is_unread = row.user_id != current_user["user_id"] and (not mark or row.created_at > mark.last_read_at)
        replies: List[Dict[str, Any]] = []
        if not is_locked:
            for reply in replies_by_entry.get(row.entry_id, []):
                reply_user = users_by_id.get(reply.user_id)
                replies.append(
                    {
                        "reply_id": reply.reply_id,
                        "user_id": reply.user_id,
                        "nickname": reply_user.nickname if reply_user else "书友",
                        "avatar": reply_user.avatar if reply_user else "",
                        "content": reply.content,
                        "created_at": reply.created_at,
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

    return {
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
    }


def put_book_read_mark(db: Session, current_user: Dict[str, Any], book_id: str, last_entry_id: Optional[str]) -> Dict[str, Any]:
    book = repo.get_book_by_id(db, book_id)
    if not book:
        raise ApiError(40411, "书籍不存在", 404)
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair or pair.pair_id != book.pair_id:
        raise ApiError(40302, "无权操作这本书", 403)
    target_time = utc_now()
    if last_entry_id:
        entry = repo.get_entry_for_book(db, last_entry_id, book_id)
        if entry:
            target_time = entry.created_at
    mark = repo.get_read_mark(db, current_user["user_id"], book_id)
    if mark:
        mark.last_read_at = target_time
    else:
        db.add(ReadMark(user_id=current_user["user_id"], book_id=book_id, last_read_at=target_time))
    db.commit()
    return {"book_id": book_id, "last_read_at": target_time}


def reply_entry(db: Session, current_user: Dict[str, Any], entry_id: str, content: str) -> Dict[str, Any]:
    entry = repo.get_entry_by_id(db, entry_id)
    if not entry:
        raise ApiError(40412, "笔记不存在", 404)
    book = repo.get_book_by_id(db, entry.book_id)
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair or not book or pair.pair_id != book.pair_id:
        raise ApiError(40303, "无权回复这条笔记", 403)
    my_progress = repo.get_user_max_page(db, entry.book_id, current_user["user_id"])
    if entry.user_id != current_user["user_id"] and int(entry.page) > my_progress:
        raise ApiError(40031, "这条笔记还未解锁，暂时不能回复", 400)
    reply = Reply(
        reply_id=new_id("r"),
        entry_id=entry_id,
        user_id=current_user["user_id"],
        content=content.strip(),
        created_at=utc_now(),
    )
    db.add(reply)
    db.commit()
    return {"reply_id": reply.reply_id}


def default_goal() -> Dict[str, Any]:
    return {"period_days": 30, "target_books": 1, "target_days": 20, "updated_at": None}


def goal_dict(row: Optional[ReadingGoal]) -> Dict[str, Any]:
    if not row:
        return default_goal()
    return {"period_days": row.period_days, "target_books": row.target_books, "target_days": row.target_days, "updated_at": row.updated_at}


def goal_progress(db: Session, user_id: str, goal: Dict[str, Any]) -> Dict[str, Any]:
    period_days = int(goal["period_days"])
    target_books = int(goal["target_books"])
    target_days = int(goal["target_days"])
    start_at = datetime.now(timezone.utc).replace(microsecond=0).timestamp() - (period_days - 1) * 24 * 60 * 60
    start_iso = datetime.fromtimestamp(start_at, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    completed_books = len(repo.list_finished_books_since(db, repo.list_pair_ids_for_user(db, user_id), start_iso))
    active_days = len({(value or "")[:10] for value in repo.list_entry_dates_since(db, user_id, start_iso) if value})
    return {
        "period_start_at": start_iso,
        "completed_books": int(completed_books),
        "target_books": target_books,
        "book_percent": min(100, int(completed_books * 100 / target_books)) if target_books else 0,
        "active_days": active_days,
        "target_days": target_days,
        "day_percent": min(100, int(active_days * 100 / target_days)) if target_days else 0,
    }


def get_reading_goal(db: Session, user_id: str) -> Dict[str, Any]:
    goal = goal_dict(repo.get_reading_goal(db, user_id))
    return {"goal": goal, "progress": goal_progress(db, user_id, goal)}


def put_reading_goal(db: Session, user_id: str, period_days: int, target_books: int, target_days: int) -> Dict[str, Any]:
    if period_days < 7 or period_days > 365:
        raise ApiError(40084, "周期天数范围应为 7-365", 400)
    if target_books < 1 or target_books > 200:
        raise ApiError(40085, "目标书籍范围应为 1-200", 400)
    if target_days < 1 or target_days > period_days:
        raise ApiError(40086, "目标天数不能超过周期天数", 400)
    row = repo.get_reading_goal(db, user_id)
    now = utc_now()
    if row:
        row.period_days = period_days
        row.target_books = target_books
        row.target_days = target_days
        row.updated_at = now
    else:
        row = ReadingGoal(user_id=user_id, period_days=period_days, target_books=target_books, target_days=target_days, updated_at=now)
        db.add(row)
    db.commit()
    goal = goal_dict(row)
    return {"goal": goal, "progress": goal_progress(db, user_id, goal)}


def reminder_delivery_meta() -> Dict[str, Any]:
    template_id = (settings.WECHAT_REMINDER_TEMPLATE_ID or "").strip()
    if template_id:
        return {
            "delivery_status": "ready",
            "delivery_message": "已配置微信订阅消息模板，保存提醒后将按调度任务投递",
            "template_id": template_id,
        }
    return {
        "delivery_status": "config_only",
        "delivery_message": "已保存提醒偏好，未配置微信订阅消息模板，暂不会真实投递",
        "template_id": "",
    }


def reminder_dict(row: Optional[ReminderConfig]) -> Dict[str, Any]:
    base = (
        {"enabled": bool(row.enabled), "remind_time": row.remind_time, "timezone": row.timezone, "updated_at": row.updated_at}
        if row
        else {"enabled": True, "remind_time": "21:00", "timezone": "Asia/Shanghai", "updated_at": None}
    )
    return {**base, **reminder_delivery_meta()}


def get_reminder_config(db: Session, user_id: str) -> Dict[str, Any]:
    return {"reminder": reminder_dict(repo.get_reminder_config(db, user_id))}


def put_reminder_config(db: Session, user_id: str, enabled: bool, remind_time: str, timezone_name: str) -> Dict[str, Any]:
    import re

    if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", remind_time or ""):
        raise ApiError(40087, "提醒时间格式应为 HH:MM", 400)
    if not timezone_name or len(timezone_name) > 64:
        raise ApiError(40088, "时区参数不合法", 400)
    row = repo.get_reminder_config(db, user_id)
    now = utc_now()
    if row:
        row.enabled = 1 if enabled else 0
        row.remind_time = remind_time
        row.timezone = timezone_name
        row.updated_at = now
    else:
        row = ReminderConfig(
            user_id=user_id,
            enabled=1 if enabled else 0,
            remind_time=remind_time,
            timezone=timezone_name,
            updated_at=now,
        )
        db.add(row)
    db.commit()
    return {"reminder": reminder_dict(row)}
