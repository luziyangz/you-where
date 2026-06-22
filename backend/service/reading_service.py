from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from common.config import settings
from common.errors import ApiError
from common.locks import acquire_named_locks
from common.models import (
    ActiveBookLock,
    ActivePairLock,
    Book,
    BookSwitchRequest,
    Entry,
    Pair,
    PairRequest,
    ReadMark,
    ReadingGoal,
    ReminderConfig,
    Reply,
)
from common.reading_enums import (
    BOOK_STATUS_FINISHED,
    BOOK_STATUS_READING,
    BOOK_STATUS_SWITCHED,
    DISPLAY_STATUS_FINISHED,
    DISPLAY_STATUS_SWITCHED,
    DISPLAY_STATUS_UNFINISHED,
)
from repo import reading_repo as repo
from repo import feed_repo
from repo import store_repo

READER_MODE_SET = frozenset({"paper", "night", "focus"})
PAIR_REQUEST_EXPIRE_DAYS = 7
TEST_DIRECT_BIND_JOIN_CODES = frozenset({"900001", "900002"})
PERSONAL_PAIR_PREFIX = "personal_"


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


def _parse_utc(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except Exception:
        return None


def _pair_request_expired(row: PairRequest) -> bool:
    start = _parse_utc(row.created_at)
    if not start:
        return False
    return (datetime.now(timezone.utc) - start).days >= PAIR_REQUEST_EXPIRE_DAYS


def partner_id(pair, user_id: str) -> str:
    return pair.user_b_id if pair.user_a_id == user_id else pair.user_a_id


def personal_pair_id(user_id: str) -> str:
    return f"{PERSONAL_PAIR_PREFIX}{user_id}"[:64]


def is_personal_book(book: Book, user_id: str) -> bool:
    return bool(book and book.pair_id == personal_pair_id(user_id) and book.created_by == user_id)


def can_access_book(db: Session, book: Book, user_id: str):
    if is_personal_book(book, user_id):
        return None
    pair = repo.get_active_pair(db, user_id)
    if pair and pair.pair_id == book.pair_id:
        return pair
    return None


def book_progress_for_viewer(db: Session, book: Book, user_id: str) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, user_id)
    target_partner_id = partner_id(pair, user_id) if pair and pair.pair_id == book.pair_id else user_id
    return book_progress(db, book, user_id, target_partner_id)


def effective_user_book_progress(db: Session, book: Book, user_id: str) -> int:
    """共读本书进度：book 进度、日记最高页；已在读的共读书再与书城进度对齐。"""
    entry_max = repo.get_user_max_page(db, book.book_id, user_id)
    scoped_last = repo.get_book_read_progress(db, user_id, book.book_id)
    combined = entry_max
    if scoped_last is not None:
        combined = max(combined, int(scoped_last))
    cid = str(getattr(book, "catalog_id", "") or "").strip()
    if cid and (book.status or "") != BOOK_STATUS_READING:
        from repo import store_repo

        catalog_last = store_repo.get_catalog_read_progress(db, user_id, cid)
        if catalog_last is not None:
            combined = max(combined, int(catalog_last))
    tp = int(book.total_pages or 0)
    if tp > 0:
        combined = min(combined, tp)
    return combined


def book_is_truly_finished(db: Session, book: Book) -> bool:
    """双方均读至末页才算「真读完」；误标 finished / switched 不计入统计。"""
    raw = (book.status or "").strip().lower()
    if raw != BOOK_STATUS_FINISHED:
        return False
    total = int(book.total_pages or 0)
    if total <= 0:
        return True
    if (book.pair_id or "").startswith(PERSONAL_PAIR_PREFIX):
        return effective_user_book_progress(db, book, book.created_by) >= total
    pair = repo.get_pair_by_id(db, book.pair_id)
    if not pair:
        return False
    prog_a = effective_user_book_progress(db, book, pair.user_a_id)
    prog_b = effective_user_book_progress(db, book, pair.user_b_id)
    return prog_a >= total and prog_b >= total


def count_truly_finished_books(db: Session, pair_ids: List[str], since_iso: Optional[str] = None) -> int:
    if not pair_ids:
        return 0
    if since_iso:
        rows = repo.list_books_for_pairs_since(db, pair_ids, since_iso)
    else:
        from sqlalchemy import select

        rows = db.execute(select(Book).where(Book.pair_id.in_(pair_ids), Book.status == BOOK_STATUS_FINISHED)).scalars().all()
    return sum(1 for book in rows if book_is_truly_finished(db, book))


def _default_reader_options() -> Dict[str, Any]:
    return {"font_size": 32, "reading_mode": "paper", "brightness": 90}


