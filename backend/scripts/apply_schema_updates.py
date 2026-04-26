"""
Apply non-destructive schema updates for existing local or MySQL databases.

Usage:
    cd backend
    python scripts/apply_schema_updates.py
"""

from pathlib import Path
import sys

from sqlalchemy import inspect, text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.db import engine
from common.models import Base


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


def main() -> None:
    Base.metadata.create_all(bind=engine)
    _add_phone_number_column_if_missing()
    print("Schema updates applied.")


if __name__ == "__main__":
    main()
