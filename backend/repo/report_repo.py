from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from common.models import UgcReport


def create_report(db: Session, values: dict) -> UgcReport:
    row = UgcReport(**values)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def count_reports_by_reporter_since(db: Session, reporter_user_id: str, since_iso: str) -> int:
    return int(
        db.execute(
            select(func.count(UgcReport.report_id)).where(
                UgcReport.reporter_user_id == reporter_user_id,
                UgcReport.created_at >= since_iso,
            )
        ).scalar_one()
        or 0
    )


def find_recent_duplicate(
    db: Session,
    reporter_user_id: str,
    target_type: str,
    target_id: str,
    since_iso: str,
) -> Optional[UgcReport]:
    if not target_id:
        return None
    return db.execute(
        select(UgcReport).where(
            UgcReport.reporter_user_id == reporter_user_id,
            UgcReport.target_type == target_type,
            UgcReport.target_id == target_id,
            UgcReport.created_at >= since_iso,
        )
    ).scalar_one_or_none()
