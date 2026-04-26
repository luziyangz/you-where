from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from common.models import CatalogBook, CatalogContent


def count_catalog_books(db: Session) -> int:
    return int(db.execute(select(func.count(CatalogBook.catalog_id))).scalar() or 0)


def list_catalog_ids(db: Session) -> List[str]:
    return list(db.execute(select(CatalogBook.catalog_id)).scalars().all())


def clear_catalog(db: Session) -> None:
    db.query(CatalogContent).delete()
    db.query(CatalogBook).delete()


def add_catalog_book_with_content(
    db: Session,
    *,
    catalog_id: str,
    source: str,
    source_book_id: str,
    title: str,
    author: str,
    language: str,
    cover_url: str,
    detail_url: str,
    text_url: str,
    content_text: str,
    page_size_chars: int,
    total_pages: int,
    now: str,
) -> None:
    db.add(
        CatalogBook(
            catalog_id=catalog_id,
            source=source,
            source_book_id=source_book_id,
            title=title,
            author=author,
            language=language,
            cover_url=cover_url,
            detail_url=detail_url,
            text_url=text_url,
            created_at=now,
            updated_at=now,
        )
    )
    db.add(
        CatalogContent(
            catalog_id=catalog_id,
            content_text=content_text,
            content_len=len(content_text),
            page_size_chars=page_size_chars,
            total_pages=total_pages,
            etag=None,
            last_fetched_at=now,
        )
    )


def list_catalog_books(
    db: Session,
    query: str,
    page: int,
    page_size: int,
    catalog_ids: Optional[Sequence[str]] = None,
) -> List[CatalogBook]:
    stmt = select(CatalogBook)
    if catalog_ids is not None:
        if not catalog_ids:
            return []
        stmt = stmt.where(CatalogBook.catalog_id.in_(list(catalog_ids)))
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(CatalogBook.title.like(like), CatalogBook.author.like(like)))
    return (
        db.execute(stmt.order_by(CatalogBook.updated_at.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )


def get_catalog_book(db: Session, catalog_id: str) -> Optional[CatalogBook]:
    return db.execute(select(CatalogBook).where(CatalogBook.catalog_id == catalog_id)).scalar_one_or_none()


def get_catalog_content(db: Session, catalog_id: str) -> Optional[CatalogContent]:
    return db.execute(select(CatalogContent).where(CatalogContent.catalog_id == catalog_id)).scalar_one_or_none()


def upsert_catalog_book(db: Session, values: Dict[str, str]) -> Optional[CatalogBook]:
    catalog_id = values.get("catalog_id") or ""
    if not catalog_id:
        return None
    row = get_catalog_book(db, catalog_id)
    if row:
        row.title = values["title"]
        row.author = values["author"]
        row.language = values["language"]
        row.cover_url = values["cover_url"]
        row.detail_url = values["detail_url"]
        row.text_url = values["text_url"]
        row.updated_at = values["now"]
        return row

    row = CatalogBook(
        catalog_id=catalog_id,
        source=values["source"],
        source_book_id=values["source_book_id"],
        title=values["title"],
        author=values["author"],
        language=values["language"],
        cover_url=values["cover_url"],
        detail_url=values["detail_url"],
        text_url=values["text_url"],
        created_at=values["now"],
        updated_at=values["now"],
    )
    db.add(row)
    return row
