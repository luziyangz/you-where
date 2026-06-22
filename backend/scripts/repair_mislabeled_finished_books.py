#!/usr/bin/env python3
"""
将「status=finished 但双方未读至末页」的历史书目改为 switched。

用法：
    cd backend
    python scripts/repair_mislabeled_finished_books.py
    python scripts/repair_mislabeled_finished_books.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select

from common.db import SessionLocal
from common.models import Book
from common.reading_enums import BOOK_STATUS_FINISHED, BOOK_STATUS_SWITCHED
from service.reading_service import book_is_truly_finished, utc_now


def main() -> None:
    parser = argparse.ArgumentParser(description="修复误标为 finished 的共读书目")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不写库")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(select(Book).where(Book.status == BOOK_STATUS_FINISHED)).scalars().all()
        fixed = 0
        for book in rows:
            if book_is_truly_finished(db, book):
                continue
            fixed += 1
            print(f"  {book.book_id} | {book.title[:40]} | -> switched")
            if not args.dry_run:
                book.status = BOOK_STATUS_SWITCHED
                if not book.finished_at:
                    book.finished_at = utc_now()
        if not args.dry_run and fixed:
            db.commit()
        print(f"共检查 finished={len(rows)}，需修正={fixed}，dry_run={args.dry_run}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
