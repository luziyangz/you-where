"""
从 Gutendex 批量同步中文（languages=zh）书目元数据到 catalog_books。

用法：
    cd backend
    python scripts/sync_gutendex_zh_catalog.py
    python scripts/sync_gutendex_zh_catalog.py --max-pages 50 --force

生产 Docker：
    sudo docker compose exec backend python scripts/sync_gutendex_zh_catalog.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.db import SessionLocal  # noqa: E402
from service.store_service import (  # noqa: E402
    seed_default_store_books,
    sync_gutendex_chinese_catalog,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 Gutendex 中文书目")
    parser.add_argument("--max-pages", type=int, default=30, help="最多拉取页数")
    parser.add_argument("--force", action="store_true", help="忽略已同步标记")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        seed_default_store_books(db, update_public_domain=True)
        result = sync_gutendex_chinese_catalog(
            db,
            max_pages=max(1, int(args.max_pages)),
            force=bool(args.force),
        )
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
