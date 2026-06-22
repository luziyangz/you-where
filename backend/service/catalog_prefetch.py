"""公版书全文预取：将 Project Gutenberg 正文写入 catalog_contents，实现站内完整阅读。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from repo import store_repo
from service.store_service import (
    PUBLIC_DOMAIN_CATALOG_BOOKS,
    fetch_plain_catalog_from_url,
    seed_default_store_books,
)

logger = logging.getLogger("youzainaye.v2.catalog_prefetch")


def prefetch_public_domain_contents(
    db: Session,
    *,
    force: bool = False,
    catalog_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    从 Gutenberg 拉取公版书全文并缓存到数据库。
    参考 Gutendex / gutenfetchen：优先 cache/epub/{id}/pg{id}.txt，并剥离 PG 头尾说明。
    """
    seed_default_store_books(db)
    db.commit()

    items: List[dict] = list(PUBLIC_DOMAIN_CATALOG_BOOKS)
    if catalog_ids:
        wanted = set(catalog_ids)
        items = [item for item in items if item.get("catalog_id") in wanted]
    if limit is not None and limit > 0:
        items = items[: int(limit)]

    ok = 0
    skipped = 0
    failed: List[str] = []

    for item in items:
        cid = str(item.get("catalog_id") or "").strip()
        if not cid:
            continue
        if not force and store_repo.get_catalog_content(db, cid):
            skipped += 1
            continue
        book = store_repo.get_catalog_book(db, cid)
        if not book:
            failed.append(cid)
            logger.warning("预取跳过：书目元数据不存在 %s", cid)
            continue
        try:
            if fetch_plain_catalog_from_url(db, book):
                db.commit()
                content = store_repo.get_catalog_content(db, cid)
                pages = int(content.total_pages) if content else 0
                logger.info("预取成功 %s（约 %s 页）", cid, pages)
                ok += 1
            else:
                db.rollback()
                failed.append(cid)
                logger.warning("预取失败 %s：无法拉取正文", cid)
        except Exception as exc:
            db.rollback()
            failed.append(cid)
            logger.warning("预取异常 %s: %s", cid, exc)

    return {
        "ok": ok,
        "skipped": skipped,
        "failed": failed,
        "total": len(items),
    }
