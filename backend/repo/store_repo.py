from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set

from sqlalchemy import Float, cast, delete, desc, func, or_, select
from sqlalchemy.orm import Session

from common.db_safety import assert_destructive_db_allowed, escape_like_pattern
from common.models import CatalogBook, CatalogContent, CatalogFavorite, CatalogReaderMark, CatalogReadProgress


def count_catalog_books(db: Session) -> int:
    return int(db.execute(select(func.count(CatalogBook.catalog_id))).scalar() or 0)


def list_catalog_ids(db: Session) -> List[str]:
    return list(db.execute(select(CatalogBook.catalog_id)).scalars().all())


def clear_catalog(db: Session) -> None:
    assert_destructive_db_allowed("clear_catalog（清空书城 catalog_*）")
    db.query(CatalogContent).delete()
    db.query(CatalogBook).delete()


def _catalog_list_stmt(
    db: Session,
    query: str,
    catalog_ids: Optional[Sequence[str]] = None,
    viewer_user_id: Optional[str] = None,
    excluded_sources: Optional[Sequence[str]] = None,
    store_category: Optional[str] = None,
):
    stmt = select(CatalogBook)
    if viewer_user_id:
        stmt = stmt.where(or_(CatalogBook.owner_user_id.is_(None), CatalogBook.owner_user_id == viewer_user_id))
    else:
        stmt = stmt.where(CatalogBook.owner_user_id.is_(None))
    if catalog_ids is not None:
        if not catalog_ids:
            return None
        stmt = stmt.where(CatalogBook.catalog_id.in_(list(catalog_ids)))
    if store_category:
        stmt = stmt.where(CatalogBook.store_category == store_category)
    if excluded_sources:
        stmt = stmt.where(CatalogBook.source.notin_(list(excluded_sources)))
    if query:
        like = f"%{escape_like_pattern(query)}%"
        stmt = stmt.where(
            or_(
                CatalogBook.title.like(like, escape="\\"),
                CatalogBook.author.like(like, escape="\\"),
            )
        )
    return stmt


def count_catalog_books_filtered(
    db: Session,
    query: str,
    catalog_ids: Optional[Sequence[str]] = None,
    viewer_user_id: Optional[str] = None,
    excluded_sources: Optional[Sequence[str]] = None,
    store_category: Optional[str] = None,
) -> int:
    stmt = _catalog_list_stmt(
        db,
        query,
        catalog_ids=catalog_ids,
        viewer_user_id=viewer_user_id,
        excluded_sources=excluded_sources,
        store_category=store_category,
    )
    if stmt is None:
        return 0
    return int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0)


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
    owner_user_id: Optional[str] = None,
    douban_rating: Optional[str] = None,
    placeholder_pages: Optional[int] = None,
    store_category: Optional[str] = None,
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
            owner_user_id=owner_user_id,
            douban_rating=douban_rating,
            placeholder_pages=placeholder_pages,
            store_category=store_category,
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
    viewer_user_id: Optional[str] = None,
    excluded_sources: Optional[Sequence[str]] = None,
    store_category: Optional[str] = None,
) -> List[CatalogBook]:
    stmt = _catalog_list_stmt(
        db,
        query,
        catalog_ids=catalog_ids,
        viewer_user_id=viewer_user_id,
        excluded_sources=excluded_sources,
        store_category=store_category,
    )
    if stmt is None:
        return []
    rating_sort = func.coalesce(cast(CatalogBook.douban_rating, Float), 0.0)
    stmt = stmt.order_by(desc(rating_sort), CatalogBook.catalog_id.asc())
    return (
        db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )


def catalog_ids_having_content(db: Session, catalog_ids: Sequence[str]) -> Set[str]:
    if not catalog_ids:
        return set()
    rows = db.execute(select(CatalogContent.catalog_id).where(CatalogContent.catalog_id.in_(list(catalog_ids)))).scalars().all()
    return set(rows)


def get_catalog_read_progress(db: Session, user_id: str, catalog_id: str) -> Optional[int]:
    row = db.execute(
        select(CatalogReadProgress).where(
            CatalogReadProgress.user_id == user_id,
            CatalogReadProgress.catalog_id == catalog_id,
        )
    ).scalar_one_or_none()
    return int(row.last_page) if row else None


def upsert_catalog_read_progress(db: Session, user_id: str, catalog_id: str, last_page: int, now: str) -> None:
    row = db.execute(
        select(CatalogReadProgress).where(
            CatalogReadProgress.user_id == user_id,
            CatalogReadProgress.catalog_id == catalog_id,
        )
    ).scalar_one_or_none()
    if row:
        row.last_page = last_page
        row.updated_at = now
        return
    db.add(
        CatalogReadProgress(
            user_id=user_id,
            catalog_id=catalog_id,
            last_page=last_page,
            updated_at=now,
        )
    )


def list_catalog_read_progress_page(db: Session, user_id: str, page: int, page_size: int) -> List[CatalogReadProgress]:
    if page < 1:
        page = 1
    offset = (page - 1) * page_size
    stmt = (
        select(CatalogReadProgress)
        .where(CatalogReadProgress.user_id == user_id)
        .order_by(CatalogReadProgress.updated_at.desc())
        .offset(offset)
        .limit(page_size + 1)
    )
    return list(db.execute(stmt).scalars().all())


def is_catalog_favorited(db: Session, user_id: str, catalog_id: str) -> bool:
    row = db.execute(
        select(CatalogFavorite).where(
            CatalogFavorite.user_id == user_id,
            CatalogFavorite.catalog_id == catalog_id,
        )
    ).scalar_one_or_none()
    return row is not None


