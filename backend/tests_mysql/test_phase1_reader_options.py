# -*- coding: utf-8 -*-
"""阶段1 扩展：users.reader_options 读写。"""

from tests_mysql.helpers import _session, login, wipe_business_tables
from common.models import User


def test_reader_options_roundtrip(app_client, auth_header):
    wipe_business_tables()
    token, user = login(app_client, "mysql_ro_u", "阅读器")
    h = auth_header(token)

    default = app_client.get("/api/v2/users/me/reader-options", headers=h)
    assert default.status_code == 200
    assert default.json()["data"]["reader_options"]["font_size"] == 32

    saved = app_client.put(
        "/api/v2/users/me/reader-options",
        json={"font_size": 36, "reading_mode": "night", "brightness": 80},
        headers=h,
    )
    assert saved.status_code == 200
    opts = saved.json()["data"]["reader_options"]
    assert opts["font_size"] == 36
    assert opts["reading_mode"] == "night"
    assert opts["brightness"] == 80

    db = _session()
    row = db.query(User).filter(User.user_id == user["user_id"]).one()
    assert row.reader_options is not None
    assert "36" in row.reader_options
    db.close()
