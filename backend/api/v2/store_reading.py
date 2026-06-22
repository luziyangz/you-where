from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.v2.common import get_current_user, get_optional_current_user, get_request_id, ok
from common.db import get_db_session
from common.errors import ApiError
from service import store_service


router = APIRouter(tags=["v2-store-reading"])


class ImportReadUrlPayload(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(default="", max_length=200)
    read_url: str = Field(min_length=8, max_length=512)
    estimated_pages: Optional[int] = Field(default=None, ge=1, le=50000)


class CatalogReadingProgressPayload(BaseModel):
    page: int = Field(ge=1, le=500000)


class CatalogReaderMarkPayload(BaseModel):
    page: int = Field(ge=1, le=500000)
    para_index: int = Field(ge=0, le=50000)
    style: str = Field(default="marker", max_length=16)
    note: str = Field(default="", max_length=500)
    text_snap: str = Field(default="", max_length=512)


@router.get("/store/books")
def store_list_books(
    query: Optional[str] = None,
    page: int = 1,
    category: Optional[str] = None,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
):
    viewer_id = current_user.get("user_id") if current_user else None
    return ok(
        store_service.list_books(db, query=query, page=page, category=category, viewer_user_id=viewer_id),
        request_id=request_id,
    )


@router.get("/store/books/{catalog_id}/reading-progress")
def store_get_catalog_reading_progress(
    catalog_id: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return ok(
        store_service.get_catalog_reading_progress(db, current_user["user_id"], catalog_id),
        request_id=request_id,
    )


@router.get("/store/books/{catalog_id}/marks")
def store_list_catalog_marks(
    catalog_id: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return ok(
        store_service.list_catalog_reader_marks(db, current_user["user_id"], catalog_id),
        request_id=request_id,
    )


@router.put("/store/books/{catalog_id}/marks")
def store_put_catalog_reader_mark(
    catalog_id: str,
    payload: CatalogReaderMarkPayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return ok(
        store_service.upsert_catalog_reader_mark(
            db,
            current_user["user_id"],
            catalog_id,
            payload.page,
            payload.para_index,
            payload.style,
            payload.note,
            payload.text_snap,
        ),
        request_id=request_id,
    )


@router.delete("/store/books/{catalog_id}/marks")
def store_delete_catalog_reader_mark(
    catalog_id: str,
    page: int,
    para_index: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return ok(
        store_service.delete_catalog_reader_mark(db, current_user["user_id"], catalog_id, page, para_index),
        request_id=request_id,
    )


@router.put("/store/books/{catalog_id}/reading-progress")
def store_put_catalog_reading_progress(
    catalog_id: str,
    payload: CatalogReadingProgressPayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return ok(
        store_service.put_catalog_reading_progress(db, current_user["user_id"], catalog_id, payload.page),
        request_id=request_id,
    )


@router.get("/store/my-shelf")
def store_list_my_shelf(
    tab: str = "recent",
    page: int = 1,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return ok(
        store_service.list_my_shelf(db, current_user["user_id"], tab=tab, page=page),
        request_id=request_id,
    )


@router.post("/store/books/{catalog_id}/favorite")
def store_add_book_favorite(
    catalog_id: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return ok(store_service.add_book_favorite(db, current_user["user_id"], catalog_id), request_id=request_id)


@router.delete("/store/books/{catalog_id}/favorite")
def store_remove_book_favorite(
    catalog_id: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return ok(store_service.remove_book_favorite(db, current_user["user_id"], catalog_id), request_id=request_id)


@router.get("/store/books/{catalog_id}")
def store_get_book(
    catalog_id: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
):
    viewer_id = current_user.get("user_id") if current_user else None
    return ok(store_service.get_book(db, catalog_id, viewer_user_id=viewer_id), request_id=request_id)


@router.get("/store/books/{catalog_id}/toc")
def store_get_catalog_toc(
    catalog_id: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return ok(
        store_service.get_catalog_toc(db, catalog_id, reader_user_id=current_user["user_id"]),
        request_id=request_id,
    )


@router.get("/store/books/{catalog_id}/read")
def store_read_page(
    catalog_id: str,
    page: int = 1,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return ok(
        store_service.read_page(db, catalog_id, page=page, reader_user_id=current_user["user_id"]),
        request_id=request_id,
    )


@router.post("/store/books/import-txt")
async def store_import_txt(
    title: str = Form(...),
    author: str = Form(""),
    file: UploadFile = File(...),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    raw = await file.read()
    if not raw:
        raise ApiError(40096, "文件为空或上传失败，请重新选择 TXT", 400)
    data = store_service.import_user_txt_book(db, current_user["user_id"], title, author, raw)
    return ok(data, request_id=request_id)


@router.post("/store/books/import-url")
def store_import_read_url(
    payload: ImportReadUrlPayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    data = store_service.import_user_read_url_book(
        db,
        current_user["user_id"],
        payload.title,
        payload.author,
        payload.read_url,
        estimated_pages=payload.estimated_pages,
    )
    return ok(data, request_id=request_id)
