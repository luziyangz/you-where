# -*- coding: utf-8 -*-
"""阶段5：reading_goals + reminder_configs + reminder_delivery_logs"""

from datetime import date

from api.v2 import reminders as reminders_module
from tests_mysql.helpers import _session
from common.models import ReadingGoal, ReminderConfig, ReminderDeliveryLog
from service.reminder_delivery_service import get_delivery_log, record_delivery_log
from tests_mysql.helpers import assert_table_has_row, login, wipe_business_tables


def test_reading_goal_crud(app_client, auth_header):
    wipe_business_tables()
    token, user = login(app_client, "mysql_goal_u", "目标用户")
    h = auth_header(token)

    default = app_client.get("/api/v2/users/me/reading-goal", headers=h)
    assert default.status_code == 200
    assert default.json()["data"]["goal"]["period_days"] == 30

    saved = app_client.put(
        "/api/v2/users/me/reading-goal",
        json={"period_days": 60, "target_books": 5, "target_days": 40},
        headers=h,
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["goal"]["target_books"] == 5
    assert_table_has_row(ReadingGoal, user_id=user["user_id"])

    db = _session()
    row = db.query(ReadingGoal).filter(ReadingGoal.user_id == user["user_id"]).one()
    assert row.target_books == 5
    db.close()


def test_reminder_config_and_delivery_log(app_client, auth_header, monkeypatch):
    wipe_business_tables()
    monkeypatch.setattr(reminders_module.settings, "WECHAT_REMINDER_TEMPLATE_ID", "")
    token, user = login(app_client, "mysql_rem_u", "提醒用户")
    h = auth_header(token)

    put_cfg = app_client.put(
        "/api/v2/users/me/reminder-config",
        json={"enabled": True, "remind_time": "21:00", "timezone": "Asia/Shanghai"},
        headers=h,
    )
    assert put_cfg.status_code == 200
    assert_table_has_row(ReminderConfig, user_id=user["user_id"])

    get_cfg = app_client.get("/api/v2/users/me/reminder-config", headers=h)
    assert get_cfg.json()["data"]["reminder"]["enabled"] is True

    today = date.today().isoformat()
    db = _session()
    record_delivery_log(db, user["user_id"], today, "sent", "")
    assert get_delivery_log(db, user["user_id"], today) is not None
    db.close()
    assert_table_has_row(ReminderDeliveryLog, user_id=user["user_id"], delivery_date=today)
