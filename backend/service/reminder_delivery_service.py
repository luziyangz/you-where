"""
提醒订阅消息投递日志（reminder_delivery_logs 表）读写。
供 dispatch_reminders 脚本与集成测试复用。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from common.models import ReminderDeliveryLog


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_delivery_log(db: Session, user_id: str, delivery_date: str) -> Optional[ReminderDeliveryLog]:
    from sqlalchemy import select

    return db.execute(
        select(ReminderDeliveryLog).where(
            ReminderDeliveryLog.user_id == user_id,
            ReminderDeliveryLog.delivery_date == delivery_date,
        )
    ).scalar_one_or_none()


def record_delivery_log(
    db: Session,
    user_id: str,
    delivery_date: str,
    status: str,
    error_message: str = "",
) -> ReminderDeliveryLog:
    """按用户+日期 upsert 投递记录；依赖表级唯一约束防重复。"""
    row = get_delivery_log(db, user_id, delivery_date)
    now = utc_now_iso()
    msg = (error_message or "")[:1000]
    if row:
        row.status = status
        row.error_message = msg
        row.created_at = now
    else:
        row = ReminderDeliveryLog(
            delivery_id=f"rd_{uuid.uuid4().hex[:16]}",
            user_id=user_id,
            delivery_date=delivery_date,
            status=status,
            error_message=msg,
            created_at=now,
        )
        db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = get_delivery_log(db, user_id, delivery_date)
        if not row:
            raise
        row.status = status
        row.error_message = msg
        row.created_at = now
        db.commit()
    db.refresh(row)
    return row
