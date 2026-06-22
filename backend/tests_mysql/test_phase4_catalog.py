# -*- coding: utf-8 -*-
"""阶段4：书城六表 catalog_*"""

from tests_mysql.helpers import _session
from common.models import (
    CatalogBook,
    CatalogContent,
    CatalogFavorite,
    CatalogReaderMark,
    CatalogReadProgress,
)
from tests_mysql.helpers import assert_table_has_row, login, seed_catalog_gutendex, wipe_business_tables


def test_catalog_read_favorite_marks_progress(app_client, auth_header):
    wipe_business_tables()
    db = _session()
    seed_catalog_gutendex(db)
    db.close()

    token, user = login(app_client, "mysql_cat_u", "书城用户")
    h = auth_header(token)
    user_id = user["user_id"]

    detail = app_client.get("/api/v2/store/books/gutendex_1", headers=h)
    assert detail.status_code == 200
    assert_table_has_row(CatalogBook, catalog_id="gutendex_1")

    read = app_client.get("/api/v2/store/books/gutendex_1/read?page=1", headers=h)
    assert read.status_code == 200
    assert "第一章" in read.json()["data"]["content"]
    assert_table_has_row(CatalogContent, catalog_id="gutendex_1")

    prog = app_client.put(
        "/api/v2/store/books/gutendex_1/reading-progress",
        json={"page": 2},
        headers=h,
    )
    assert prog.status_code == 200
    assert_table_has_row(CatalogReadProgress, user_id=user_id, catalog_id="gutendex_1")

    fav = app_client.post("/api/v2/store/books/gutendex_1/favorite", headers=h)
    assert fav.status_code == 200
    assert_table_has_row(CatalogFavorite, catalog_id="gutendex_1")

    mark = app_client.put(
        "/api/v2/store/books/gutendex_1/marks",
        json={"page": 1, "para_index": 0, "style": "marker", "note": "划重点", "text_snap": "第一章"},
        headers=h,
    )
    assert mark.status_code == 200
    assert_table_has_row(CatalogReaderMark, catalog_id="gutendex_1", page=1, para_index=0)
