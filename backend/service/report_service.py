from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from common.errors import ApiError
from repo import feed_repo, report_repo, reading_repo as repo
from service.reading_service import new_id, utc_now

REPORT_REASONS = {
    "illegal": "违法违规",
    "porn": "色情低俗",
    "spam": "垃圾广告",
    "infringement": "侵权",
    "abuse": "人身攻击或骚扰",
    "other": "其他问题",
}

ALLOWED_TARGET_TYPES = {"feed_post", "entry", "reply", "app"}
MAX_REPORTS_PER_DAY = 20


def _since_24h_iso() -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=24)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _assert_not_self(reporter_id: str, target_user_id: Optional[str]) -> None:
    if target_user_id and target_user_id == reporter_id:
        raise ApiError(40041, "不能举报自己的内容", 400)


def _assert_pair_access(db: Session, user_id: str, book_id: str) -> None:
    book = repo.get_book_by_id(db, book_id)
    if not book:
        raise ApiError(40411, "书籍不存在", 404)
    pair = repo.get_active_pair(db, user_id)
    if not pair or pair.pair_id != book.pair_id:
        raise ApiError(40302, "无权访问该内容", 403)


def _resolve_target(
    db: Session,
    reporter_id: str,
    target_type: str,
    target_id: str,
) -> tuple[str, str, str]:
    """返回 (target_user_id, content_snapshot, normalized_target_id)。"""
    if target_type == "app":
        return "", "", ""

    if target_type == "feed_post":
        post = feed_repo.get_post_by_id(db, target_id)
        if not post or post.status != "published":
            raise ApiError(40422, "分享内容不存在或已撤回", 404)
        _assert_not_self(reporter_id, post.user_id)
        snap = f"《{post.book_title}》\n{post.excerpt or ''}".strip()
        return post.user_id, snap[:800], post.post_id

    if target_type == "entry":
        entry = repo.get_entry_by_id(db, target_id)
        if not entry:
            raise ApiError(40421, "记录不存在", 404)
        _assert_pair_access(db, reporter_id, entry.book_id)
        _assert_not_self(reporter_id, entry.user_id)
        quote = (getattr(entry, "quote_text", None) or "").strip()
        note = (entry.note_content or "").strip()
        parts = []
        if quote:
            parts.append(f"原文：{quote}")
        if note:
            parts.append(f"想法：{note}")
        if not parts:
            parts.append(f"第 {entry.page} 页进度记录")
        return entry.user_id, "\n".join(parts)[:800], entry.entry_id

    if target_type == "reply":
        reply = repo.get_reply_by_id(db, target_id)
        if not reply:
            raise ApiError(40431, "回复不存在", 404)
        entry = repo.get_entry_by_id(db, reply.entry_id)
        if not entry:
            raise ApiError(40421, "记录不存在", 404)
        _assert_pair_access(db, reporter_id, entry.book_id)
        _assert_not_self(reporter_id, reply.user_id)
        return reply.user_id, (reply.content or "").strip()[:800], reply.reply_id

    raise ApiError(40042, "不支持的举报类型", 400)


def submit_report(
    db: Session,
    current_user: Dict[str, Any],
    *,
    target_type: str,
    target_id: str,
    reason_code: str,
    description: str = "",
) -> Dict[str, Any]:
    reporter_id = current_user["user_id"]
    safe_type = (target_type or "app").strip().lower()
    if safe_type not in ALLOWED_TARGET_TYPES:
        raise ApiError(40042, "不支持的举报类型", 400)

    safe_reason = (reason_code or "").strip().lower()
    if safe_reason not in REPORT_REASONS:
        raise ApiError(40043, "请选择举报原因", 400)

    safe_desc = (description or "").strip()[:500]
    safe_target_id = (target_id or "").strip()[:64]

    if safe_type != "app" and not safe_target_id:
        raise ApiError(40044, "缺少举报对象", 400)

    since = _since_24h_iso()
    if report_repo.count_reports_by_reporter_since(db, reporter_id, since) >= MAX_REPORTS_PER_DAY:
        raise ApiError(42901, "今日举报次数已达上限，请明日再试", 429)

    if safe_type != "app":
        dup = report_repo.find_recent_duplicate(db, reporter_id, safe_type, safe_target_id, since)
        if dup:
            raise ApiError(40941, "你已举报过该内容，我们会尽快处理", 409)

    target_user_id, snapshot, normalized_id = _resolve_target(db, reporter_id, safe_type, safe_target_id)

    row = report_repo.create_report(
        db,
        {
            "report_id": new_id("rpt"),
            "reporter_user_id": reporter_id,
            "target_type": safe_type,
            "target_id": normalized_id,
            "target_user_id": target_user_id or None,
            "reason_code": safe_reason,
            "description": safe_desc,
            "content_snapshot": snapshot,
            "status": "pending",
            "created_at": utc_now(),
        },
    )
    return {
        "report_id": row.report_id,
        "status": row.status,
        "message": "举报已提交，我们会在 24 小时内处理",
    }
