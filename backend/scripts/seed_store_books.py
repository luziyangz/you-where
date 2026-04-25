from pathlib import Path
import argparse
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.db import SessionLocal
from api.v2.store_reading import seed_default_store_books


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed default store books into database.")
    parser.add_argument("--force", action="store_true", help="Clear existing catalog and reseed.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        count = seed_default_store_books(db, force=args.force)
        print(f"Seed completed, inserted: {count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
