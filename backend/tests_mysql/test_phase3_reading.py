# -*- coding: utf-8 -*-
"""阶段3：共读六表 books / locks / switch / entries / replies / read_marks"""

from tests_mysql.helpers import _session
from common.models import (
    ActiveBookLock,
    Book,
    BookSwitchRequest,
    Entry,
    ReadMark,
    Reply,
)
from common.reading_enums import BOOK_STATUS_FINISHED, BOOK_STATUS_SWITCHED
from tests_mysql.helpers import (
    assert_table_has_row,
    bind_pair,
    create_book_with_partner_approval,
    seed_catalog_gutendex,
    wipe_business_tables,
)


def test_books_entries_replies_read_marks(app_client, auth_header):
    wipe_business_tables()
    db = _session()
    seed_catalog_gutendex(db)
    db.close()

    ta, tb, ua, ub, pair_id = bind_pair(app_client, auth_header, "mysql_r3_a", "mysql_r3_b")
    created = create_book_with_partner_approval(
        app_client, auth_header, ta, tb, {"catalog_id": "gutendex_1"}
    )
    book_id = created["book_id"]
    assert_table_has_row(Book, book_id=book_id, pair_id=pair_id, status="reading")
    assert_table_has_row(ActiveBookLock, pair_id=pair_id, book_id=book_id)

    e1 = app_client.post(
        f"/api/v2/books/{book_id}/entries",
        json={
            "page": 1,
            "note_content": "这段写得太好了",
            "quote_text": "甲甲甲甲甲",
            "client_request_id": "mysql-e1",
        },
        headers=auth_header(ta),
    )
    assert e1.status_code == 200
    entry_id = e1.json()["data"].get("entry_id") or _entry_id_from_list(app_client, auth_header(tb), book_id)
    assert_table_has_row(Entry, book_id=book_id)

    # 伙伴需先读到同页才能回复（解锁规则）
    unlock = app_client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 1, "note_content": "", "client_request_id": "mysql-unlock-b"},
        headers=auth_header(tb),
    )
    assert unlock.status_code == 200

    listed = app_client.get(f"/api/v2/books/{book_id}/entries?page=1&page_size=10", headers=auth_header(tb))
    assert listed.status_code == 200
    first = listed.json()["data"]["entries"][0]
    assert first.get("quote_text") == "甲甲甲甲甲"

    reply = app_client.post(
        f"/api/v2/entries/{entry_id}/replies",
        json={"content": "伙伴回复"},
        headers=auth_header(tb),
    )
    assert reply.status_code == 200
    assert_table_has_row(Reply, entry_id=entry_id)

    mark = app_client.put(
        f"/api/v2/books/{book_id}/read-mark",
        json={"last_entry_id": entry_id},
        headers=auth_header(tb),
    )
    assert mark.status_code == 200
    assert_table_has_row(ReadMark, user_id=ub["user_id"], book_id=book_id)


def _entry_id_from_list(client, auth_header, book_id):
    listed = client.get(f"/api/v2/books/{book_id}/entries?page=1&page_size=10", headers=auth_header)
    assert listed.status_code == 200
    rows = listed.json()["data"]["entries"]
    assert rows
    return rows[0]["entry_id"]


def test_book_switch_and_truly_finished(app_client, auth_header):
    wipe_business_tables()
    db = _session()
    seed_catalog_gutendex(db)
    db.close()

    ta, tb, ua, ub, _ = bind_pair(app_client, auth_header, "mysql_r3_sw_a", "mysql_r3_sw_b")
    first = create_book_with_partner_approval(
        app_client, auth_header, ta, tb, {"catalog_id": "gutendex_1"}
    )
    book1 = first["book_id"]

    req = app_client.post(
        "/api/v2/pairs/current/book-switch-requests",
        json={"title": "换书B", "author": "作者", "total_pages": 50},
        headers=auth_header(ta),
    )
    assert req.status_code == 200
    req_id = req.json()["data"]["switch_request"]["request_id"]
    assert_table_has_row(BookSwitchRequest, request_id=req_id)

    approved = app_client.post(
        f"/api/v2/pairs/current/book-switch-requests/{req_id}/respond",
        json={"action": "approve"},
        headers=auth_header(tb),
    )
    assert approved.status_code == 200

    db = _session()
    old = db.query(Book).filter(Book.book_id == book1).one()
    assert old.status == BOOK_STATUS_SWITCHED
    db.close()

    book2 = approved.json()["data"]["book"]["book_id"]
    for user, token in ((ua, ta), (ub, tb)):
        for page in (49, 50):
            resp = app_client.post(
                f"/api/v2/books/{book2}/entries",
                json={
                    "page": page,
                    "note_content": "",
                    "client_request_id": f"fin-{user['user_id']}-{page}",
                },
                headers=auth_header(token),
            )
            assert resp.status_code == 200, resp.text
    db = _session()
    done = db.query(Book).filter(Book.book_id == book2).one()
    assert done.status == BOOK_STATUS_FINISHED
    db.close()

    stats = app_client.get("/api/v2/users/me/stats", headers=auth_header(ta))
    assert stats.json()["data"]["total_books"] == 1
