# -*- coding: utf-8 -*-
"""阶段1：users + sessions"""

from sqlalchemy import select

from common.models import SessionModel, User
from tests_mysql.helpers import assert_table_has_row, login, wipe_business_tables, _session


def test_login_persists_user_and_session(app_client, auth_header):
    wipe_business_tables()
    token, user = login(app_client, "mysql_u1", "用户甲")
    assert token
    assert_table_has_row(User, user_id=user["user_id"])
    db = _session()
    try:
        sess = db.execute(select(SessionModel).where(SessionModel.token == token)).scalar_one_or_none()
        assert sess is not None
        assert sess.user_id == user["user_id"]
    finally:
        db.close()

    me = app_client.get("/api/v2/users/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["data"]["user_id"] == user["user_id"]
