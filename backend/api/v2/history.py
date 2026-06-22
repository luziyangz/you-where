# -*- coding: utf-8 -*-
"""阅读历史（委托 reading_service，与 /users/me/reading-history 口径一致）。"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.v2.common import get_current_user, get_request_id, ok
from common.db import get_db_session
from service import reading_service

router = APIRouter(prefix="/profile", tags=["v2-history"])


@router.get("/history")
def profile_history(
    page: int = 1,
    page_size: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(
        reading_service.get_reading_history(db, current_user["user_id"], page, page_size),
        request_id=request_id,
    )
