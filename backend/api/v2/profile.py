from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from api.v2.common import (
    get_active_pair,
    get_current_user,
    get_partner_id,
    get_request_id,
    ok,
    calc_days_since,
)
from common.db import get_db_session
from common.models import Book, Entry, Pair, User


router = APIRouter(prefix="/profile", tags=["v2-profile"])


@router.get("/me")
def profile_me(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    pair = get_active_pair(db, current_user["user_id"])
    partner = None
    if pair:
        partner_id = get_partner_id(pair, current_user["user_id"])
        partner_row = db.execute(select(User).where(User.user_id == partner_id)).scalar_one_or_none()
        if partner_row:
            partner = {
                "user_id": partner_row.user_id,
                "nickname": partner_row.nickname,
                "avatar": partner_row.avatar,
                "join_code": partner_row.join_code,
            }
    return ok({"user": current_user, "partner": partner}, request_id=request_id)


@router.get("/stats")
def profile_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    user_id = current_user["user_id"]
    pair_ids = db.execute(
        select(Pair.pair_id).where(
            Pair.status == "active",
            or_(Pair.user_a_id == user_id, Pair.user_b_id == user_id),
        )
    ).scalars().all()

    total_books = 0
    total_pages = 0
    total_entries = db.execute(select(func.count(Entry.entry_id)).where(Entry.user_id == user_id)).scalar() or 0
    if pair_ids:
        total_books = db.execute(
            select(func.count(Book.book_id)).where(and_(Book.pair_id.in_(pair_ids), Book.status == "finished"))
        ).scalar() or 0
        progress_rows = db.execute(
            select(Entry.book_id, func.max(Entry.page).label("max_page"))
            .where(Entry.user_id == user_id)
            .group_by(Entry.book_id)
        ).all()
        total_pages = sum(int(row.max_page or 0) for row in progress_rows)

    return ok(
        {
            "total_books": int(total_books),
            "total_pages": int(total_pages),
            "total_entries": int(total_entries),
            "total_days": calc_days_since(current_user.get("created_at", "")),
        },
        request_id=request_id,
    )
