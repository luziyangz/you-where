from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v2.common import (
    get_active_pair,
    get_current_user,
    get_partner_id,
    get_request_id,
    ok,

)
from common.db import get_db_session
from common.models import Pair, User
from service import reading_service


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
    return ok(reading_service.get_current_user_stats(db, current_user), request_id=request_id)
