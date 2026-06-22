# -*- coding: utf-8 -*-
"""阶段2：pairs + active_pair_locks"""

from tests_mysql.helpers import assert_table_has_row, login, wipe_business_tables
from common.models import ActivePairLock, Pair


def test_pair_bind_creates_pair_and_locks(app_client, auth_header):
    wipe_business_tables()
    ta, ua = login(app_client, "mysql_pa", "甲")
    tb, ub = login(app_client, "mysql_pb", "乙")

    from tests_mysql.helpers import approve_pair_bind

    pair_id = approve_pair_bind(app_client, auth_header, tb, ta, ua["join_code"])
    assert_table_has_row(Pair, pair_id=pair_id, status="active")
    assert_table_has_row(ActivePairLock, user_id=ua["user_id"], pair_id=pair_id)
    assert_table_has_row(ActivePairLock, user_id=ub["user_id"], pair_id=pair_id)

    cur = app_client.get("/api/v2/pairs/current", headers=auth_header(ta))
    assert cur.status_code == 200
    assert cur.json()["data"]["pair"]["pair_id"] == pair_id
