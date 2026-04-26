"""
Dispatch WeChat subscription reminders for enabled reminder configs.

Run from a scheduler, for example every 5 minutes:
    cd backend
    python scripts/dispatch_reminders.py

Required env:
    WECHAT_APP_ID
    WECHAT_APP_SECRET
    WECHAT_REMINDER_TEMPLATE_ID

The template data keys below must match the selected WeChat template.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.config import settings  # noqa: E402
from common.db import SessionLocal, engine  # noqa: E402
from common.models import Base, ReminderConfig, ReminderDeliveryLog, User  # noqa: E402


TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _http_json(url: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None
    method = "GET"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        method = "POST"

    req = Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"WeChat request failed: {exc}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"WeChat response is not JSON: {body[:200]}") from exc


def _get_access_token() -> str:
    query = urlencode(
        {
            "grant_type": "client_credential",
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
        }
    )
    payload = _http_json(f"{TOKEN_URL}?{query}")
    token = payload.get("access_token")
    if token:
        return token
    raise RuntimeError(f"WeChat token error: {payload.get('errcode')} {payload.get('errmsg')}")


def _safe_zone(timezone_name: str) -> tzinfo:
    try:
        return ZoneInfo(timezone_name or "Asia/Shanghai")
    except ZoneInfoNotFoundError:
        if (timezone_name or "Asia/Shanghai") == "Asia/Shanghai":
            return timezone(timedelta(hours=8))
        return timezone.utc


def _due_delivery_date(config: ReminderConfig, now_utc: datetime) -> Optional[str]:
    zone = _safe_zone(config.timezone)
    local_now = now_utc.astimezone(zone)
    if local_now.strftime("%H:%M") < config.remind_time:
        return None
    return local_now.date().isoformat()


def _delivery_log(db, user_id: str, delivery_date: str) -> Optional[ReminderDeliveryLog]:
    return db.execute(
        select(ReminderDeliveryLog).where(
            ReminderDeliveryLog.user_id == user_id,
            ReminderDeliveryLog.delivery_date == delivery_date,
        )
    ).scalar_one_or_none()


def _record_delivery(db, user_id: str, delivery_date: str, status: str, error_message: str = "") -> None:
    row = _delivery_log(db, user_id, delivery_date)
    now = _utc_now()
    if row:
        row.status = status
        row.error_message = error_message[:1000]
        row.created_at = now
    else:
        db.add(
            ReminderDeliveryLog(
                delivery_id=f"rd_{uuid.uuid4().hex}",
                user_id=user_id,
                delivery_date=delivery_date,
                status=status,
                error_message=error_message[:1000],
                created_at=now,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def _send_reminder(access_token: str, user: User, config: ReminderConfig) -> None:
    payload = {
        "touser": user.open_id,
        "template_id": settings.WECHAT_REMINDER_TEMPLATE_ID,
        "page": "pages/home/index",
        "data": {
            "thing1": {"value": "今天还没有记录阅读进度"},
            "time2": {"value": config.remind_time},
            "thing3": {"value": "打开小程序记录你在哪页"},
        },
    }
    response = _http_json(f"{SEND_URL}?access_token={access_token}", payload)
    if response.get("errcode", 0) != 0:
        raise RuntimeError(f"WeChat subscribe send error: {response.get('errcode')} {response.get('errmsg')}")


def _validate_env() -> Optional[str]:
    missing = [
        key
        for key, value in {
            "WECHAT_APP_ID": settings.WECHAT_APP_ID,
            "WECHAT_APP_SECRET": settings.WECHAT_APP_SECRET,
            "WECHAT_REMINDER_TEMPLATE_ID": settings.WECHAT_REMINDER_TEMPLATE_ID,
        }.items()
        if not value
    ]
    if missing:
        return f"Reminder dispatch skipped, missing env: {', '.join(missing)}"
    return None


def main() -> int:
    env_error = _validate_env()
    if env_error:
        print(env_error)
        return 0

    Base.metadata.create_all(bind=engine)
    access_token = _get_access_token()
    now_utc = datetime.now(timezone.utc)
    sent = 0
    failed = 0
    skipped = 0

    db = SessionLocal()
    try:
        rows = db.execute(
            select(ReminderConfig, User)
            .join(User, User.user_id == ReminderConfig.user_id)
            .where(ReminderConfig.enabled == 1)
        ).all()

        for config, user in rows:
            delivery_date = _due_delivery_date(config, now_utc)
            if not delivery_date:
                skipped += 1
                continue

            existing = _delivery_log(db, user.user_id, delivery_date)
            if existing and existing.status == "success":
                skipped += 1
                continue

            try:
                _send_reminder(access_token, user, config)
                _record_delivery(db, user.user_id, delivery_date, "success")
                sent += 1
            except Exception as exc:  # noqa: BLE001 - scheduler must log and continue per user.
                _record_delivery(db, user.user_id, delivery_date, "failed", str(exc))
                failed += 1
                print(f"Reminder failed for user={user.user_id}: {exc}")
    finally:
        db.close()

    print(f"Reminder dispatch finished: sent={sent}, failed={failed}, skipped={skipped}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
