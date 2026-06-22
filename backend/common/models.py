from sqlalchemy import Column, Index, Integer, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(64), primary_key=True)
    open_id = Column(String(128), nullable=False, unique=True)
    phone_number = Column(String(32), nullable=True, unique=True)
    nickname = Column(String(64), nullable=False)
    avatar = Column(String(512), nullable=False, default="")
    join_code = Column(String(16), nullable=False, unique=True)
    agreement_accepted_at = Column(String(64), nullable=True)
    created_at = Column(String(64), nullable=False)
    # JSON：书城阅读器偏好（字号、主题、亮度），账号级同步
    reader_options = Column(Text, nullable=True)


class SessionModel(Base):
    __tablename__ = "sessions"

    token = Column(String(256), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    expires_at = Column(String(64), nullable=False)
    created_at = Column(String(64), nullable=False)


class Pair(Base):
    __tablename__ = "pairs"

    pair_id = Column(String(64), primary_key=True)
    user_a_id = Column(String(64), nullable=False, index=True)
    user_b_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)


class ActivePairLock(Base):
    __tablename__ = "active_pair_locks"

    user_id = Column(String(64), primary_key=True)
    pair_id = Column(String(64), nullable=False, index=True)
    created_at = Column(String(64), nullable=False)


class PairRequest(Base):
    """绑定/解除关系申请。超过 7 天未处理由服务层视为 rejected。"""

    __tablename__ = "pair_requests"
    __table_args__ = (
        Index("idx_pair_requests_target_status", "target_user_id", "status"),
        Index("idx_pair_requests_requester_status", "requester_user_id", "status"),
        Index("idx_pair_requests_pair_status", "pair_id", "status"),
    )

    request_id = Column(String(64), primary_key=True)
    request_type = Column(String(16), nullable=False)
    requester_user_id = Column(String(64), nullable=False)
    target_user_id = Column(String(64), nullable=False)
    pair_id = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False)
    created_at = Column(String(64), nullable=False)
    responded_at = Column(String(64), nullable=True)
    responded_by = Column(String(64), nullable=True)


class PairBlock(Base):
    """关系解除后的永久互绑禁止记录。user_low_id/user_high_id 保持排序。"""

    __tablename__ = "pair_blocks"
    __table_args__ = (
        PrimaryKeyConstraint("user_low_id", "user_high_id", name="pk_pair_blocks"),
    )

    user_low_id = Column(String(64), nullable=False)
    user_high_id = Column(String(64), nullable=False)
    reason = Column(String(64), nullable=False, default="unbound")
    created_at = Column(String(64), nullable=False)


class Book(Base):
    __tablename__ = "books"

    book_id = Column(String(64), primary_key=True)
    pair_id = Column(String(64), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    author = Column(String(200), nullable=False, default="")
    total_pages = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False)
    # 来自书城创建时写入，用于前端打开详情与正文；手动添加的书为空
    catalog_id = Column(String(64), nullable=True)
    created_by = Column(String(64), nullable=False)
    created_at = Column(String(64), nullable=False)
    finished_at = Column(String(64), nullable=True)


class ActiveBookLock(Base):
    __tablename__ = "active_book_locks"

    pair_id = Column(String(64), primary_key=True)
    book_id = Column(String(64), nullable=False, index=True)
    created_at = Column(String(64), nullable=False)


class BookReadProgress(Base):
    """用户在某一本共读书内的正文阅读页码；按 book_id 隔离不同伙伴关系。"""

    __tablename__ = "book_read_progress"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "book_id", name="pk_book_read_progress"),
        Index("idx_book_read_progress_book", "book_id"),
    )

    user_id = Column(String(64), nullable=False)
    book_id = Column(String(64), nullable=False)
    last_page = Column(Integer, nullable=False, default=1)
    updated_at = Column(String(64), nullable=False)


