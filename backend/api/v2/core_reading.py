from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.v2.common import calc_days_since, get_active_pair, get_current_user, get_partner_id, get_request_id, ok
from common.config import settings
from common.db import get_db_session
from common.errors import ApiError
from common.locks import acquire_named_locks
from common.models import ActiveBookLock, ActivePairLock, Book, Entry, Pair, ReadMark, Reply, SessionModel, User
from service import reading_service


router = APIRouter(tags=["v2-core-reading"])
_wechat_access_token = ""
_wechat_access_token_expires_at = 0.0

TEST_USERS = {
    "a": {
        "open_id": "youzainaye_test_user_a",
        "nickname": "测试用户A",
        "join_code": "900001",
    },
    "b": {
        "open_id": "youzainaye_test_user_b",
        "nickname": "测试用户B",
        "join_code": "900002",
    },
}

REVIEW_USER = {
    "open_id": "youzainaye_review_user",
    "nickname": "微信审核员",
    "join_code": "900003",
}


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
        "phone_number": user.phone_number,
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


def _current_book(db: Session, pair_id: str) -> Optional[Book]:
    return db.execute(select(Book).where(and_(Book.pair_id == pair_id, Book.status == "reading")).order_by(desc(Book.created_at))).scalars().first()


def _book_progress(db: Session, book: Book, user_id: str, partner_id: str) -> Dict[str, Any]:
    return reading_service.book_progress(db, book, user_id, partner_id)


class LoginPayload(BaseModel):
    code: str
    debug_open_id: Optional[str] = None


class PhoneLoginPayload(BaseModel):
    code: str
    phone_code: Optional[str] = None
    debug_open_id: Optional[str] = None
    debug_phone_number: Optional[str] = None


class TestLoginPayload(BaseModel):
    role: str = "a"


class ReviewLoginPayload(BaseModel):
    account: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


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


def _fetch_json(url: str, method: str = "GET", data: Optional[Dict[str, Any]] = None, timeout_seconds: int = 8) -> Dict[str, Any]:
    body = json.dumps(data or {}).encode("utf-8") if method.upper() != "GET" else None
    req = UrlRequest(
        url,
        data=body,
        method=method.upper(),
        headers={"Content-Type": "application/json", "User-Agent": "youzainaye-mini/1.0"},
    )
    with urlopen(req, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _exchange_wechat_open_id(code: str, debug_open_id: Optional[str] = None) -> str:
    if debug_open_id:
        return debug_open_id.strip()

    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        raise ApiError(40003, "未配置微信小程序 AppID/AppSecret，暂不能使用微信登录", 400)

    query = urlencode(
        {
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
            "js_code": code,
            "grant_type": "authorization_code",
        }
    )
    payload = _fetch_json(f"https://api.weixin.qq.com/sns/jscode2session?{query}")
    open_id = str(payload.get("openid") or "").strip()
    if not open_id:
        errcode = int(payload.get("errcode") or 0)
        errmsg = str(payload.get("errmsg") or "").strip()
        if errcode in {40029, 40163} or "invalid code" in errmsg.lower():
            raise ApiError(
                40001,
                "微信登录凭证无效，请重新点击登录；如果持续出现，请确认服务器 WECHAT_APP_ID/WECHAT_APP_SECRET 与小程序 AppID 一致",
                400,
            )
        raise ApiError(40001, errmsg or "微信登录凭证无效，请重试", 400)
    return open_id


def _fetch_wechat_access_token() -> str:
    global _wechat_access_token, _wechat_access_token_expires_at
    if _wechat_access_token and time.monotonic() < _wechat_access_token_expires_at:
        return _wechat_access_token

    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        raise ApiError(40003, "未配置微信小程序 AppID/AppSecret，暂不能使用手机号登录", 400)

    query = urlencode(
        {
            "grant_type": "client_credential",
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
        }
    )
    payload = _fetch_json(f"https://api.weixin.qq.com/cgi-bin/token?{query}")
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise ApiError(40003, payload.get("errmsg") or "获取微信访问凭证失败", 400)
    expires_in = int(payload.get("expires_in") or 7200)
    _wechat_access_token = access_token
    _wechat_access_token_expires_at = time.monotonic() + max(60, expires_in - 300)
    return access_token


def _normalize_phone_number(value: str) -> str:
    phone = re.sub(r"\D", "", value or "")
    if len(phone) < 8 or len(phone) > 15:
        raise ApiError(40004, "手机号格式不合法", 400)
    return phone


def _exchange_phone_number(phone_code: Optional[str], debug_phone_number: Optional[str] = None) -> str:
    if debug_phone_number:
        return _normalize_phone_number(debug_phone_number)
    if not phone_code:
        raise ApiError(40004, "缺少手机号授权凭证", 400)

    access_token = _fetch_wechat_access_token()
    payload = _fetch_json(
        f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}",
        method="POST",
        data={"code": phone_code},
    )
    if int(payload.get("errcode") or 0) != 0:
        raise ApiError(40004, payload.get("errmsg") or "手机号授权失败，请重试", 400)

    phone_info = payload.get("phone_info") if isinstance(payload.get("phone_info"), dict) else {}
    return _normalize_phone_number(str(phone_info.get("phoneNumber") or phone_info.get("purePhoneNumber") or ""))


