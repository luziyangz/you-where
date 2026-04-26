from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import re

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v2.common import ReminderPayload, get_current_user, get_request_id, ok
from common.config import settings
from common.db import get_db_session
from common.errors import ApiError
from common.models import ReminderConfig


router = APIRouter(prefix="/profile", tags=["v2-reminders"])

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _delivery_meta() -> Dict[str, Any]:
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


def _reminder_dict(row: Optional[ReminderConfig]) -> Dict[str, Any]:
    delivery_meta = _delivery_meta()
    if not row:
        return {
            "enabled": True,
            "remind_time": "21:00",
            "timezone": "Asia/Shanghai",
            "updated_at": None,
            **delivery_meta,
        }
    return {
        "enabled": bool(row.enabled),
        "remind_time": row.remind_time,
        "timezone": row.timezone,
        "updated_at": row.updated_at,
        **delivery_meta,
    }


@router.get("/reminders")
def get_reminders(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    row = db.execute(select(ReminderConfig).where(ReminderConfig.user_id == current_user["user_id"])).scalar_one_or_none()
    return ok({"reminder": _reminder_dict(row)}, request_id=request_id)


@router.put("/reminders")
def put_reminders(
    payload: ReminderPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    if not TIME_PATTERN.match(payload.remind_time or ""):
        raise ApiError(40087, "提醒时间格式应为 HH:MM", 400)
    if not payload.timezone or len(payload.timezone) > 64:
        raise ApiError(40088, "时区参数不合法", 400)

    row = db.execute(select(ReminderConfig).where(ReminderConfig.user_id == current_user["user_id"])).scalar_one_or_none()
    now = _utc_now()
    if row:
        row.enabled = 1 if payload.enabled else 0
        row.remind_time = payload.remind_time
        row.timezone = payload.timezone
        row.updated_at = now
    else:
        row = ReminderConfig(
            user_id=current_user["user_id"],
            enabled=1 if payload.enabled else 0,
            remind_time=payload.remind_time,
            timezone=payload.timezone,
            updated_at=now,
        )
        db.add(row)
    db.commit()
    return ok({"reminder": _reminder_dict(row)}, request_id=request_id)
