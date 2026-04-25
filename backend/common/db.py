from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from common.config import settings


def _create_engine():
    if settings.DB_BACKEND == "mysql":
        return create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.MYSQL_POOL_SIZE,
            max_overflow=settings.MYSQL_MAX_OVERFLOW,
            future=True,
        )

    # SQLite 仅用于本地兼容和回滚。
    return create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

