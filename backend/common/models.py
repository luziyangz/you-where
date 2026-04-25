from sqlalchemy import Column, Index, Integer, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(64), primary_key=True)
    open_id = Column(String(128), nullable=False, unique=True)
    nickname = Column(String(64), nullable=False)
    avatar = Column(String(512), nullable=False, default="")
    join_code = Column(String(16), nullable=False, unique=True)
    agreement_accepted_at = Column(String(64), nullable=True)
    created_at = Column(String(64), nullable=False)


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


class Book(Base):
    __tablename__ = "books"

    book_id = Column(String(64), primary_key=True)
    pair_id = Column(String(64), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    author = Column(String(200), nullable=False, default="")
    total_pages = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False)
    created_by = Column(String(64), nullable=False)
    created_at = Column(String(64), nullable=False)
    finished_at = Column(String(64), nullable=True)


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
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)


class CatalogContent(Base):
    __tablename__ = "catalog_contents"

    catalog_id = Column(String(64), primary_key=True)
    content_text = Column(Text, nullable=False)
    content_len = Column(Integer, nullable=False)
    page_size_chars = Column(Integer, nullable=False)
    total_pages = Column(Integer, nullable=False)
    etag = Column(String(128), nullable=True)
    last_fetched_at = Column(String(64), nullable=False)


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

