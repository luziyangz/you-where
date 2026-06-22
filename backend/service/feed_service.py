from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from common.errors import ApiError
from common.models import FeedPost
from repo import feed_repo, reading_repo as repo
from service.reading_service import effective_user_book_progress, new_id, utc_now


def _trim_excerpt(text: str, max_len: int = 300) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ApiError(40021, "摘录不能为空", 400)
    if len(cleaned) > max_len:
        return cleaned[:max_len]
    return cleaned


def publish_entry_to_feed(
    db: Session,
    current_user: Dict[str, Any],
    entry_id: str,
    excerpt: str,
    confirm: bool,
) -> Dict[str, Any]:
    if not confirm:
        raise ApiError(40022, "请先确认分享内容", 400)

    entry = repo.get_entry_by_id(db, entry_id)
    if not entry:
        raise ApiError(40421, "记录不存在", 404)
    if entry.user_id != current_user["user_id"]:
        raise ApiError(40321, "只能分享自己的记录", 403)

    book = repo.get_book_by_id(db, entry.book_id)
    if not book:
        raise ApiError(40411, "书籍不存在", 404)
    pair = repo.get_active_pair(db, current_user["user_id"])
    if not pair or pair.pair_id != book.pair_id:
        raise ApiError(40302, "无权操作这本书", 403)

    my_progress = effective_user_book_progress(db, book, current_user["user_id"])
    if int(entry.page) > my_progress and (entry.note_content or "").strip():
        raise ApiError(40023, "锁定内容暂不可分享", 400)

    existing = feed_repo.get_post_by_entry_id(db, entry_id)
    if existing and existing.status == "published":
        raise ApiError(40921, "该记录已分享过", 409)

    safe_excerpt = _trim_excerpt(excerpt or getattr(entry, "quote_text", None) or entry.note_content)
    if existing:
        existing.excerpt = safe_excerpt
        existing.book_title = book.title or "共读书目"
        existing.status = "published"
        existing.created_at = utc_now()
        db.commit()
        db.refresh(existing)
        row = existing
    else:
        row = FeedPost(
            post_id=new_id("fp"),
            user_id=current_user["user_id"],
            entry_id=entry_id,
            book_title=book.title or "共读书目",
            excerpt=safe_excerpt,
            status="published",
            created_at=utc_now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return _serialize_post(db, row, current_user["user_id"])


def list_my_shares(db: Session, current_user: Dict[str, Any], page: int, page_size: int) -> Dict[str, Any]:
    user_id = current_user["user_id"]
    safe_page = max(1, int(page or 1))
    safe_size = min(50, max(1, int(page_size or 20)))
    offset = (safe_page - 1) * safe_size
    total = feed_repo.count_published_posts_by_user(db, user_id)
    rows = feed_repo.list_published_posts_by_user(db, user_id, offset, safe_size)
    author = repo.get_user_by_id(db, user_id)
    posts = [_serialize_post(db, row, user_id, author) for row in rows]
    return {
        "posts": posts,
        "pagination": {
            "page": safe_page,
            "page_size": safe_size,
            "total": total,
            "has_more": offset + len(rows) < total,
        },
    }


def list_explore_shares(
    db: Session,
    current_user: Dict[str, Any],
    page: int,
    page_size: int,
    book_query: str = "",
) -> Dict[str, Any]:
    """书友主动分享的摘录（只读发现，不含互动）。"""
    viewer_id = current_user["user_id"]
    safe_page = max(1, int(page or 1))
    safe_size = min(50, max(1, int(page_size or 20)))
    offset = (safe_page - 1) * safe_size
    query = (book_query or "").strip()[:64]
    total = feed_repo.count_explore_posts(db, viewer_id, query or None)
    rows = feed_repo.list_explore_posts(db, viewer_id, offset, safe_size, query or None)
    user_ids = {row.user_id for row in rows}
    users_by_id = {user.user_id: user for user in repo.list_users_by_ids(db, list(user_ids))}
    posts = [_serialize_post(db, row, viewer_id, users_by_id.get(row.user_id)) for row in rows]
    return {
        "posts": posts,
        "pagination": {
            "page": safe_page,
            "page_size": safe_size,
            "total": total,
            "has_more": offset + len(rows) < total,
        },
    }


def get_share_post(db: Session, current_user: Dict[str, Any], post_id: str) -> Dict[str, Any]:
    row = feed_repo.get_post_by_id(db, post_id)
    if not row or row.status != "published":
        raise ApiError(40422, "分享不存在或已撤回", 404)
    author = repo.get_user_by_id(db, row.user_id)
    return _serialize_post(db, row, current_user["user_id"], author)


def delete_feed_post(db: Session, current_user: Dict[str, Any], post_id: str) -> Dict[str, Any]:
    post = feed_repo.get_post_by_id(db, post_id)
    if not post:
        raise ApiError(40422, "分享不存在", 404)
    if post.user_id != current_user["user_id"]:
        raise ApiError(40322, "只能删除自己的分享", 403)
    post.status = "hidden"
    db.commit()
    return {"post_id": post_id, "deleted": True}


def _serialize_post(
    db: Session,
    row: FeedPost,
    viewer_id: str,
    author=None,
) -> Dict[str, Any]:
    if author is None:
        author = repo.get_user_by_id(db, row.user_id)
    return {
        "post_id": row.post_id,
        "entry_id": row.entry_id,
        "user_id": row.user_id,
        "nickname": author.nickname if author else "书友",
        "avatar": author.avatar if author else "",
        "book_title": row.book_title,
        "excerpt": row.excerpt,
        "created_at": row.created_at,
        "is_mine": row.user_id == viewer_id,
        "share_title": f"{author.nickname if author else '书友'}的共读摘录",
    }