class BookSwitchRequest(Base):
    """换书申请：需共读伙伴同意后方可切换在读书目。"""

    __tablename__ = "book_switch_requests"
    __table_args__ = (Index("idx_book_switch_pair_status", "pair_id", "status"),)

    request_id = Column(String(64), primary_key=True)
    pair_id = Column(String(64), nullable=False, index=True)
    requested_by = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    from_book_id = Column(String(64), nullable=True)
    catalog_id = Column(String(64), nullable=True)
    title = Column(String(200), nullable=False)
    author = Column(String(200), nullable=False, default="")
    total_pages = Column(Integer, nullable=False)
    created_at = Column(String(64), nullable=False)
    responded_at = Column(String(64), nullable=True)
    responded_by = Column(String(64), nullable=True)


class CatalogBook(Base):
    __tablename__ = "catalog_books"

    catalog_id = Column(String(64), primary_key=True)
    source = Column(String(32), nullable=False)
    source_book_id = Column(String(64), nullable=False)
    title = Column(String(200), nullable=False)
    author = Column(String(200), nullable=False, default="")
    language = Column(String(32), nullable=False, default="")
    cover_url = Column(String(512), nullable=False, default="")
    detail_url = Column(String(512), nullable=False, default="")
    text_url = Column(String(512), nullable=False, default="")
    # 用户自建书目可见范围；NULL 表示平台公共书城
    owner_user_id = Column(String(64), nullable=True, index=True)
    # 展示用评分（如豆瓣），列表按此字段降序
    douban_rating = Column(String(16), nullable=True)
    # 书城分类 Tab（fiction / classical / world_fiction 等，见 store_categories.py）
    store_category = Column(String(32), nullable=True, index=True)
    # 无本地正文时用于共读目标的预估总页数（外链书、书单卡片）
    placeholder_pages = Column(Integer, nullable=True)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)


class CatalogContent(Base):
    __tablename__ = "catalog_contents"

    catalog_id = Column(String(64), primary_key=True)
    # MySQL 默认 Text 仅 64KB；Gutenberg 等长篇需 LONGTEXT
    content_text = Column(Text().with_variant(LONGTEXT(), "mysql"), nullable=False)
    content_len = Column(Integer, nullable=False)
    page_size_chars = Column(Integer, nullable=False)
    total_pages = Column(Integer, nullable=False)
    etag = Column(String(128), nullable=True)
    last_fetched_at = Column(String(64), nullable=False)


class CatalogReadProgress(Base):
    """用户在书城正文内的阅读页码；展示共读进度时会与日记条目页码取较大值。"""

    __tablename__ = "catalog_read_progress"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "catalog_id", name="pk_catalog_read_progress"),
        Index("idx_catalog_read_progress_catalog", "catalog_id"),
    )

    user_id = Column(String(64), nullable=False)
    catalog_id = Column(String(64), nullable=False)
    last_page = Column(Integer, nullable=False, default=1)
    updated_at = Column(String(64), nullable=False)


class CatalogFavorite(Base):
    """用户收藏的书城书目（catalog_id）。"""

    __tablename__ = "catalog_favorites"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "catalog_id", name="pk_catalog_favorites"),
        Index("idx_catalog_favorites_user_created", "user_id", "created_at"),
    )

    user_id = Column(String(64), nullable=False)
    catalog_id = Column(String(64), nullable=False)
    created_at = Column(String(64), nullable=False)


class CatalogReaderMark(Base):
    """用户在书城正文内的划重点 / 随感（按页与段落序号），云端同步。"""

    __tablename__ = "catalog_reader_marks"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "catalog_id", "page", "para_index", name="pk_catalog_reader_marks"),
        Index("idx_catalog_reader_marks_catalog_user", "catalog_id", "user_id"),
    )

    user_id = Column(String(64), nullable=False)
    catalog_id = Column(String(64), nullable=False)
    page = Column(Integer, nullable=False)
    para_index = Column(Integer, nullable=False)
    style = Column(String(16), nullable=False)
    note = Column(Text, nullable=False, default="")
    text_snap = Column(String(512), nullable=False, default="")
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (
        UniqueConstraint("book_id", "user_id", "client_request_id", name="uq_entries_idempotent"),
        Index("idx_entries_book_created", "book_id", "created_at"),
        Index("idx_entries_book_user_page", "book_id", "user_id", "page"),
    )

    entry_id = Column(String(64), primary_key=True)
    book_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    page = Column(Integer, nullable=False)
    note_content = Column(Text, nullable=False, default="")
    quote_text = Column(Text, nullable=True)
    created_at = Column(String(64), nullable=False)
    client_request_id = Column(String(128), nullable=True)


