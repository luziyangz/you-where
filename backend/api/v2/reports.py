from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.v2.common import get_current_user, get_request_id, ok
from common.db import get_db_session
from service import report_service


router = APIRouter(tags=["v2-reports"])


class SubmitReportPayload(BaseModel):
    target_type: str = Field(default="app", max_length=32)
    target_id: str = Field(default="", max_length=64)
    reason_code: str = Field(..., max_length=32)
    description: str = Field(default="", max_length=500)


@router.post("/reports")
def submit_report(
    payload: SubmitReportPayload,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    data = report_service.submit_report(
        db,
        current_user,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason_code=payload.reason_code,
        description=payload.description,
    )
    return ok(data, request_id)


@router.get("/reports/reasons")
def list_report_reasons(
    request_id: str = Depends(get_request_id),
):
    reasons = [{"code": code, "label": label} for code, label in report_service.REPORT_REASONS.items()]
    return ok({"reasons": reasons}, request_id)