def _normalize_reader_options_blob(raw: Optional[str]) -> Dict[str, Any]:
    base = _default_reader_options()
    if not raw or not str(raw).strip():
        return dict(base)
    try:
        data = json.loads(raw)
    except Exception:
        return dict(base)
    if not isinstance(data, dict):
        return dict(base)
    out = dict(base)
    try:
        fs = int(data.get("font_size"))
        if 28 <= fs <= 42:
            out["font_size"] = fs
    except Exception:
        pass
    rm = str(data.get("reading_mode") or "").strip()
    if rm in READER_MODE_SET:
        out["reading_mode"] = rm
    try:
        br = int(data.get("brightness"))
        if 25 <= br <= 100:
            out["brightness"] = br
    except Exception:
        pass
    return out


def get_reader_options(db: Session, user_id: str) -> Dict[str, Any]:
    user = repo.get_user_by_id(db, user_id)
    if not user:
        raise ApiError(40100, "登录状态已失效，请重新登录", 401)
    blob = getattr(user, "reader_options", None)
    return {"reader_options": _normalize_reader_options_blob(blob if isinstance(blob, str) else None)}


def put_reader_options(
    db: Session,
    user_id: str,
    *,
    font_size: Optional[int] = None,
    reading_mode: Optional[str] = None,
    brightness: Optional[int] = None,
) -> Dict[str, Any]:
    user = repo.get_user_by_id(db, user_id)
    if not user:
        raise ApiError(40100, "登录状态已失效，请重新登录", 401)
    if font_size is None and reading_mode is None and brightness is None:
        return {"reader_options": _normalize_reader_options_blob(getattr(user, "reader_options", None))}
    current = _normalize_reader_options_blob(getattr(user, "reader_options", None))
    if font_size is not None:
        if font_size < 28 or font_size > 42:
            raise ApiError(40091, "字号范围为 28-42", 400)
        current["font_size"] = int(font_size)
    if reading_mode is not None:
        rm = str(reading_mode).strip()
        if rm not in READER_MODE_SET:
            raise ApiError(40092, "阅读主题无效", 400)
        current["reading_mode"] = rm
    if brightness is not None:
        if brightness < 25 or brightness > 100:
            raise ApiError(40093, "亮度范围为 25-100", 400)
        current["brightness"] = int(brightness)
    user.reader_options = json.dumps(current, ensure_ascii=False)
    db.commit()
    return {"reader_options": dict(current)}


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


def _expire_pair_request_if_needed(db: Session, row: PairRequest) -> bool:
    if row.status != "pending" or not _pair_request_expired(row):
        return False
    row.status = "rejected"
    row.responded_at = utc_now()
    row.responded_by = None
    db.flush()
    return True


def _pair_request_dict(db: Session, row: PairRequest, viewer_user_id: str) -> Dict[str, Any]:
    other_id = row.target_user_id if row.requester_user_id == viewer_user_id else row.requester_user_id
    other = repo.get_user_by_id(db, other_id)
    return {
        "request_id": row.request_id,
        "request_type": row.request_type,
        "status": row.status,
        "direction": "incoming" if row.target_user_id == viewer_user_id else "outgoing",
        "created_at": row.created_at,
        "expires_in_days": max(0, PAIR_REQUEST_EXPIRE_DAYS - calc_days_since(row.created_at) + 1),
        "pair_id": row.pair_id,
        "other_user": {
            "user_id": other.user_id if other else other_id,
            "nickname": other.nickname if other else "书友",
            "avatar": other.avatar if other else "",
            "join_code": other.join_code if other else "",
        },
    }


