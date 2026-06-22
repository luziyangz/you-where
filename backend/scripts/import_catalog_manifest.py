"""
将 data/catalog_manifest.json 写入 catalog_books（共读推荐书单，无内置正文）。

公版全书（西游记、红楼梦等）请使用 seed + prefetch_catalog_contents，勿与本清单重复。

用法：
    cd backend
    python scripts/import_catalog_manifest.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.db import SessionLocal  # noqa: E402
from common.models import CatalogBook  # noqa: E402
from repo import store_repo  # noqa: E402
from service.store_categories import classify_book  # noqa: E402
from service.store_service import PUBLIC_DOMAIN_CATALOG_BOOKS, utc_now  # noqa: E402

# 已有站内全文的公版书标题，避免 manifest 重复占位
_FULLTEXT_TITLES = {str(item.get("title") or "").strip() for item in PUBLIC_DOMAIN_CATALOG_BOOKS}


def main() -> None:
    manifest_path = ROOT_DIR / "data" / "catalog_manifest.json"
    if not manifest_path.exists():
        print(f"未找到清单文件: {manifest_path}")
        sys.exit(1)

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    books = data.get("books") if isinstance(data, dict) else None
    if not isinstance(books, list):
        print("catalog_manifest.json 格式应为 {\"books\": [...]}")
        sys.exit(1)

    db = SessionLocal()
    now = utc_now()
    inserted = 0
    skipped = 0
    try:
        for item in books:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("catalog_id") or "").strip()
            title = str(item.get("title") or "").strip()
            if not cid or not title:
                continue
            if title in _FULLTEXT_TITLES:
                print(f"跳过（已有公版全书）: {title}")
                skipped += 1
                continue
            if store_repo.get_catalog_book(db, cid):
                continue
            author = str(item.get("author") or "").strip()
            detail_url = str(item.get("detail_url") or "").strip()[:512]
            rating = str(item.get("douban_rating") or "").strip()[:16]
            placeholder = item.get("placeholder_pages")
            try:
                pp = int(placeholder) if placeholder is not None else 350
            except (TypeError, ValueError):
                pp = 350
            if pp < 1:
                pp = 350

            db.add(
                CatalogBook(
                    catalog_id=cid,
                    source="manifest",
                    source_book_id=cid,
                    title=title[:200],
                    author=author[:200],
                    language="zh",
                    cover_url="",
                    detail_url=detail_url,
                    text_url="",
                    owner_user_id=None,
                    douban_rating=rating or None,
                    store_category=classify_book(
                        catalog_id=cid,
                        title=title,
                        author=author,
                        language="zh",
                        source="manifest",
                        meta_category=str(item.get("category") or "").strip() or None,
                    ),
                    placeholder_pages=pp,
                    created_at=now,
                    updated_at=now,
                )
            )
            inserted += 1
        db.commit()
    finally:
        db.close()

    print(f"catalog manifest 导入完成，新增 {inserted} 条，跳过重复公版 {skipped} 条。")


if __name__ == "__main__":
    main()
