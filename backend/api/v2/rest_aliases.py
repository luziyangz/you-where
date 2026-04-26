from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.v2.common import GoalPayload, ReminderPayload, get_current_user, get_request_id, ok
from common.db import get_db_session
from service import reading_service


router = APIRouter(tags=["v2-resources"])


class UserUpdatePayload(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)


class PairCreatePayload(BaseModel):
    join_code: str = Field(min_length=6, max_length=6)


class BookCreatePayload(BaseModel):
    catalog_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    author: str = Field(default="", max_length=200)
    total_pages: Optional[int] = Field(default=None, ge=1, le=50000)


class BookEntryCreatePayload(BaseModel):
    page: int = Field(ge=1, le=50000)
    note_content: str = Field(default="", max_length=200)
    mark_finished: bool = False
    client_request_id: Optional[str] = None


class ReadMarkPayload(BaseModel):
    last_entry_id: Optional[str] = None


class ReplyPayload(BaseModel):
    content: str = Field(min_length=1, max_length=200)


def _payload_dict(payload: BaseModel) -> Dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


@router.get("/home")
def get_home_resource(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.get_home(db, current_user), request_id=request_id)


@router.get("/users/me")
def get_current_user_resource(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    return ok(current_user, request_id=request_id)


@router.put("/users/me")
def update_current_user_resource(
    payload: UserUpdatePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.update_current_user(db, current_user["user_id"], payload.nickname), request_id=request_id)


@router.get("/users/me/profile")
def get_current_user_profile_resource(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.get_current_user_profile(db, current_user), request_id=request_id)


@router.get("/users/me/stats")
def get_current_user_stats_resource(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.get_current_user_stats(db, current_user), request_id=request_id)


@router.get("/users/me/reading-history")
def get_current_user_reading_history_resource(
    page: int = Query(default=1, ge=1, le=200),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.get_reading_history(db, current_user["user_id"], page, page_size), request_id=request_id)


@router.get("/users/me/reading-goal")
def get_current_user_reading_goal_resource(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.get_reading_goal(db, current_user["user_id"]), request_id=request_id)


@router.put("/users/me/reading-goal")
def put_current_user_reading_goal_resource(
    payload: GoalPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(
        reading_service.put_reading_goal(
            db,
            current_user["user_id"],
            payload.period_days,
            payload.target_books,
            payload.target_days,
        ),
        request_id=request_id,
    )


@router.get("/users/me/reminder-config")
def get_current_user_reminder_config_resource(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.get_reminder_config(db, current_user["user_id"]), request_id=request_id)


@router.put("/users/me/reminder-config")
def put_current_user_reminder_config_resource(
    payload: ReminderPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(
        reading_service.put_reminder_config(
            db,
            current_user["user_id"],
            payload.enabled,
            payload.remind_time,
            payload.timezone,
        ),
        request_id=request_id,
    )


@router.get("/pairs/current")
def get_current_pair_resource(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.get_current_pair(db, current_user), request_id=request_id)


@router.post("/pairs")
def create_pair_resource(
    payload: PairCreatePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.create_pair(db, current_user, payload.join_code), request_id=request_id)


@router.delete("/pairs/current")
def delete_current_pair_resource(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.delete_current_pair(db, current_user), request_id=request_id)


@router.get("/books")
def get_books_resource(
    status: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.list_books(db, current_user, status), request_id=request_id)


@router.post("/books")
def create_book_resource(
    payload: BookCreatePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.create_book(db, current_user, _payload_dict(payload)), request_id=request_id)


@router.get("/pairs/current/books/current")
def get_current_pair_book_resource(
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.get_current_pair_book(db, current_user), request_id=request_id)


@router.get("/books/{book_id}/entries")
def get_book_entries_resource(
    book_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.list_book_entries(db, current_user, book_id, page, page_size), request_id=request_id)


@router.post("/books/{book_id}/entries")
def create_book_entry_resource(
    book_id: str,
    payload: BookEntryCreatePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(
        reading_service.create_entry(
            db,
            current_user,
            book_id,
            payload.page,
            payload.note_content,
            payload.mark_finished,
            payload.client_request_id,
        ),
        request_id=request_id,
    )


@router.put("/books/{book_id}/read-mark")
def put_book_read_mark_resource(
    book_id: str,
    payload: ReadMarkPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.put_book_read_mark(db, current_user, book_id, payload.last_entry_id), request_id=request_id)


@router.post("/entries/{entry_id}/replies")
def create_entry_reply_resource(
    entry_id: str,
    payload: ReplyPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(reading_service.reply_entry(db, current_user, entry_id, payload.content), request_id=request_id)