def add_catalog_favorite(db: Session, user_id: str, catalog_id: str, now: str) -> None:
    if is_catalog_favorited(db, user_id, catalog_id):
        return
    db.add(CatalogFavorite(user_id=user_id, catalog_id=catalog_id, created_at=now))


def remove_catalog_favorite(db: Session, user_id: str, catalog_id: str) -> None:
    db.execute(
        delete(CatalogFavorite).where(
            CatalogFavorite.user_id == user_id,
            CatalogFavorite.catalog_id == catalog_id,
        )
    )


def list_catalog_favorites_page(db: Session, user_id: str, page: int, page_size: int) -> List[CatalogFavorite]:
    if page < 1:
        page = 1
    offset = (page - 1) * page_size
    stmt = (
        select(CatalogFavorite)
        .where(CatalogFavorite.user_id == user_id)
        .order_by(CatalogFavorite.created_at.desc())
        .offset(offset)
        .limit(page_size + 1)
    )
    return list(db.execute(stmt).scalars().all())


def upsert_catalog_content(
    db: Session,
    *,
    catalog_id: str,
    content_text: str,
    page_size_chars: int,
    total_pages: int,
    now: str,
) -> None:
    row = get_catalog_content(db, catalog_id)
    if row:
        row.content_text = content_text
        row.content_len = len(content_text)
        row.page_size_chars = page_size_chars
        row.total_pages = total_pages
        row.last_fetched_at = now
        return
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


def get_catalog_book(db: Session, catalog_id: str) -> Optional[CatalogBook]:
    return db.execute(select(CatalogBook).where(CatalogBook.catalog_id == catalog_id)).scalar_one_or_none()


def get_catalog_content(db: Session, catalog_id: str) -> Optional[CatalogContent]:
    return db.execute(select(CatalogContent).where(CatalogContent.catalog_id == catalog_id)).scalar_one_or_none()


def delete_catalog_content(db: Session, catalog_id: str) -> None:
    db.execute(delete(CatalogContent).where(CatalogContent.catalog_id == catalog_id))


def upsert_catalog_book(db: Session, values: Dict[str, str]) -> Optional[CatalogBook]:
    catalog_id = values.get("catalog_id") or ""
    if not catalog_id:
        return None
    row = get_catalog_book(db, catalog_id)
    if row:
        changed = (
            row.title != values["title"]
            or row.author != values["author"]
            or row.language != values["language"]
            or row.cover_url != values["cover_url"]
            or row.detail_url != values["detail_url"]
            or row.text_url != values["text_url"]
        )
        row.title = values["title"]
        row.author = values["author"]
        row.language = values["language"]
        row.cover_url = values["cover_url"]
        row.detail_url = values["detail_url"]
        row.text_url = values["text_url"]
        if "douban_rating" in values and values.get("douban_rating"):
            if row.douban_rating != values.get("douban_rating"):
                row.douban_rating = values.get("douban_rating")
                changed = True
        if values.get("store_category"):
            if row.store_category != values.get("store_category"):
                row.store_category = values.get("store_category")
                changed = True
        if changed:
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
        douban_rating=values.get("douban_rating"),
        store_category=values.get("store_category"),
        created_at=values["now"],
        updated_at=values["now"],
    )
    db.add(row)
    return row


def list_catalog_reader_marks(db: Session, user_id: str, catalog_id: str) -> List[CatalogReaderMark]:
    stmt = (
        select(CatalogReaderMark)
        .where(
            CatalogReaderMark.user_id == user_id,
            CatalogReaderMark.catalog_id == catalog_id,
        )
        .order_by(CatalogReaderMark.page.asc(), CatalogReaderMark.para_index.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_catalog_reader_mark(
    db: Session, user_id: str, catalog_id: str, page: int, para_index: int
) -> Optional[CatalogReaderMark]:
    return db.execute(
        select(CatalogReaderMark).where(
            CatalogReaderMark.user_id == user_id,
            CatalogReaderMark.catalog_id == catalog_id,
            CatalogReaderMark.page == page,
            CatalogReaderMark.para_index == para_index,
        )
    ).scalar_one_or_none()


def upsert_catalog_reader_mark(
    db: Session,
    user_id: str,
    catalog_id: str,
    page: int,
    para_index: int,
    style: str,
    note: str,
    text_snap: str,
    now: str,
) -> None:
    row = db.execute(
        select(CatalogReaderMark).where(
            CatalogReaderMark.user_id == user_id,
            CatalogReaderMark.catalog_id == catalog_id,
            CatalogReaderMark.page == page,
            CatalogReaderMark.para_index == para_index,
        )
    ).scalar_one_or_none()
    if row:
        row.style = style
        row.note = note
        row.text_snap = text_snap
        row.updated_at = now
        return
    db.add(
        CatalogReaderMark(
            user_id=user_id,
            catalog_id=catalog_id,
            page=page,
            para_index=para_index,
            style=style,
            note=note,
            text_snap=text_snap,
            created_at=now,
            updated_at=now,
        )
    )


def delete_catalog_reader_mark(db: Session, user_id: str, catalog_id: str, page: int, para_index: int) -> None:
    db.execute(
        delete(CatalogReaderMark).where(
            CatalogReaderMark.user_id == user_id,
            CatalogReaderMark.catalog_id == catalog_id,
            CatalogReaderMark.page == page,
            CatalogReaderMark.para_index == para_index,
        )
    )


def count_catalog_reader_marks(db: Session, user_id: str, catalog_id: str) -> int:
    stmt = select(func.count()).select_from(CatalogReaderMark).where(
        CatalogReaderMark.user_id == user_id,
        CatalogReaderMark.catalog_id == catalog_id,
    )
    return int(db.execute(stmt).scalar() or 0)