def _get_or_create_user(db: Session, open_id: str, phone_number: Optional[str] = None) -> User:
    user = db.execute(select(User).where(User.open_id == open_id)).scalar_one_or_none()
    if not user and phone_number:
        user = db.execute(select(User).where(User.phone_number == phone_number)).scalar_one_or_none()
        if user and user.open_id != open_id:
            conflict = db.execute(select(User).where(User.open_id == open_id)).scalar_one_or_none()
            if conflict:
                raise ApiError(40005, "该微信账号或手机号已绑定其他用户", 400)
            user.open_id = open_id

    if not user:
        now = _utc_now()
        user = User(
            user_id=_new_id("u"),
            open_id=open_id,
            phone_number=phone_number,
            nickname=f"书友_{open_id[-4:]}",
            avatar="",
            join_code=_join_code(open_id + now),
            agreement_accepted_at=None,
            created_at=now,
        )
        db.add(user)
        db.flush()
        return user

    if phone_number and user.phone_number != phone_number:
        existing = db.execute(select(User).where(User.phone_number == phone_number, User.user_id != user.user_id)).scalar_one_or_none()
        if existing:
            raise ApiError(40005, "该手机号已绑定其他用户", 400)
        user.phone_number = phone_number
        db.flush()
    return user


def _normalize_test_role(role: str) -> str:
    value = (role or "a").strip().lower()
    if value in {"1", "user_a", "test_a"}:
        return "a"
    if value in {"2", "user_b", "test_b"}:
        return "b"
    if value in TEST_USERS:
        return value
    raise ApiError(40006, "测试用户角色仅支持 A 或 B", 400)


def _prepare_test_user(db: Session, role: str) -> User:
    spec = TEST_USERS[_normalize_test_role(role)]
    user = _get_or_create_user(db, spec["open_id"])
    conflict = db.execute(select(User).where(User.join_code == spec["join_code"], User.user_id != user.user_id)).scalar_one_or_none()
    if conflict:
        conflict.join_code = _join_code(conflict.open_id + _utc_now())
    user.nickname = spec["nickname"]
    user.avatar = ""
    user.join_code = spec["join_code"]
    db.flush()
    return user


def _prepare_review_user(db: Session) -> User:
    spec = REVIEW_USER
    user = _get_or_create_user(db, spec["open_id"])
    conflict = db.execute(select(User).where(User.join_code == spec["join_code"], User.user_id != user.user_id)).scalar_one_or_none()
    if conflict:
        conflict.join_code = _join_code(conflict.open_id + _utc_now())
    user.nickname = spec["nickname"]
    user.avatar = ""
    user.join_code = spec["join_code"]
    db.flush()
    return user


def _create_login_session(db: Session, user: User) -> Dict[str, Any]:
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
    return {
        "token": token,
        "user": data_user,
        "need_agreement": not bool(user.agreement_accepted_at),
    }


