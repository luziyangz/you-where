from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from common.db_safety import escape_like_pattern
from common.models import FeedComment, FeedPost


def get_post_by_id(db: Session, post_id: str) -> Optional[FeedPost]:
    return db.execute(select(FeedPost).where(FeedPost.post_id == post_id)).scalar_one_or_none()


def get_post_by_entry_id(db: Session, entry_id: str) -> Optional[FeedPost]:
    return db.execute(select(FeedPost).where(FeedPost.entry_id == entry_id)).scalar_one_or_none()


def map_posts_by_entry_ids(db: Session, entry_ids: Iterable[str]) -> Dict[str, FeedPost]:
    ids = list({item for item in entry_ids if item})
    if not ids:
        return {}
    rows = db.execute(
        select(FeedPost).where(FeedPost.entry_id.in_(ids), FeedPost.status == "published")
    ).scalars().all()
    return {row.entry_id: row for row in rows}


def list_published_posts_by_user(db: Session, user_id: str, offset: int, limit: int) -> List[FeedPost]:
    return (
        db.execute(
            select(FeedPost)
            .where(FeedPost.status == "published", FeedPost.user_id == user_id)
            .order_by(desc(FeedPost.created_at))
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )


def count_published_posts_by_user(db: Session, user_id: str) -> int:
    return int(
        db.execute(
            select(func.count(FeedPost.post_id)).where(
                FeedPost.status == "published",
                FeedPost.user_id == user_id,
            )
        ).scalar_one()
    )


def list_published_posts(db: Session, offset: int, limit: int) -> List[FeedPost]:
    return (
        db.execute(
            select(FeedPost)
            .where(FeedPost.status == "published")
            .order_by(desc(FeedPost.created_at))
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )


def count_published_posts(db: Session) -> int:
    return int(db.execute(select(func.count(FeedPost.post_id)).where(FeedPost.status == "published")).scalar_one())


def _explore_conditions(exclude_user_id: str, book_query: Optional[str]):
    conditions = [FeedPost.status == "published", FeedPost.user_id != exclude_user_id]
    q = (book_query or "").strip()
    if q:
        conditions.append(FeedPost.book_title.like(f"%{escape_like_pattern(q)}%", escape="\\"))
    return conditions


def list_explore_posts(
    db: Session,
    exclude_user_id: str,
    offset: int,
    limit: int,
    book_query: Optional[str] = None,
) -> List[FeedPost]:
    return (
        db.execute(
            select(FeedPost)
            .where(*_explore_conditions(exclude_user_id, book_query))
            .order_by(desc(FeedPost.created_at))
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )


def count_explore_posts(db: Session, exclude_user_id: str, book_query: Optional[str] = None) -> int:
    return int(
        db.execute(
            select(func.count(FeedPost.post_id)).where(*_explore_conditions(exclude_user_id, book_query))
        ).scalar_one()
    )


def list_comments_for_posts(db: Session, post_ids: Iterable[str]) -> List[FeedComment]:
    ids = list({item for item in post_ids if item})
    if not ids:
        return []
    return (
        db.execute(select(FeedComment).where(FeedComment.post_id.in_(ids)).order_by(FeedComment.created_at.asc()))
        .scalars()
        .all()
    )


def count_comments_for_post(db: Session, post_id: str) -> int:
    return int(db.execute(select(func.count(FeedComment.comment_id)).where(FeedComment.post_id == post_id)).scalar_one())
