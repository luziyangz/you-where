from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from common.models import (
    ActiveBookLock,
    Book,
    CatalogBook,
    CatalogContent,
    Entry,
    Pair,
    ReadMark,
    ReadingGoal,
    ReminderConfig,
    Reply,
    User,
)


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.execute(select(User).where(User.user_id == user_id)).scalar_one_or_none()


def get_user_by_join_code(db: Session, join_code: str) -> Optional[User]:
    return db.execute(select(User).where(User.join_code == join_code)).scalar_one_or_none()


def list_users_by_ids(db: Session, user_ids: Iterable[str]) -> List[User]:
    ids = list({item for item in user_ids if item})
    if not ids:
        return []
    return db.execute(select(User).where(User.user_id.in_(ids))).scalars().all()


def get_active_pair(db: Session, user_id: str) -> Optional[Pair]:
    return db.execute(
        select(Pair).where(
            Pair.status == "active",
            or_(Pair.user_a_id == user_id, Pair.user_b_id == user_id),
        )
    ).scalar_one_or_none()


def get_pair_for_update(db: Session, pair_id: str) -> Optional[Pair]:
    return db.execute(select(Pair).where(Pair.pair_id == pair_id).with_for_update()).scalar_one_or_none()


def lock_users(db: Session, user_ids: Iterable[str]) -> None:
    ids = sorted({item for item in user_ids if item})
    if not ids:
        return
    db.execute(select(User).where(User.user_id.in_(ids)).order_by(User.user_id.asc()).with_for_update()).scalars().all()


def list_pair_ids_for_user(db: Session, user_id: str) -> List[str]:
    return db.execute(
        select(Pair.pair_id).where(
            Pair.status.in_(["active", "unbound"]),
            or_(Pair.user_a_id == user_id, Pair.user_b_id == user_id),
        )
    ).scalars().all()


def count_books_for_pairs(db: Session, pair_ids: List[str], status: Optional[str] = None) -> int:
    if not pair_ids:
        return 0
    stmt = select(func.count(Book.book_id)).where(Book.pair_id.in_(pair_ids))
    if status:
        stmt = stmt.where(Book.status == status)
    return int(db.execute(stmt).scalar() or 0)


def count_entries_for_user(db: Session, user_id: str) -> int:
    return int(db.execute(select(func.count(Entry.entry_id)).where(Entry.user_id == user_id)).scalar() or 0)


def list_user_book_max_pages(db: Session, user_id: str):
    return db.execute(
        select(Entry.book_id, func.max(Entry.page).label("max_page")).where(Entry.user_id == user_id).group_by(Entry.book_id)
    ).all()


def get_current_book(db: Session, pair_id: str) -> Optional[Book]:
    return (
        db.execute(select(Book).where(and_(Book.pair_id == pair_id, Book.status == "reading")).order_by(desc(Book.created_at)))
        .scalars()
        .first()
    )


def get_book_by_id(db: Session, book_id: str) -> Optional[Book]:
    return db.execute(select(Book).where(Book.book_id == book_id)).scalar_one_or_none()


def list_books_for_pair(db: Session, pair_id: str, status: Optional[str] = None) -> List[Book]:
    stmt = select(Book).where(Book.pair_id == pair_id)
    if status:
        stmt = stmt.where(Book.status == status)
    return db.execute(stmt.order_by(desc(Book.created_at))).scalars().all()


def list_books_for_pairs(db: Session, pair_ids: List[str], offset: int, limit: int) -> List[Book]:
    if not pair_ids:
        return []
    return (
        db.execute(select(Book).where(Book.pair_id.in_(pair_ids)).order_by(desc(Book.created_at)).offset(offset).limit(limit))
        .scalars()
        .all()
    )


def get_catalog_book_with_content(db: Session, catalog_id: str):
    cbook = db.execute(select(CatalogBook).where(CatalogBook.catalog_id == catalog_id)).scalar_one_or_none()
    ccontent = db.execute(select(CatalogContent).where(CatalogContent.catalog_id == catalog_id)).scalar_one_or_none()
    return cbook, ccontent


def get_active_book_lock(db: Session, pair_id: str) -> Optional[ActiveBookLock]:
    return db.execute(select(ActiveBookLock).where(ActiveBookLock.pair_id == pair_id)).scalar_one_or_none()


def get_user_max_page(db: Session, book_id: str, user_id: str) -> int:
    value = db.execute(select(func.max(Entry.page)).where(Entry.book_id == book_id, Entry.user_id == user_id)).scalar()
    return int(value or 0)


def get_duplicate_entry(db: Session, book_id: str, user_id: str, client_request_id: Optional[str]) -> Optional[Entry]:
    if not client_request_id:
        return None
    return db.execute(
        select(Entry).where(
            Entry.book_id == book_id,
            Entry.user_id == user_id,
            Entry.client_request_id == client_request_id,
        )
    ).scalar_one_or_none()


def count_entries_for_book(db: Session, book_id: str) -> int:
    return int(db.execute(select(func.count(Entry.entry_id)).where(Entry.book_id == book_id)).scalar() or 0)


def list_entries_for_book(db: Session, book_id: str, offset: int, limit: int) -> List[Entry]:
    return (
        db.execute(select(Entry).where(Entry.book_id == book_id).order_by(desc(Entry.created_at)).offset(offset).limit(limit))
        .scalars()
        .all()
    )


def get_read_mark(db: Session, user_id: str, book_id: str) -> Optional[ReadMark]:
    return db.execute(select(ReadMark).where(ReadMark.user_id == user_id, ReadMark.book_id == book_id)).scalar_one_or_none()


def get_entry_by_id(db: Session, entry_id: str) -> Optional[Entry]:
    return db.execute(select(Entry).where(Entry.entry_id == entry_id)).scalar_one_or_none()


def get_entry_for_book(db: Session, entry_id: str, book_id: str) -> Optional[Entry]:
    return db.execute(select(Entry).where(Entry.entry_id == entry_id, Entry.book_id == book_id)).scalar_one_or_none()


def count_unread_entries(db: Session, book_id: str, user_id: str, last_read_at: Optional[str]) -> int:
    stmt = select(func.count(Entry.entry_id)).where(Entry.book_id == book_id, Entry.user_id != user_id)
    if last_read_at:
        stmt = stmt.where(Entry.created_at > last_read_at)
    return int(db.execute(stmt).scalar() or 0)


def list_replies_for_entries(db: Session, entry_ids: List[str]) -> List[Reply]:
    if not entry_ids:
        return []
    return db.execute(select(Reply).where(Reply.entry_id.in_(entry_ids)).order_by(Reply.created_at.asc())).scalars().all()


def get_reading_goal(db: Session, user_id: str) -> Optional[ReadingGoal]:
    return db.execute(select(ReadingGoal).where(ReadingGoal.user_id == user_id)).scalar_one_or_none()


def list_finished_books_since(db: Session, pair_ids: List[str], start_iso: str) -> List[str]:
    if not pair_ids:
        return []
    return db.execute(
        select(Book.book_id).where(
            Book.pair_id.in_(pair_ids),
            Book.status == "finished",
            Book.finished_at >= start_iso,
        )
    ).scalars().all()


def list_entry_dates_since(db: Session, user_id: str, start_iso: str) -> List[str]:
    return db.execute(select(Entry.created_at).where(Entry.user_id == user_id, Entry.created_at >= start_iso)).scalars().all()


def get_reminder_config(db: Session, user_id: str) -> Optional[ReminderConfig]:
    return db.execute(select(ReminderConfig).where(ReminderConfig.user_id == user_id)).scalar_one_or_none()
