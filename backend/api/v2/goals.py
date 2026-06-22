from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v2.common import GoalPayload, get_current_user, get_request_id, ok
from common.db import get_db_session
from common.errors import ApiError
from common.models import ReadingGoal
from service import reading_service


router = APIRouter(prefix="/profile", tags=["v2-goals"])


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_goal() -> Dict[str, Any]:
    return {
        "period_days": 30,
        "target_books": 1,
        "target_days": 20,
        "updated_at": None,
    }


def _goal_progress(db: Session, user_id: str, goal: Dict[str, Any]) -> Dict[str, Any]:
    return reading_service.goal_progress(db, user_id, goal)


def _goal_dict(row: Optional[ReadingGoal]) -> Dict[str, Any]:
    if not row:
        return _default_goal()
    return {
        "period_days": row.period_days,
        "target_books": row.target_books,
        "target_days": row.target_days,
        "updated_at": row.updated_at,
    }


@router.get("/goals")
def get_goals(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    row = db.execute(select(ReadingGoal).where(ReadingGoal.user_id == current_user["user_id"])).scalar_one_or_none()
    goal = _goal_dict(row)
    return ok(
        {
            "goal": goal,
            "progress": _goal_progress(db, current_user["user_id"], goal),
        },
        request_id=request_id,
    )


@router.put("/goals")
def put_goals(
    payload: GoalPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    if payload.period_days < 7 or payload.period_days > 365:
        raise ApiError(40084, "周期天数范围应为 7-365", 400)
    if payload.target_books < 1 or payload.target_books > 200:
        raise ApiError(40085, "目标书籍范围应为 1-200", 400)
    if payload.target_days < 1 or payload.target_days > payload.period_days:
        raise ApiError(40086, "目标天数不能超过周期天数", 400)

    row = db.execute(select(ReadingGoal).where(ReadingGoal.user_id == current_user["user_id"])).scalar_one_or_none()
    now = _utc_now()
    if row:
        row.period_days = payload.period_days
        row.target_books = payload.target_books
        row.target_days = payload.target_days
        row.updated_at = now
    else:
        row = ReadingGoal(
            user_id=current_user["user_id"],
            period_days=payload.period_days,
            target_books=payload.target_books,
            target_days=payload.target_days,
            updated_at=now,
        )
        db.add(row)
    db.commit()
    goal = _goal_dict(row)
    return ok(
        {
            "goal": goal,
            "progress": _goal_progress(db, current_user["user_id"], goal),
        },
        request_id=request_id,
    )
