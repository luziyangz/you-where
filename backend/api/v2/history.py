from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from api.v2.common import get_current_user, get_request_id, ok
from common.db import get_db_session
from common.errors import ApiError
from common.models import Book, Entry, Pair


router = APIRouter(prefix="/profile", tags=["v2-history"])


@router.get("/history")
def profile_history(
    page: int = 1,
    page_size: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    if page < 1 or page > 200:
        raise ApiError(40082, "page 范围不合法", 400)
    if page_size < 1 or page_size > 50:
        raise ApiError(40083, "page_size 范围不合法", 400)

    user_id = current_user["user_id"]
    pair_ids = db.execute(
        select(Pair.pair_id).where(
            Pair.status.in_(["active", "unbound"]),
            or_(Pair.user_a_id == user_id, Pair.user_b_id == user_id),
        )
    ).scalars().all()
    if not pair_ids:
        return ok({"items": [], "page": page, "page_size": page_size, "has_more": False}, request_id=request_id)

    total_count = db.execute(select(func.count(Book.book_id)).where(Book.pair_id.in_(pair_ids))).scalar() or 0
    rows = db.execute(
        select(Book)
        .where(Book.pair_id.in_(pair_ids))
        .order_by(Book.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    result: List[Dict[str, Any]] = []
    for book in rows:
        my_max_page = (
            db.execute(
                select(func.max(Entry.page)).where(
                    Entry.book_id == book.book_id,
                    Entry.user_id == user_id,
                )
            ).scalar()
            or 0
        )
        result.append(
            {
                "book_id": book.book_id,
                "title": book.title,
                "author": book.author,
                "total_pages": int(book.total_pages or 0),
                "my_progress": int(my_max_page),
                "status": book.status,
                "finished_at": book.finished_at,
                "created_at": book.created_at,
            }
        )

    return ok(
        {
            "items": result,
            "page": page,
            "page_size": page_size,
            "has_more": page * page_size < int(total_count),
        },
        request_id=request_id,
    )
