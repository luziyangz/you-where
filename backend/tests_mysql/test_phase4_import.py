# -*- coding: utf-8 -*-
"""阶段4 扩展：user_txt / user_link 导入与共读串联。"""

from common.models import CatalogBook, CatalogContent
from service import store_service
from tests_mysql.helpers import (
    _session,
    assert_table_has_row,
    approve_pair_bind,
    create_book_with_partner_approval,
    login,
    wipe_business_tables,
)


def test_import_txt_then_co_read(app_client, auth_header):
    wipe_business_tables()
    ta, ua = login(app_client, "mysql_txt_a", "导入甲")
    tb, _ = login(app_client, "mysql_txt_b", "伙伴乙")
    approve_pair_bind(app_client, auth_header, tb, ta, ua["join_code"])

    body = ("第一章\n\n" + "用户上传中文正文用于 MySQL 集成测试。" * 40).encode("utf-8")
    imported = app_client.post(
        "/api/v2/store/books/import-txt",
        data={"title": "MySQL上传书", "author": "测试"},
        files={"file": ("book.txt", body, "text/plain")},
        headers=auth_header(ta),
    )
    assert imported.status_code == 200, imported.text
    catalog_id = imported.json()["data"]["catalog_id"]
    assert catalog_id.startswith("utxt_")
    assert_table_has_row(CatalogBook, catalog_id=catalog_id, source="user_txt")
    assert_table_has_row(CatalogContent, catalog_id=catalog_id)

    book = create_book_with_partner_approval(
        app_client, auth_header, ta, tb, {"catalog_id": catalog_id}
    )
    book_id = book["book_id"]

    read = app_client.get(
        f"/api/v2/store/books/{catalog_id}/read?page=1",
        headers=auth_header(ta),
    )
    assert read.status_code == 200
    assert "第一章" in read.json()["data"]["content"]

    entry = app_client.post(
        f"/api/v2/books/{book_id}/entries",
        json={"page": 1, "note_content": "共读笔记", "client_request_id": "mysql-txt-e1"},
        headers=auth_header(ta),
    )
    assert entry.status_code == 200


def test_import_url_placeholder(app_client, auth_header, monkeypatch):
    wipe_business_tables()
    token, _ = login(app_client, "mysql_url_u", "链接用户")
    h = auth_header(token)

    def fail_fetch(url, limit):
        raise TimeoutError("skip remote in mysql test")

    monkeypatch.setattr(store_service, "_validate_public_import_url", lambda url: None)
    monkeypatch.setattr(store_service, "_fetch_url_payload", fail_fetch)

    imported = app_client.post(
        "/api/v2/store/books/import-url",
        json={
            "title": "外链占位书",
            "author": "作者",
            "read_url": "https://example.org/remote-book",
            "estimated_pages": 120,
        },
        headers=h,
    )
    assert imported.status_code == 200, imported.text
    data = imported.json()["data"]
    assert data["catalog_id"].startswith("ulink_")
    assert data.get("import_mode") in ("external_link", "placeholder")

    db = _session()
    row = db.query(CatalogBook).filter(CatalogBook.catalog_id == data["catalog_id"]).one()
    assert row.source == "user_link"
    assert int(row.placeholder_pages or 0) == 120
    db.close()
