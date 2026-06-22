from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from common.models import (
    ActiveBookLock,
    Book,
    BookReadProgress,
    BookSwitchRequest,
    CatalogBook,
    CatalogContent,
    Entry,
    Pair,
    PairBlock,
    PairRequest,
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


def get_pair_by_id(db: Session, pair_id: str) -> Optional[Pair]:
    return db.execute(select(Pair).where(Pair.pair_id == pair_id)).scalar_one_or_none()


def get_pair_for_update(db: Session, pair_id: str) -> Optional[Pair]:
    return db.execute(select(Pair).where(Pair.pair_id == pair_id).with_for_update()).scalar_one_or_none()


def pair_block_key(user_a_id: str, user_b_id: str) -> tuple[str, str]:
    return tuple(sorted([user_a_id, user_b_id]))


def get_pair_block(db: Session, user_a_id: str, user_b_id: str) -> Optional[PairBlock]:
    low, high = pair_block_key(user_a_id, user_b_id)
    return db.execute(
        select(PairBlock).where(PairBlock.user_low_id == low, PairBlock.user_high_id == high)
    ).scalar_one_or_none()


def add_pair_block(db: Session, user_a_id: str, user_b_id: str, now: str, reason: str = "unbound") -> None:
    low, high = pair_block_key(user_a_id, user_b_id)
    if get_pair_block(db, low, high):
        return
    db.add(PairBlock(user_low_id=low, user_high_id=high, reason=reason, created_at=now))


def add_pair_request(db: Session, row: PairRequest) -> None:
    db.add(row)


def get_pair_request(db: Session, request_id: str) -> Optional[PairRequest]:
    return db.execute(select(PairRequest).where(PairRequest.request_id == request_id)).scalar_one_or_none()


def get_pending_pair_request_between(
    db: Session,
    request_type: str,
    user_a_id: str,
    user_b_id: str,
) -> Optional[PairRequest]:
    return (
        db.execute(
            select(PairRequest)
            .where(
                PairRequest.request_type == request_type,
                PairRequest.status == "pending",
                or_(
                    and_(PairRequest.requester_user_id == user_a_id, PairRequest.target_user_id == user_b_id),
                    and_(PairRequest.requester_user_id == user_b_id, PairRequest.target_user_id == user_a_id),
                ),
            )
            .order_by(desc(PairRequest.created_at))
        )
        .scalars()
        .first()
    )


def get_pending_outgoing_pair_request(
    db: Session,
    request_type: str,
    requester_user_id: str,
) -> Optional[PairRequest]:
    return (
        db.execute(
            select(PairRequest)
            .where(
                PairRequest.request_type == request_type,
                PairRequest.status == "pending",
                PairRequest.requester_user_id == requester_user_id,
            )
            .order_by(desc(PairRequest.created_at))
        )
        .scalars()
        .first()
    )


def get_pending_unbind_request_for_pair(db: Session, pair_id: str) -> Optional[PairRequest]:
    return (
        db.execute(
            select(PairRequest)
            .where(
                PairRequest.request_type == "unbind",
                PairRequest.pair_id == pair_id,
                PairRequest.status == "pending",
            )
            .order_by(desc(PairRequest.created_at))
        )
        .scalars()
        .first()
    )


def list_pending_pair_requests_for_user(db: Session, user_id: str) -> List[PairRequest]:
    return list(
        db.execute(
            select(PairRequest)
            .where(
                PairRequest.status == "pending",
                or_(PairRequest.requester_user_id == user_id, PairRequest.target_user_id == user_id),
            )
            .order_by(desc(PairRequest.created_at))
        )
        .scalars()
        .all()
    )


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


def get_pending_book_switch_request(db: Session, pair_id: str) -> Optional[BookSwitchRequest]:
    return (
        db.execute(
            select(BookSwitchRequest)
            .where(and_(BookSwitchRequest.pair_id == pair_id, BookSwitchRequest.status == "pending"))
            .order_by(desc(BookSwitchRequest.created_at))
        )
        .scalars()
        .first()
    )


def get_book_switch_request(db: Session, request_id: str) -> Optional[BookSwitchRequest]:
    return db.execute(select(BookSwitchRequest).where(BookSwitchRequest.request_id == request_id)).scalar_one_or_none()


def add_book_switch_request(db: Session, row: BookSwitchRequest) -> None:
    db.add(row)


def get_pair_book_by_catalog_id(db: Session, pair_id: str, catalog_id: str) -> Optional[Book]:
    """共读关系中是否已收录该书城书目（含在读与已读完）。"""
    if not pair_id or not catalog_id:
        return None
    return (
        db.execute(
            select(Book)
            .where(and_(Book.pair_id == pair_id, Book.catalog_id == catalog_id))
            .order_by(desc(Book.created_at))
        )
        .scalars()
        .first()
    )


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


def get_catalog_book(db: Session, catalog_id: str) -> Optional[CatalogBook]:
    return db.execute(select(CatalogBook).where(CatalogBook.catalog_id == catalog_id)).scalar_one_or_none()


def get_catalog_content_row(db: Session, catalog_id: str) -> Optional[CatalogContent]:
    return db.execute(select(CatalogContent).where(CatalogContent.catalog_id == catalog_id)).scalar_one_or_none()


def get_catalog_book_with_content(db: Session, catalog_id: str):
    cbook = get_catalog_book(db, catalog_id)
    ccontent = get_catalog_content_row(db, catalog_id)
    return cbook, ccontent


def get_active_book_lock(db: Session, pair_id: str) -> Optional[ActiveBookLock]:
    return db.execute(select(ActiveBookLock).where(ActiveBookLock.pair_id == pair_id)).scalar_one_or_none()


def get_user_max_page(db: Session, book_id: str, user_id: str) -> int:
    value = db.execute(select(func.max(Entry.page)).where(Entry.book_id == book_id, Entry.user_id == user_id)).scalar()
    return int(value or 0)


def get_book_read_progress(db: Session, user_id: str, book_id: str) -> Optional[int]:
    row = db.execute(
        select(BookReadProgress).where(
            BookReadProgress.user_id == user_id,
            BookReadProgress.book_id == book_id,
        )
    ).scalar_one_or_none()
    return int(row.last_page) if row else None


def upsert_book_read_progress(db: Session, user_id: str, book_id: str, last_page: int, now: str) -> None:
    row = db.execute(
        select(BookReadProgress).where(
            BookReadProgress.user_id == user_id,
            BookReadProgress.book_id == book_id,
        )
    ).scalar_one_or_none()
    if row:
        row.last_page = last_page
        row.updated_at = now
        return
    db.add(
        BookReadProgress(
            user_id=user_id,
            book_id=book_id,
            last_page=last_page,
            updated_at=now,
        )
    )


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


def get_reply_by_id(db: Session, reply_id: str) -> Optional[Reply]:
    return db.execute(select(Reply).where(Reply.reply_id == reply_id)).scalar_one_or_none()


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
    """周期内已结束的书目 book_id（含 finished / switched）；真读完由 service 层再过滤。"""
    if not pair_ids:
        return []
    return list(
        db.execute(
            select(Book.book_id).where(
                Book.pair_id.in_(pair_ids),
                Book.finished_at.isnot(None),
                Book.finished_at >= start_iso,
                Book.status.in_(("finished", "switched")),
            )
        ).scalars().all()
    )


def list_books_for_pairs_since(db: Session, pair_ids: List[str], start_iso: str) -> List[Book]:
    if not pair_ids:
        return []
    return (
        db.execute(
            select(Book).where(
                Book.pair_id.in_(pair_ids),
                Book.finished_at.isnot(None),
                Book.finished_at >= start_iso,
            )
        )
        .scalars()
        .all()
    )


def list_entry_dates_since(db: Session, user_id: str, start_iso: str) -> List[str]:
    return db.execute(select(Entry.created_at).where(Entry.user_id == user_id, Entry.created_at >= start_iso)).scalars().all()


def get_reminder_config(db: Session, user_id: str) -> Optional[ReminderConfig]:
    return db.execute(select(ReminderConfig).where(ReminderConfig.user_id == user_id)).scalar_one_or_none()