@router.post("/auth/login")
def login(
    payload: LoginPayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    open_id = _exchange_wechat_open_id(payload.code, payload.debug_open_id)
    user = _get_or_create_user(db, open_id)
    return ok(_create_login_session(db, user), request_id=request_id)


@router.post("/auth/phone-login")
def phone_login(
    payload: PhoneLoginPayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    open_id = _exchange_wechat_open_id(payload.code, payload.debug_open_id)
    phone_number = _exchange_phone_number(payload.phone_code, payload.debug_phone_number)
    user = _get_or_create_user(db, open_id, phone_number=phone_number)
    return ok(_create_login_session(db, user), request_id=request_id)


@router.post("/auth/test-login")
def test_login(
    payload: TestLoginPayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    if not settings.ENABLE_TEST_USERS:
        raise ApiError(40404, "测试用户入口未启用", 404)
    user = _prepare_test_user(db, payload.role)
    return ok(_create_login_session(db, user), request_id=request_id)


@router.post("/auth/review-login")
def review_login(
    payload: ReviewLoginPayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    if not settings.ENABLE_REVIEW_LOGIN:
        raise ApiError(40404, "审核登录入口未启用", 404)
    if not settings.WECHAT_REVIEW_PASSWORD:
        raise ApiError(40404, "审核登录密码未配置", 404)

    expected_account = settings.WECHAT_REVIEW_ACCOUNT or "reviewer"
    account_ok = hmac.compare_digest((payload.account or "").strip(), expected_account)
    password_ok = hmac.compare_digest(payload.password or "", settings.WECHAT_REVIEW_PASSWORD)
    if not account_ok or not password_ok:
        raise ApiError(40104, "审核账号或密码错误", 401)

    user = _prepare_review_user(db)
    return ok(_create_login_session(db, user), request_id=request_id)


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


def me(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    return ok(current_user, request_id=request_id)


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


def me_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    from service import reading_service

    return ok(reading_service.get_current_user_stats(db, current_user), request_id=request_id)


def home(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    from service import reading_service

    return ok(reading_service.get_home(db, current_user), request_id=request_id)


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

    with acquire_named_locks(f"bind-user:{current_user['user_id']}", f"bind-user:{target.user_id}"):
        db.execute(
            select(User)
            .where(User.user_id.in_([current_user["user_id"], target.user_id]))
            .order_by(User.user_id.asc())
            .with_for_update()
        ).scalars().all()

        if get_active_pair(db, current_user["user_id"]):
            raise ApiError(40012, "你已与其他伙伴共读，请先解绑再绑定新伙伴", 400)
        if get_active_pair(db, target.user_id):
            raise ApiError(40012, "对方已与其他伙伴共读，无法绑定", 400)

        now = _utc_now()
        pair_id = _new_id("p")
        pair = Pair(
            pair_id=pair_id,
            user_a_id=current_user["user_id"],
            user_b_id=target.user_id,
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(pair)
        db.add_all(
            [
                ActivePairLock(user_id=current_user["user_id"], pair_id=pair_id, created_at=now),
                ActivePairLock(user_id=target.user_id, pair_id=pair_id, created_at=now),
            ]
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ApiError(40012, "你或对方已有正在生效的共读关系", 400)
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
    db.query(ActivePairLock).filter(ActivePairLock.pair_id == pair.pair_id).delete(synchronize_session=False)
    db.query(ActiveBookLock).filter(ActiveBookLock.pair_id == pair.pair_id).delete(synchronize_session=False)
    db.commit()
    return ok({"pair_id": pair.pair_id, "status": "unbound"}, request_id=request_id)


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
    partner_id = get_partner_id(pair, current_user["user_id"])
    my_progress = reading_service.effective_user_book_progress(db, book, current_user["user_id"])
    partner_progress = reading_service.effective_user_book_progress(db, book, partner_id)

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
    my_progress = reading_service.effective_user_book_progress(db, book, current_user["user_id"])
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
