from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from typing import Any, Dict, Optional

from fastapi import Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from common.db import get_db_session
from common.errors import ApiError
from common.models import Pair, SessionModel, User


def make_request_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(6)


def ok(data: Dict[str, Any], request_id: Optional[str] = None) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "code": 0,
            "message": "ok",
            "data": data,
            "request_id": request_id or make_request_id(),
        },
    )


def calc_days_since(created_at: str) -> int:
    try:
        start = datetime.fromisoformat((created_at or "").replace("Z", "+00:00"))
    except Exception:
        return 1
    return max(1, (datetime.now(timezone.utc) - start).days + 1)


def _to_user_dict(user: User) -> Dict[str, Any]:
    return {
        "user_id": user.user_id,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "join_code": user.join_code,
        "phone_number": user.phone_number,
        "agreement_accepted_at": user.agreement_accepted_at,
        "join_days": calc_days_since(user.created_at),
    }


def get_request_id(x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id")) -> str:
    if x_request_id:
        return x_request_id[:64]
    return make_request_id()


def get_current_user(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(40100, "请先登录后再操作", 401)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise ApiError(40100, "请先登录后再操作", 401)

    session_row = db.execute(select(SessionModel).where(SessionModel.token == token)).scalar_one_or_none()
    if not session_row:
        raise ApiError(40100, "登录状态已失效，请重新登录", 401)

    try:
        expires_at = datetime.fromisoformat((session_row.expires_at or "").replace("Z", "+00:00"))
    except Exception:
        expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    if expires_at <= datetime.now(timezone.utc):
        raise ApiError(40100, "登录状态已失效，请重新登录", 401)

    user_row = db.execute(select(User).where(User.user_id == session_row.user_id)).scalar_one_or_none()
    if not user_row:
        raise ApiError(40100, "登录状态已失效，请重新登录", 401)
    return _to_user_dict(user_row)


def get_active_pair(db: Session, user_id: str) -> Optional[Pair]:
    return db.execute(
        select(Pair).where(
            Pair.status == "active",
            ((Pair.user_a_id == user_id) | (Pair.user_b_id == user_id)),
        )
    ).scalar_one_or_none()


def get_partner_id(pair: Pair, user_id: str) -> str:
    return pair.user_b_id if pair.user_a_id == user_id else pair.user_a_id


class GoalPayload(BaseModel):
    period_days: int
    target_books: int
    target_days: int


class ReminderPayload(BaseModel):
    enabled: bool
    remind_time: str
    timezone: str
