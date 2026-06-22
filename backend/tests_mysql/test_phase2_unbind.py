# -*- coding: utf-8 -*-
"""阶段2 扩展：解绑时将在读书标为 switched。"""

from common.models import ActivePairLock, Book, Pair
from common.reading_enums import BOOK_STATUS_SWITCHED
from tests_mysql.helpers import (
    _session,
    assert_table_has_row,
    approve_unbind,
    bind_pair,
    create_book_with_partner_approval,
    seed_catalog_gutendex,
    wipe_business_tables,
)


def test_unbind_switches_active_book(app_client, auth_header):
    wipe_business_tables()
    db = _session()
    seed_catalog_gutendex(db)
    db.close()

    ta, tb, _, _, pair_id = bind_pair(app_client, auth_header, "mysql_ub_a", "mysql_ub_b")
    book = create_book_with_partner_approval(
        app_client, auth_header, ta, tb, {"catalog_id": "gutendex_1"}
    )
    book_id = book["book_id"]

    approve_unbind(app_client, auth_header, ta, tb)

    db = _session()
    book = db.query(Book).filter(Book.book_id == book_id).one()
    pair = db.query(Pair).filter(Pair.pair_id == pair_id).one()
    lock = db.query(ActivePairLock).filter(ActivePairLock.pair_id == pair_id).first()
    db.close()

    assert book.status == BOOK_STATUS_SWITCHED
    assert pair.status == "unbound"
    assert lock is None

    history = app_client.get("/api/v2/users/me/reading-history?page=1&page_size=10", headers=auth_header(ta))
    assert history.status_code == 200
    item = next(x for x in history.json()["data"]["items"] if x["book_id"] == book_id)
    assert item["display_status"] == "switched"
    assert item["display_label"] == "已切换"
