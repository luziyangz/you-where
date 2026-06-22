"""
将 catalog_books 的 store_category 统一迁移为微信读书风格分类。

用法：
    cd backend
    python scripts/reclassify_store_categories.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.db import SessionLocal  # noqa: E402
from common.models import CatalogBook  # noqa: E402
from service.store_categories import classify_book, remap_legacy_store_category  # noqa: E402
from service.store_service import DEFAULT_CATEGORY_FALLBACKS, _default_book_meta  # noqa: E402


def main() -> None:
    db = SessionLocal()
    updated = 0
    try:
        rows = db.query(CatalogBook).all()
        for row in rows:
            meta = _default_book_meta(row.catalog_id)
            new_cat = classify_book(
                catalog_id=row.catalog_id,
                title=row.title or "",
                author=row.author or "",
                language=row.language or "",
                source=row.source,
                meta_category=str(meta.get("category") or DEFAULT_CATEGORY_FALLBACKS.get(row.catalog_id) or ""),
            )
            old = remap_legacy_store_category(row.store_category) or row.store_category
            if old != new_cat:
                row.store_category = new_cat
                updated += 1
        db.commit()
    finally:
        db.close()
    print(f"书城分类迁移完成，更新 {updated} 条。")


if __name__ == "__main__":
    main()
