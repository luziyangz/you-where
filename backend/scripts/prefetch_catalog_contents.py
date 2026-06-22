"""
预取书城公版书全文到 catalog_contents（部署后首次运行可能需数分钟）。

用法：
    cd backend
    python scripts/prefetch_catalog_contents.py
    python scripts/prefetch_catalog_contents.py --force --catalog-id pg_23962
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.db import SessionLocal  # noqa: E402
from service.catalog_prefetch import prefetch_public_domain_contents  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="预取 Project Gutenberg 公版书全文到站内书库。")
    parser.add_argument("--force", action="store_true", help="即使已有正文也重新拉取")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 本（0 表示全部）")
    parser.add_argument(
        "--catalog-id",
        action="append",
        default=[],
        help="仅处理指定 catalog_id，可重复传入",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = prefetch_public_domain_contents(
            db,
            force=args.force,
            catalog_ids=args.catalog_id or None,
            limit=args.limit if args.limit > 0 else None,
        )
    finally:
        db.close()

    print(
        f"预取完成：成功 {result['ok']}，跳过 {result['skipped']}，失败 {len(result['failed'])} / 共 {result['total']}"
    )
    if result["failed"]:
        print("失败书目：", ", ".join(result["failed"]))


if __name__ == "__main__":
    main()
