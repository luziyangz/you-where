# -*- coding: utf-8 -*-
"""阶段6：分享摘录 feed_posts（非社交，仅我的分享 + 单条查看）"""

from common.models import FeedPost
from tests_mysql.helpers import assert_table_has_row, bind_pair, seed_catalog_gutendex, wipe_business_tables, _session


def test_share_publish_mine_and_view(app_client, auth_header):
    wipe_business_tables()
    db = _session()
    seed_catalog_gutendex(db)
    db.close()

    ta, tb, ua, ub, _ = bind_pair(app_client, auth_header, "mysql_share_a", "mysql_share_b")
    created = app_client.post(
        "/api/v2/books",
        json={"catalog_id": "gutendex_1"},
        headers=auth_header(ta),
    )
    assert created.status_code == 200
    book_id = created.json()["data"]["book_id"]

    entry = app_client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 1, "note_content": "MySQL 分享摘录", "client_request_id": "mysql-share-e1"},
        headers=auth_header(ta),
    )
    assert entry.status_code == 200
    listed = app_client.get(f"/api/v2/books/{book_id}/entries?page=1&page_size=10", headers=auth_header(ta))
    entry_id = listed.json()["data"]["entries"][0]["entry_id"]

    published = app_client.post(
        f"/api/v2/entries/{entry_id}/publish-to-feed",
        json={"excerpt": "MySQL 分享摘录", "confirm": True},
        headers=auth_header(ta),
    )
    assert published.status_code == 200
    post_id = published.json()["data"]["post_id"]
    assert_table_has_row(FeedPost, post_id=post_id, user_id=ua["user_id"], status="published")

    mine = app_client.get("/api/v2/feed/posts/mine", headers=auth_header(ta))
    assert mine.status_code == 200
    assert len(mine.json()["data"]["posts"]) == 1

    other_mine = app_client.get("/api/v2/feed/posts/mine", headers=auth_header(tb))
    assert other_mine.json()["data"]["posts"] == []

    detail = app_client.get(f"/api/v2/feed/posts/{post_id}", headers=auth_header(tb))
    assert detail.status_code == 200

    deleted = app_client.delete(f"/api/v2/feed/posts/{post_id}", headers=auth_header(ta))
    assert deleted.status_code == 200


def test_explore_excludes_self(app_client, auth_header):
    wipe_business_tables()
    db = _session()
    seed_catalog_gutendex(db)
    db.close()

    ta, tb, ua, ub, _ = bind_pair(app_client, auth_header, "mysql_explore_a", "mysql_explore_b")
    created = app_client.post(
        "/api/v2/books",
        json={"catalog_id": "gutendex_1"},
        headers=auth_header(ta),
    )
    assert created.status_code == 200
    book_id = created.json()["data"]["book_id"]

    entry = app_client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 1, "note_content": "探索书摘", "client_request_id": "mysql-explore-e1"},
        headers=auth_header(ta),
    )
    assert entry.status_code == 200
    listed = app_client.get(f"/api/v2/books/{book_id}/entries?page=1&page_size=10", headers=auth_header(ta))
    entry_id = listed.json()["data"]["entries"][0]["entry_id"]

    published = app_client.post(
        f"/api/v2/entries/{entry_id}/publish-to-feed",
        json={"excerpt": "探索书摘", "confirm": True},
        headers=auth_header(ta),
    )
    assert published.status_code == 200

    self_explore = app_client.get("/api/v2/feed/posts/explore", headers=auth_header(ta))
    assert self_explore.status_code == 200
    assert self_explore.json()["data"]["posts"] == []

    explore = app_client.get("/api/v2/feed/posts/explore", headers=auth_header(tb))
    assert explore.status_code == 200
    posts = explore.json()["data"]["posts"]
    assert len(posts) == 1
    assert posts[0]["user_id"] == ua["user_id"]
