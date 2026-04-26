from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.v2.common import get_request_id, ok
from common.db import get_db_session
from service import store_service


router = APIRouter(tags=["v2-store-reading"])


@router.get("/store/books")
def store_list_books(
    query: Optional[str] = None,
    page: int = 1,
    category: Optional[str] = None,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(store_service.list_books(db, query=query, page=page, category=category), request_id=request_id)


@router.get("/store/books/{catalog_id}")
def store_get_book(
    catalog_id: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(store_service.get_book(db, catalog_id), request_id=request_id)


@router.get("/store/books/{catalog_id}/read")
def store_read_page(
    catalog_id: str,
    page: int = 1,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
):
    return ok(store_service.read_page(db, catalog_id, page=page), request_id=request_id)
