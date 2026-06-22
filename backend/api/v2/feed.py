from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.v2.common import get_current_user, get_request_id, ok
from common.db import get_db_session
from service import feed_service


router = APIRouter(tags=["v2-share"])


class PublishFeedPayload(BaseModel):
    excerpt: str = Field(default="", max_length=300)
    confirm: bool = False


@router.get("/feed/posts/mine")
def list_my_share_posts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    data = feed_service.list_my_shares(db, current_user, page, page_size)
    return ok(data, request_id)


@router.get("/feed/posts/explore")
def list_explore_share_posts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    book: str = Query(default="", max_length=64),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    data = feed_service.list_explore_shares(db, current_user, page, page_size, book)
    return ok(data, request_id)


@router.get("/feed/posts/{post_id}")
def get_share_post(
    post_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    data = feed_service.get_share_post(db, current_user, post_id)
    return ok(data, request_id)


@router.post("/entries/{entry_id}/publish-to-feed")
def publish_entry_to_feed(
    entry_id: str,
    payload: PublishFeedPayload,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    data = feed_service.publish_entry_to_feed(db, current_user, entry_id, payload.excerpt, payload.confirm)
    return ok(data, request_id)


@router.delete("/feed/posts/{post_id}")
def delete_feed_post(
    post_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    data = feed_service.delete_feed_post(db, current_user, post_id)
    return ok(data, request_id)
