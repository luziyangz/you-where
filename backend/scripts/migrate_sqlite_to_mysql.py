#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将 SQLite 数据迁移到 MySQL。

用法：
    python scripts/migrate_sqlite_to_mysql.py --dry-run
    python scripts/migrate_sqlite_to_mysql.py
"""

import argparse
import os
import sqlite3
from pathlib import Path
import sys
from typing import Iterable, Tuple

import pymysql

# 兼容从 backend/scripts 直接执行，确保可导入 backend/common。
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


TABLES: Tuple[str, ...] = (
    "users",
    "sessions",
    "pairs",
    "books",
    "entries",
    "replies",
    "read_marks",
    "catalog_books",
    "catalog_contents",
    "reading_goals",
    "reminder_configs",
)


def get_sqlite_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_mysql_conn() -> pymysql.Connection:
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "youzainaye"),
        charset="utf8mb4",
        autocommit=False,
    )


def fetch_rows(sqlite_conn: sqlite3.Connection, table: str) -> Iterable[sqlite3.Row]:
    cur = sqlite_conn.execute(f"SELECT * FROM {table}")
    return cur.fetchall()


def clear_mysql_table(mysql_conn: pymysql.Connection, table: str) -> None:
    # 为了保证可重复执行迁移，先清空目标表再导入。
    with mysql_conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table}")


def insert_rows(mysql_conn: pymysql.Connection, table: str, rows: Iterable[sqlite3.Row]) -> int:
    rows = list(rows)
    if not rows:
        return 0

    columns = list(rows[0].keys())
    placeholders = ",".join(["%s"] * len(columns))
    columns_sql = ",".join(columns)
    sql = f"INSERT INTO {table} ({columns_sql}) VALUES ({placeholders})"
    values = [tuple(row[col] for col in columns) for row in rows]

    with mysql_conn.cursor() as cur:
        cur.executemany(sql, values)
    return len(values)


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite -> MySQL 迁移脚本")
    parser.add_argument("--dry-run", action="store_true", help="仅输出迁移统计，不写入 MySQL")
    parser.add_argument("--sqlite-path", default=os.path.join("data", "app.db"), help="SQLite 数据库路径")
    parser.add_argument(
        "--skip-missing-table",
        action="store_true",
        help="SQLite 缺失某表时跳过该表（默认遇错即停止）",
    )
    args = parser.parse_args()

    if not os.path.exists(args.sqlite_path):
        raise FileNotFoundError(f"未找到 SQLite 数据库文件: {args.sqlite_path}")

    sqlite_conn = get_sqlite_conn(args.sqlite_path)
    mysql_conn = None
    if not args.dry_run:
        mysql_conn = get_mysql_conn()

    try:
        print("开始迁移（dry_run=%s）" % args.dry_run)
        for table in TABLES:
            try:
                rows = fetch_rows(sqlite_conn, table)
            except sqlite3.OperationalError as exc:
                if args.skip_missing_table:
                    print(f"[{table}] SQLite 中不存在，已跳过: {exc}")
                    continue
                raise
            print(f"[{table}] SQLite 行数: {len(rows)}")
            if args.dry_run:
                continue

            clear_mysql_table(mysql_conn, table)
            inserted = insert_rows(mysql_conn, table, rows)
            print(f"[{table}] MySQL 写入行数: {inserted}")

        if not args.dry_run:
            mysql_conn.commit()
            print("迁移完成并已提交事务。")
        else:
            print("Dry-run 完成，未写入 MySQL。")
    except Exception:
        if mysql_conn is not None:
            mysql_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        if mysql_conn is not None:
            mysql_conn.close()


if __name__ == "__main__":
    main()