class Reply(Base):
    __tablename__ = "replies"
    __table_args__ = (
        Index("idx_replies_entry_created", "entry_id", "created_at"),
    )

    reply_id = Column(String(64), primary_key=True)
    entry_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(String(64), nullable=False)


class ReadMark(Base):
    __tablename__ = "read_marks"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "book_id", name="pk_read_marks"),
    )

    user_id = Column(String(64), nullable=False)
    book_id = Column(String(64), nullable=False)
    last_read_at = Column(String(64), nullable=False)


class ReadingGoal(Base):
    __tablename__ = "reading_goals"

    user_id = Column(String(64), primary_key=True)
    period_days = Column(Integer, nullable=False, default=30)
    target_books = Column(Integer, nullable=False, default=1)
    target_days = Column(Integer, nullable=False, default=20)
    updated_at = Column(String(64), nullable=False)


class ReminderConfig(Base):
    __tablename__ = "reminder_configs"

    user_id = Column(String(64), primary_key=True)
    enabled = Column(Integer, nullable=False, default=1)
    remind_time = Column(String(8), nullable=False, default="21:00")
    timezone = Column(String(64), nullable=False, default="Asia/Shanghai")
    updated_at = Column(String(64), nullable=False)


class ReminderDeliveryLog(Base):
    __tablename__ = "reminder_delivery_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "delivery_date", name="uq_reminder_delivery_daily"),
        Index("idx_reminder_delivery_user_created", "user_id", "created_at"),
    )

    delivery_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    delivery_date = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False)
    error_message = Column(Text, nullable=False, default="")
    created_at = Column(String(64), nullable=False)


class FeedPost(Base):
    __tablename__ = "feed_posts"
    __table_args__ = (
        Index("idx_feed_posts_created", "created_at"),
        Index("idx_feed_posts_user", "user_id"),
        Index("idx_feed_posts_book_title", "book_title"),
    )

    post_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False)
    entry_id = Column(String(64), nullable=False, unique=True)
    book_title = Column(String(200), nullable=False, default="")
    excerpt = Column(Text, nullable=False, default="")
    status = Column(String(16), nullable=False, default="published")
    created_at = Column(String(64), nullable=False)


class FeedComment(Base):
    __tablename__ = "feed_comments"
    __table_args__ = (
        Index("idx_feed_comments_post_created", "post_id", "created_at"),
    )

    comment_id = Column(String(64), primary_key=True)
    post_id = Column(String(64), nullable=False)
    user_id = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(String(64), nullable=False)


class UgcReport(Base):
    """用户举报/投诉记录，满足小程序 UGC 合规留存要求。"""

    __tablename__ = "ugc_reports"
    __table_args__ = (
        Index("idx_ugc_reports_created", "created_at"),
        Index("idx_ugc_reports_reporter", "reporter_user_id"),
        Index("idx_ugc_reports_target", "target_type", "target_id"),
    )

    report_id = Column(String(64), primary_key=True)
    reporter_user_id = Column(String(64), nullable=False)
    target_type = Column(String(32), nullable=False)
    target_id = Column(String(64), nullable=False, default="")
    target_user_id = Column(String(64), nullable=True)
    reason_code = Column(String(32), nullable=False)
    description = Column(Text, nullable=False, default="")
    content_snapshot = Column(Text, nullable=False, default="")
    status = Column(String(16), nullable=False, default="pending")
    created_at = Column(String(64), nullable=False)
