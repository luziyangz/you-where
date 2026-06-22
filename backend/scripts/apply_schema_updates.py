"""
Apply non-destructive schema updates for existing local or MySQL databases.

新环境建表优先：
  - MySQL：执行 scripts/mysql_init.sql（与 common/models.py 22 表对齐）
  - 或本脚本：Base.metadata.create_all + 下方增量补丁

表结构真相来源：backend/common/models.py

Usage:
    # 本地开发（已安装 requirements.txt）
    cd backend
    python scripts/apply_schema_updates.py

    # 生产/云端 Docker（推荐，宿主机无需安装 sqlalchemy）
    cd /opt/you-where-backend
    sudo docker compose exec backend python scripts/apply_schema_updates.py
    # 或
    sudo sh scripts/apply_schema.sh
"""

from pathlib import Path
import sys

try:
    from sqlalchemy import inspect, text
except ModuleNotFoundError:
    print(
        "错误：当前 Python 环境未安装 sqlalchemy。\n"
        "生产环境请在 backend 容器内执行，不要直接在宿主机运行：\n"
        "  sudo docker compose exec backend python scripts/apply_schema_updates.py\n"
        "  sudo sh scripts/apply_schema.sh\n"
        "本地开发请先：pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.db import engine
from common.db_safety import assert_static_ddl_sql, log_schema_sync_status
from common.models import Base


def _add_books_catalog_id_column_if_missing() -> None:
    inspector = inspect(engine)
    if "books" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("books")}
    if "catalog_id" in columns:
        return

    dialect = engine.dialect.name
    alter_sql = assert_static_ddl_sql("ALTER TABLE books ADD COLUMN catalog_id VARCHAR(64) NULL")
    with engine.begin() as conn:
        conn.execute(text(alter_sql))
        if dialect == "mysql":
            conn.execute(text("CREATE INDEX idx_books_catalog_id ON books (catalog_id)"))
        else:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_books_catalog_id ON books (catalog_id)"))


def _add_catalog_books_extra_columns_if_missing() -> None:
    inspector = inspect(engine)
    if "catalog_books" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("catalog_books")}
    dialect = engine.dialect.name

    def run_alter(sql: str) -> None:
        with engine.begin() as conn:
            conn.execute(text(assert_static_ddl_sql(sql)))

    if "owner_user_id" not in columns:
        run_alter("ALTER TABLE catalog_books ADD COLUMN owner_user_id VARCHAR(64) NULL")
        if dialect == "mysql":
            run_alter("CREATE INDEX idx_catalog_owner ON catalog_books (owner_user_id)")
        else:
            run_alter("CREATE INDEX IF NOT EXISTS idx_catalog_owner ON catalog_books (owner_user_id)")
        columns.add("owner_user_id")

    if "douban_rating" not in columns:
        run_alter("ALTER TABLE catalog_books ADD COLUMN douban_rating VARCHAR(16) NULL")

    if "placeholder_pages" not in columns:
        run_alter("ALTER TABLE catalog_books ADD COLUMN placeholder_pages INTEGER NULL")

    if "store_category" not in columns:
        run_alter("ALTER TABLE catalog_books ADD COLUMN store_category VARCHAR(32) NULL")
        if dialect == "mysql":
            run_alter("CREATE INDEX idx_catalog_store_category ON catalog_books (store_category)")
        else:
            run_alter("CREATE INDEX IF NOT EXISTS idx_catalog_store_category ON catalog_books (store_category)")


def _add_users_reader_options_column_if_missing() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "reader_options" in columns:
        return

    alter_sql = "ALTER TABLE users ADD COLUMN reader_options TEXT NULL"
    with engine.begin() as conn:
        conn.execute(text(alter_sql))


def _widen_catalog_contents_content_text_if_needed() -> None:
    """MySQL TEXT 上限约 64KB，长篇正文需 LONGTEXT。"""
    if engine.dialect.name != "mysql":
        return
    inspector = inspect(engine)
    if "catalog_contents" not in inspector.get_table_names():
        return
    for col in inspector.get_columns("catalog_contents"):
        if col["name"] != "content_text":
            continue
        col_type = str(col["type"]).upper()
        if "LONGTEXT" in col_type:
            return
        break
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE catalog_contents MODIFY COLUMN content_text LONGTEXT NOT NULL")
        )


def _add_phone_number_column_if_missing() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "phone_number" in columns:
        return

    dialect = engine.dialect.name
    alter_sql = "ALTER TABLE users ADD COLUMN phone_number VARCHAR(32) NULL"
    with engine.begin() as conn:
        conn.execute(text(alter_sql))
        if dialect == "mysql":
            conn.execute(text("CREATE UNIQUE INDEX uq_users_phone_number ON users (phone_number)"))
        else:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone_number ON users (phone_number)"))


def _add_feed_posts_book_title_index_if_missing() -> None:
    """书摘 explore 按书名 LIKE 检索，数据量大时需索引。"""
    inspector = inspect(engine)
    if "feed_posts" not in inspector.get_table_names():
        return

    existing = {item["name"] for item in inspector.get_indexes("feed_posts")}
    if "idx_feed_posts_book_title" in existing:
        return

    dialect = engine.dialect.name
    if dialect == "mysql":
        sql = "CREATE INDEX idx_feed_posts_book_title ON feed_posts (book_title)"
    else:
        sql = "CREATE INDEX IF NOT EXISTS idx_feed_posts_book_title ON feed_posts (book_title)"
    with engine.begin() as conn:
        conn.execute(text(assert_static_ddl_sql(sql)))


def _add_entries_quote_text_column_if_missing() -> None:
    inspector = inspect(engine)
    if "entries" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("entries")}
    if "quote_text" in columns:
        return

    alter_sql = "ALTER TABLE entries ADD COLUMN quote_text TEXT NULL"
    with engine.begin() as conn:
        conn.execute(text(assert_static_ddl_sql(alter_sql)))


def main() -> None:
    Base.metadata.create_all(bind=engine)
    _add_books_catalog_id_column_if_missing()
    _add_catalog_books_extra_columns_if_missing()
    _add_users_reader_options_column_if_missing()
    _add_phone_number_column_if_missing()
    _widen_catalog_contents_content_text_if_needed()
    _add_feed_posts_book_title_index_if_missing()
    _add_entries_quote_text_column_if_missing()
    print("Schema updates applied.")
    log_schema_sync_status(engine)


if __name__ == "__main__":
    main()