def _pending_pair_requests_for_user(db: Session, user_id: str) -> List[Dict[str, Any]]:
    rows = repo.list_pending_pair_requests_for_user(db, user_id)
    out: List[Dict[str, Any]] = []
    changed = False
    for row in rows:
        if _expire_pair_request_if_needed(db, row):
            changed = True
            continue
        out.append(_pair_request_dict(db, row, user_id))
    if changed:
        db.commit()
    return out


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
    cid = getattr(book, "catalog_id", None)
    total = int(book.total_pages or 0)
    my_prog = effective_user_book_progress(db, book, user_id)
    partner_prog = effective_user_book_progress(db, book, target_partner_id)
    my_finished = total > 0 and my_prog >= total
    partner_finished = total > 0 and partner_prog >= total
    display = book_history_display(book, my_prog)
    return {
        "book_id": book.book_id,
        "catalog_id": cid if cid else None,
        "title": book.title,
        "author": book.author,
        "total_pages": total,
        "status": book.status,
        "my_progress": my_prog,
        "partner_progress": partner_prog,
        "my_finished": my_finished,
        "partner_finished": partner_finished,
        "reading_days": calc_days_since(book.created_at),
        "created_at": book.created_at,
        "finished_at": book.finished_at,
        **display,
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
        "total_books": count_truly_finished_books(db, pair_ids),
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
        cid = getattr(book, "catalog_id", None)
        my_prog = effective_user_book_progress(db, book, user_id)
        display = book_history_display(book, my_prog)
        pair = repo.get_pair_by_id(db, book.pair_id)
        history_partner = None
        if pair:
            history_partner_id = partner_id(pair, user_id)
            partner_row = repo.get_user_by_id(db, history_partner_id)
            if partner_row:
                history_partner = {
                    "user_id": partner_row.user_id,
                    "nickname": partner_row.nickname,
                    "avatar": partner_row.avatar,
                }
        items.append(
            {
                "book_id": book.book_id,
                "pair_id": book.pair_id,
                "catalog_id": cid if cid else None,
                "title": book.title,
                "author": book.author,
                "total_pages": int(book.total_pages or 0),
                "my_progress": my_prog,
                "partner": history_partner,
                "partner_nickname": history_partner["nickname"] if history_partner else "",
                "status": book.status,
                "finished_at": book.finished_at,
                "created_at": book.created_at,
                **display,
            }
        )
    return {"items": items, "page": page, "page_size": page_size, "has_more": page * page_size < int(total_count)}


def get_current_pair(db: Session, current_user: Dict[str, Any]) -> Dict[str, Any]:
    pending_requests = _pending_pair_requests_for_user(db, current_user["user_id"])
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        return {"pair": None, "pair_requests": pending_requests}
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
    return {"pair": data, "pair_requests": pending_requests}


def _is_test_direct_bind(current_user: Dict[str, Any], target) -> bool:
    codes = {
        str(current_user.get("join_code") or "").strip(),
        str(getattr(target, "join_code", "") or "").strip(),
    }
    return bool(codes & TEST_DIRECT_BIND_JOIN_CODES)


def _pair_has_test_direct_user(db: Session, pair: Pair) -> bool:
    users = repo.list_users_by_ids(db, [pair.user_a_id, pair.user_b_id])
    return any(str(user.join_code or "").strip() in TEST_DIRECT_BIND_JOIN_CODES for user in users)


def _create_active_pair(db: Session, user_a_id: str, user_b_id: str, now: str) -> Pair:
    pair_id_value = new_id("p")
    pair = Pair(
        pair_id=pair_id_value,
        user_a_id=user_a_id,
        user_b_id=user_b_id,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(pair)
    db.add_all([
        ActivePairLock(user_id=user_a_id, pair_id=pair_id_value, created_at=now),
        ActivePairLock(user_id=user_b_id, pair_id=pair_id_value, created_at=now),
    ])
    return pair


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
        if repo.get_pair_block(db, current_user["user_id"], target.user_id):
            raise ApiError(40014, "你们曾经解除过关系，不能再次绑定", 400)
        existing = repo.get_pending_pair_request_between(db, "bind", current_user["user_id"], target.user_id)
        if existing:
            if _expire_pair_request_if_needed(db, existing):
                db.commit()
            else:
                if _is_test_direct_bind(current_user, target):
                    now = utc_now()
                    pair = _create_active_pair(db, current_user["user_id"], target.user_id, now)
                    existing.pair_id = pair.pair_id
                    existing.status = "approved"
                    existing.responded_at = now
                    existing.responded_by = current_user["user_id"]
                    db.commit()
                    return {
                        "mode": "pair",
                        "pair": get_current_pair(db, current_user)["pair"],
                    }
                return {
                    "mode": "pair_request",
                    "pair_request": _pair_request_dict(db, existing, current_user["user_id"]),
                }
        outgoing = repo.get_pending_outgoing_pair_request(db, "bind", current_user["user_id"])
        if outgoing:
            if _expire_pair_request_if_needed(db, outgoing):
                db.commit()
            else:
                raise ApiError(40015, "你已有待对方同意的绑定申请，请先等待处理后再绑定其他人", 400)

        now = utc_now()
        if _is_test_direct_bind(current_user, target):
            _create_active_pair(db, current_user["user_id"], target.user_id, now)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise ApiError(40012, "你或对方已有正在生效的共读关系", 400)
            return {
                "mode": "pair",
                "pair": get_current_pair(db, current_user)["pair"],
            }

        req = PairRequest(
            request_id=new_id("pr"),
            request_type="bind",
            requester_user_id=current_user["user_id"],
            target_user_id=target.user_id,
            pair_id=None,
            status="pending",
            created_at=now,
            responded_at=None,
            responded_by=None,
        )
        repo.add_pair_request(db, req)
        db.commit()
        return {
            "mode": "pair_request",
            "pair_request": _pair_request_dict(db, req, current_user["user_id"]),
        }


def _finish_unbind(db: Session, pair: Pair, *, block_forever: bool = False) -> None:
    """结束共读关系。仅强制解绑时写入永久互绑禁止记录。"""
    for book in repo.list_books_for_pair(db, pair.pair_id, status=BOOK_STATUS_READING):
        _switch_away_reading_book(db, book)
    pair.status = "unbound"
    pair.updated_at = utc_now()
    db.query(ActivePairLock).filter(ActivePairLock.pair_id == pair.pair_id).delete(synchronize_session=False)
    remaining = repo.get_active_book_lock(db, pair.pair_id)
    if remaining:
        db.delete(remaining)
    if block_forever:
        repo.add_pair_block(db, pair.user_a_id, pair.user_b_id, utc_now(), reason="force_unbound")


def respond_pair_request(db: Session, current_user: Dict[str, Any], request_id: str, action: str) -> Dict[str, Any]:
    row = repo.get_pair_request(db, request_id)
    if not row:
        raise ApiError(40431, "申请不存在", 404)
    if row.target_user_id != current_user["user_id"]:
        raise ApiError(40305, "只能由对方处理该申请", 403)
    if row.status != "pending":
        raise ApiError(40031, "申请已处理", 400)
    if _expire_pair_request_if_needed(db, row):
        db.commit()
        raise ApiError(40032, "申请已超过 7 天，已视为不同意", 400)
    act = (action or "").strip().lower()
    if act not in {"approve", "reject"}:
        raise ApiError(40033, "action 须为 approve 或 reject", 400)
    now = utc_now()
    if act == "reject":
        row.status = "rejected"
        row.responded_at = now
        row.responded_by = current_user["user_id"]
        db.commit()
        return {"status": "rejected", "pair_request": _pair_request_dict(db, row, current_user["user_id"])}
    with acquire_named_locks(f"bind-user:{row.requester_user_id}", f"bind-user:{row.target_user_id}"):
        if row.request_type == "bind":
            repo.lock_users(db, [row.requester_user_id, row.target_user_id])
            if repo.get_pair_block(db, row.requester_user_id, row.target_user_id):
                raise ApiError(40014, "你们曾经解除过关系，不能再次绑定", 400)
            if repo.get_active_pair(db, row.requester_user_id) or repo.get_active_pair(db, row.target_user_id):
                raise ApiError(40012, "其中一方已有正在生效的共读关系", 400)
            pair = _create_active_pair(db, row.requester_user_id, row.target_user_id, now)
            row.pair_id = pair.pair_id
            row.status = "approved"
            row.responded_at = now
            row.responded_by = current_user["user_id"]
            db.commit()
            return {"status": "approved", "pair": get_current_pair(db, current_user)["pair"]}
        if row.request_type == "unbind":
            pair = repo.get_pair_by_id(db, row.pair_id or "")
            if not pair or pair.status != "active":
                raise ApiError(40402, "当前没有可解除的共读关系", 404)
            _finish_unbind(db, pair, block_forever=False)
            row.status = "approved"
            row.responded_at = now
            row.responded_by = current_user["user_id"]
            db.commit()
            return {"status": "unbound", "pair_id": pair.pair_id}
    raise ApiError(40034, "申请类型无效", 400)


def _can_force_unbind_pair(db: Session, pair: Pair, user_id: str) -> bool:
    """绑定满 7 天，或解绑申请已超 7 天未处理时，可申请方强制解绑。"""
    if calc_days_since(pair.created_at) >= PAIR_REQUEST_EXPIRE_DAYS:
        return True
    pending = repo.get_pending_unbind_request_for_pair(db, pair.pair_id)
    if pending and pending.requester_user_id == user_id and _pair_request_expired(pending):
        return True
    return False


def request_unbind_pair(db: Session, current_user: Dict[str, Any]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        raise ApiError(40402, "当前没有可解绑的共读关系", 404)
    if _pair_has_test_direct_user(db, pair):
        _finish_unbind(db, pair, block_forever=False)
        db.commit()
        return {"pair_id": pair.pair_id, "status": "unbound", "mode": "pair"}
    target_id = partner_id(pair, current_user["user_id"])
    existing = repo.get_pending_unbind_request_for_pair(db, pair.pair_id)
    if existing:
        if _expire_pair_request_if_needed(db, existing):
            db.commit()
        elif existing.requester_user_id == current_user["user_id"]:
            return {
                "mode": "pair_request",
                "pair_request": _pair_request_dict(db, existing, current_user["user_id"]),
            }
        else:
            raise ApiError(40035, "伙伴已发起解绑申请，请先处理", 400)

    now = utc_now()
    req = PairRequest(
        request_id=new_id("pr"),
        request_type="unbind",
        requester_user_id=current_user["user_id"],
        target_user_id=target_id,
        pair_id=pair.pair_id,
        status="pending",
        created_at=now,
        responded_at=None,
        responded_by=None,
    )
    repo.add_pair_request(db, req)
    db.commit()
    return {
        "mode": "pair_request",
        "pair_request": _pair_request_dict(db, req, current_user["user_id"]),
    }


def delete_current_pair(db: Session, current_user: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        raise ApiError(40402, "当前没有可解绑的共读关系", 404)
    if force:
        if not _can_force_unbind_pair(db, pair, current_user["user_id"]):
            raise ApiError(
                40036,
                "绑定未满 7 天且解绑申请未超时，暂不能强制解除",
                400,
            )
        pending = repo.get_pending_unbind_request_for_pair(db, pair.pair_id)
        if pending and pending.status == "pending":
            pending.status = "rejected"
            pending.responded_at = utc_now()
            pending.responded_by = current_user["user_id"]
        _finish_unbind(db, pair, block_forever=True)
        db.commit()
        return {"pair_id": pair.pair_id, "status": "unbound", "forced": True}
    return request_unbind_pair(db, current_user)


def get_home(db: Session, current_user: Dict[str, Any]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    pending_requests = _pending_pair_requests_for_user(db, current_user["user_id"])
    result: Dict[str, Any] = {
        "user": current_user,
        "pair": None,
        "current_book": None,
        "pair_requests": pending_requests,
    }
    if not pair:
        personal_book = repo.get_current_book(db, personal_pair_id(current_user["user_id"]))
        if personal_book:
            result["current_book"] = book_progress(db, personal_book, current_user["user_id"], current_user["user_id"])
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
    result["book_switch"] = get_book_switch_state(db, pair, current_user["user_id"])
    return result


def list_books(db: Session, current_user: Dict[str, Any], status: Optional[str]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        return {
            "books": [
                book_progress(db, row, current_user["user_id"], current_user["user_id"])
                for row in repo.list_books_for_pair(db, personal_pair_id(current_user["user_id"]), status=status)
            ]
        }
    target_partner_id = partner_id(pair, current_user["user_id"])
    return {
        "books": [
            book_progress(db, row, current_user["user_id"], target_partner_id)
            for row in repo.list_books_for_pair(db, pair.pair_id, status=status)
        ]
    }


def _finish_reading_book(db: Session, book: Book) -> None:
    """双方读至末页后标记读完，并释放共读锁。"""
    book.status = BOOK_STATUS_FINISHED
    book.finished_at = utc_now()
    _release_active_book_lock(db, book)


def _switch_away_reading_book(db: Session, book: Book) -> None:
    """换书时中止在读书目（未读完），与真正读完区分。"""
    book.status = BOOK_STATUS_SWITCHED
    book.finished_at = utc_now()
    _release_active_book_lock(db, book)


def _release_active_book_lock(db: Session, book: Book) -> None:
    lock = repo.get_active_book_lock(db, book.pair_id)
    if lock and lock.book_id == book.book_id:
        db.delete(lock)


def book_history_display(book: Book, my_progress: int) -> Dict[str, str]:
    """
    阅读历史展示状态：
    - finished：读至末页（真读完）
    - unfinished：仍在共读 / 未读完
    - switched：中途换书搁置
    """
    total = max(0, int(book.total_pages or 0))
    prog = max(0, int(my_progress or 0))
    raw = (book.status or "").strip().lower()

    if raw == BOOK_STATUS_SWITCHED:
        return {"display_status": DISPLAY_STATUS_SWITCHED, "display_label": "已切换"}

    if raw == BOOK_STATUS_READING:
        return {"display_status": DISPLAY_STATUS_UNFINISHED, "display_label": "未读完"}

    if raw == BOOK_STATUS_FINISHED:
        if total > 0 and prog >= total:
            return {"display_status": DISPLAY_STATUS_FINISHED, "display_label": "已读完"}
        # 旧版换书逻辑曾误标为 finished
        return {"display_status": DISPLAY_STATUS_SWITCHED, "display_label": "已切换"}

    return {"display_status": DISPLAY_STATUS_UNFINISHED, "display_label": "未读完"}


def _switch_request_dict(db: Session, row: BookSwitchRequest, viewer_user_id: str) -> Dict[str, Any]:
    requester = repo.get_user_by_id(db, row.requested_by)
    from_book = repo.get_book_by_id(db, row.from_book_id) if row.from_book_id else None
    return {
        "request_id": row.request_id,
        "status": row.status,
        "requested_by": row.requested_by,
        "requester_nickname": requester.nickname if requester else "书友",
        "is_mine": row.requested_by == viewer_user_id,
        "title": row.title,
        "author": row.author,
        "total_pages": int(row.total_pages or 0),
        "catalog_id": row.catalog_id,
        "from_book": (
            {
                "book_id": from_book.book_id,
                "title": from_book.title,
                "author": from_book.author,
            }
            if from_book
            else None
        ),
        "created_at": row.created_at,
    }


def get_book_switch_state(db: Session, pair: Pair, viewer_user_id: str) -> Dict[str, Any]:
    pending = repo.get_pending_book_switch_request(db, pair.pair_id)
    if not pending:
        return {"incoming": None, "outgoing": None}
    item = _switch_request_dict(db, pending, viewer_user_id)
    if pending.requested_by == viewer_user_id:
        return {"incoming": None, "outgoing": item}
    return {"incoming": item, "outgoing": None}


def _assert_no_blocking_switch_request(db: Session, pair_id: str, user_id: str) -> None:
    pending = repo.get_pending_book_switch_request(db, pair_id)
    if not pending:
        return
    if pending.requested_by == user_id:
        raise ApiError(40023, "已有待伙伴处理的换书申请", 400)
    raise ApiError(40024, "伙伴发起了换书申请，请先处理", 400)


def _resolve_new_book_fields(db: Session, payload: Dict[str, Any]) -> tuple[str, str, int, Optional[str]]:
    if payload.get("catalog_id"):
        from service import store_service

        cid = (payload.get("catalog_id") or "").strip()
        cbook = repo.get_catalog_book(db, cid)
        if not cbook:
            raise ApiError(40423, "书城书籍不存在或正文不可用", 404)
        store_service.hydrate_catalog_if_needed(db, cbook)
        db.flush()
        ccontent = repo.get_catalog_content_row(db, cid)
        title = cbook.title
        author = cbook.author
        if ccontent:
            total_pages = int(ccontent.total_pages or 1)
        elif store_service.catalog_allows_placeholder_pair(cbook):
            pp = getattr(cbook, "placeholder_pages", None)
            total_pages = int(pp) if pp is not None and int(pp) > 0 else 400
        else:
            raise ApiError(40423, "书城书籍不存在或正文不可用", 404)
        catalog_ref = cid
    else:
        title = (payload.get("title") or "").strip()
        if not title:
            raise ApiError(40072, "书名不能为空", 400)
        if payload.get("total_pages") is None:
            raise ApiError(40073, "总页数不能为空", 400)
        author = (payload.get("author") or "").strip()
        total_pages = int(payload["total_pages"])
        catalog_ref = None
    return title, author, total_pages, catalog_ref


def _create_reading_book_row(
    db: Session,
    *,
    pair_id: str,
    title: str,
    author: str,
    total_pages: int,
    catalog_ref: Optional[str],
    created_by: str,
) -> Book:
    now = utc_now()
    book = Book(
        book_id=new_id("b"),
        pair_id=pair_id,
        title=title,
        author=author,
        total_pages=total_pages,
        status="reading",
        catalog_id=catalog_ref,
        created_by=created_by,
        created_at=now,
        finished_at=None,
    )
    db.add(book)
    db.add(ActiveBookLock(pair_id=pair_id, book_id=book.book_id, created_at=now))
    return book


def create_book_switch_request(db: Session, current_user: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        raise ApiError(40301, "请先绑定共读伙伴后再添加书籍", 403)
    with acquire_named_locks(f"create-book:{pair.pair_id}"):
        locked_pair = repo.get_pair_for_update(db, pair.pair_id)
        if not locked_pair or locked_pair.status != "active":
            raise ApiError(40301, "请先绑定共读伙伴后再添加书籍", 403)

        current_reading = repo.get_current_book(db, pair.pair_id)
        _assert_no_blocking_switch_request(db, pair.pair_id, current_user["user_id"])

        catalog_ref_early = (payload.get("catalog_id") or "").strip() or None
        if catalog_ref_early:
            existing = repo.get_pair_book_by_catalog_id(db, pair.pair_id, catalog_ref_early)
            if existing and existing.status == "reading":
                target_partner_id = partner_id(pair, current_user["user_id"])
                return {
                    "mode": "book",
                    "book": book_progress(db, existing, current_user["user_id"], target_partner_id),
                }

        title, author, total_pages, catalog_ref = _resolve_new_book_fields(db, payload)
        if _pair_has_test_direct_user(db, pair):
            if current_reading:
                _switch_away_reading_book(db, current_reading)
                db.flush()
            active_lock = repo.get_active_book_lock(db, pair.pair_id)
            if active_lock:
                locked_book = repo.get_book_by_id(db, active_lock.book_id)
                if locked_book and locked_book.status == BOOK_STATUS_READING and (
                    not current_reading or locked_book.book_id != current_reading.book_id
                ):
                    _switch_away_reading_book(db, locked_book)
                elif locked_book and locked_book.status != BOOK_STATUS_READING:
                    db.delete(active_lock)
                db.flush()
            book = _create_reading_book_row(
                db,
                pair_id=pair.pair_id,
                title=title[:200],
                author=author[:200],
                total_pages=total_pages,
                catalog_ref=catalog_ref,
                created_by=current_user["user_id"],
            )
            db.commit()
            target_partner_id = partner_id(pair, current_user["user_id"])
            return {
                "mode": "book",
                "book": book_progress(db, book, current_user["user_id"], target_partner_id),
            }

        now = utc_now()
        row = BookSwitchRequest(
            request_id=new_id("bsr"),
            pair_id=pair.pair_id,
            requested_by=current_user["user_id"],
            status="pending",
            from_book_id=current_reading.book_id if current_reading else None,
            catalog_id=catalog_ref,
            title=title[:200],
            author=author[:200],
            total_pages=total_pages,
            created_at=now,
            responded_at=None,
            responded_by=None,
        )
        repo.add_book_switch_request(db, row)
        db.commit()
        return {"mode": "switch_request", "switch_request": _switch_request_dict(db, row, current_user["user_id"])}


def respond_book_switch_request(
    db: Session, current_user: Dict[str, Any], request_id: str, action: str
) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        raise ApiError(40301, "请先绑定共读伙伴", 403)
    act = (action or "").strip().lower()
    if act not in {"approve", "reject"}:
        raise ApiError(40026, "action 须为 approve 或 reject", 400)

    with acquire_named_locks(f"create-book:{pair.pair_id}"):
        row = repo.get_book_switch_request(db, request_id)
        if not row or row.pair_id != pair.pair_id:
            raise ApiError(40424, "换书申请不存在", 404)
        if row.status != "pending":
            raise ApiError(40027, "换书申请已处理", 400)
        if row.requested_by == current_user["user_id"]:
            raise ApiError(40304, "不能处理自己发起的换书申请", 403)

        now = utc_now()
        if act == "reject":
            row.status = "rejected"
            row.responded_at = now
            row.responded_by = current_user["user_id"]
            db.commit()
            return {"status": "rejected", "switch_request": _switch_request_dict(db, row, current_user["user_id"])}

        from_book = repo.get_book_by_id(db, row.from_book_id) if row.from_book_id else None
        if from_book and from_book.status == "reading":
            _switch_away_reading_book(db, from_book)
            db.flush()

        active_lock = repo.get_active_book_lock(db, pair.pair_id)
        if active_lock:
            locked_book = repo.get_book_by_id(db, active_lock.book_id)
            if locked_book and locked_book.status == "reading" and (
                not from_book or locked_book.book_id != from_book.book_id
            ):
                _switch_away_reading_book(db, locked_book)
            elif locked_book and locked_book.status != "reading":
                db.delete(active_lock)
            db.flush()

        if row.catalog_id:
            existing = repo.get_pair_book_by_catalog_id(db, pair.pair_id, row.catalog_id)
            if existing and existing.status == "reading":
                row.status = "approved"
                row.responded_at = now
                row.responded_by = current_user["user_id"]
                db.commit()
                target_partner_id = partner_id(pair, current_user["user_id"])
                return {
                    "status": "approved",
                    "book": book_progress(db, existing, current_user["user_id"], target_partner_id),
                }

        book = _create_reading_book_row(
            db,
            pair_id=pair.pair_id,
            title=row.title,
            author=row.author,
            total_pages=int(row.total_pages),
            catalog_ref=row.catalog_id,
            created_by=row.requested_by,
        )
        row.status = "approved"
        row.responded_at = now
        row.responded_by = current_user["user_id"]
        db.commit()
        target_partner_id = partner_id(pair, current_user["user_id"])
        return {
            "status": "approved",
            "book": book_progress(db, book, current_user["user_id"], target_partner_id),
        }


def create_book(db: Session, current_user: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        user_id = current_user["user_id"]
        pid = personal_pair_id(user_id)
        with acquire_named_locks(f"create-book:{pid}"):
            title, author, total_pages, _catalog_ref = _resolve_new_book_fields(db, payload)
            current_reading = repo.get_current_book(db, pid)
            if current_reading:
                _switch_away_reading_book(db, current_reading)
                db.flush()
            book = _create_reading_book_row(
                db,
                pair_id=pid,
                title=title[:200],
                author=author[:200],
                total_pages=total_pages,
                catalog_ref=None,
                created_by=user_id,
            )
            db.commit()
            return {
                "mode": "book",
                "book": book_progress(db, book, user_id, user_id),
            }
    if bool(payload.get("replace_current")):
        return create_book_switch_request(db, current_user, payload)
    with acquire_named_locks(f"create-book:{pair.pair_id}"):
        locked_pair = repo.get_pair_for_update(db, pair.pair_id)
        if not locked_pair or locked_pair.status != "active":
            raise ApiError(40301, "请先绑定共读伙伴后再添加书籍", 403)

        _assert_no_blocking_switch_request(db, pair.pair_id, current_user["user_id"])

        catalog_ref_early = (payload.get("catalog_id") or "").strip() or None
        if catalog_ref_early:
            existing = repo.get_pair_book_by_catalog_id(db, pair.pair_id, catalog_ref_early)
            if existing and existing.status == BOOK_STATUS_READING:
                target_partner_id = partner_id(pair, current_user["user_id"])
                return {
                    "mode": "book",
                    "book": book_progress(db, existing, current_user["user_id"], target_partner_id),
                }

        current_reading = repo.get_current_book(db, pair.pair_id)
        if current_reading:
            raise ApiError(40021, "当前已有在读书，请申请换书并等待伙伴同意", 400)

    # 加入共读须伙伴同意（含第一本）
    return create_book_switch_request(db, current_user, payload)


def get_current_pair_book(db: Session, current_user: Dict[str, Any]) -> Dict[str, Any]:
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair:
        book = repo.get_current_book(db, personal_pair_id(current_user["user_id"]))
        return {"book": book_progress(db, book, current_user["user_id"], current_user["user_id"])} if book else {"book": None}
    book = repo.get_current_book(db, pair.pair_id)
    if not book:
        return {"book": None}
    return {"book": book_progress(db, book, current_user["user_id"], partner_id(pair, current_user["user_id"]))}


def _trim_quote_text(text: str, max_len: int = 800) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) > max_len:
        return cleaned[:max_len]
    return cleaned


def create_entry(
    db: Session,
    current_user: Dict[str, Any],
    book_id: str,
    page: int,
    note_content: str,
    mark_finished: bool,
    client_request_id: Optional[str],
    quote_text: str = "",
) -> Dict[str, Any]:
    book = repo.get_book_by_id(db, book_id)
    if not book:
        raise ApiError(40411, "书籍不存在", 404)
    pair = can_access_book(db, book, current_user["user_id"])
    if not pair and not is_personal_book(book, current_user["user_id"]):
        raise ApiError(40302, "无权操作这本书", 403)
    if book.status != "reading":
        raise ApiError(40022, "这本书已归档，不能再更新进度", 400)

    duplicated = repo.get_duplicate_entry(db, book_id, current_user["user_id"], client_request_id)
    if duplicated:
        return book_progress_for_viewer(db, book, current_user["user_id"])

    current_page = effective_user_book_progress(db, book, current_user["user_id"])
    final_page = int(book.total_pages) if mark_finished else int(page)
    if final_page < current_page:
        raise ApiError(40023, "页码不能小于当前已记录的页码", 400)
    if final_page > int(book.total_pages):
        raise ApiError(40024, "页码不能超过书籍总页数", 400)

    safe_note = (note_content or "").strip()
    safe_quote = _trim_quote_text(quote_text)

    entry = Entry(
        entry_id=new_id("e"),
        book_id=book_id,
        user_id=current_user["user_id"],
        page=final_page,
        note_content=safe_note,
        quote_text=safe_quote or None,
        created_at=utc_now(),
        client_request_id=client_request_id,
    )
    db.add(entry)

    target_partner_id = partner_id(pair, current_user["user_id"]) if pair else current_user["user_id"]
    partner_progress = effective_user_book_progress(db, book, target_partner_id)
    if final_page >= int(book.total_pages) and partner_progress >= int(book.total_pages):
        book.status = BOOK_STATUS_FINISHED
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
    pair = can_access_book(db, book, current_user["user_id"])
    if not pair and not is_personal_book(book, current_user["user_id"]):
        raise ApiError(40302, "无权查看这本书", 403)
    my_progress = effective_user_book_progress(db, book, current_user["user_id"])
    target_partner_id = partner_id(pair, current_user["user_id"]) if pair else current_user["user_id"]
    partner_progress = effective_user_book_progress(db, book, target_partner_id)
    total_entries = repo.count_entries_for_book(db, book_id)
    offset = (page - 1) * page_size
    rows = repo.list_entries_for_book(db, book_id, offset, page_size)
    mark = repo.get_read_mark(db, current_user["user_id"], book_id)
    unread_count = repo.count_unread_entries(db, book_id, current_user["user_id"], mark.last_read_at if mark else None)

    entry_ids = [row.entry_id for row in rows]
    feed_by_entry = feed_repo.map_posts_by_entry_ids(db, entry_ids)
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
                "quote_text": None if is_locked else (row.quote_text or ""),
                "note_content": None if is_locked else row.note_content,
                "is_locked": is_locked,
                "unlock_at_page": row.page if is_locked else None,
                "created_at": row.created_at,
                "replies": replies,
                "is_mine": row.user_id == current_user["user_id"],
                "is_unread": is_unread,
                "feed_post_id": feed_by_entry[row.entry_id].post_id if row.entry_id in feed_by_entry else None,
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
    pair = can_access_book(db, book, current_user["user_id"])
    if not pair and not is_personal_book(book, current_user["user_id"]):
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
    pair = can_access_book(db, book, current_user["user_id"]) if book else None
    if not pair and (not book or not is_personal_book(book, current_user["user_id"])):
        raise ApiError(40303, "无权回复这条记录", 403)
    my_progress = effective_user_book_progress(db, book, current_user["user_id"])
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
    completed_books = count_truly_finished_books(db, repo.list_pair_ids_for_user(db, user_id), start_iso)
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
