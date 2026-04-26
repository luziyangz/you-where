"""
Seed hidden test users into the real users table.

Usage:
    cd backend
    python scripts/seed_test_users.py
    python scripts/seed_test_users.py --reset-active-pairs
"""

from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import sys
import uuid

from sqlalchemy import or_, select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.db import SessionLocal
from common.models import ActivePairLock, Pair, User


TEST_USERS = {
    "a": {
        "open_id": "youzainaye_test_user_a",
        "nickname": "测试用户A",
        "join_code": "900001",
    },
    "b": {
        "open_id": "youzainaye_test_user_b",
        "nickname": "测试用户B",
        "join_code": "900002",
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _join_code(seed: str, attempt: int = 0) -> str:
    digest = hashlib.sha256(f"{seed}:{attempt}".encode("utf-8")).hexdigest()
    number = int(digest[:8], 16) % 900000 + 100000
    return str(number)


def _allocate_fallback_join_code(db, seed: str, reserved_codes: set[str]) -> str:
    for attempt in range(100):
        candidate = _join_code(seed, attempt)
        if candidate in reserved_codes:
            continue
        exists = db.execute(select(User).where(User.join_code == candidate)).scalar_one_or_none()
        if not exists:
            reserved_codes.add(candidate)
            return candidate
    raise RuntimeError("Failed to allocate fallback join code")


def _seed_one_user(db, role: str, reserved_codes: set[str]) -> User:
    spec = TEST_USERS[role]
    now = _utc_now()
    user = db.execute(select(User).where(User.open_id == spec["open_id"])).scalar_one_or_none()
    if not user:
        user = User(
            user_id=_new_id("u"),
            open_id=spec["open_id"],
            phone_number=None,
            nickname=spec["nickname"],
            avatar="",
            join_code=spec["join_code"],
            agreement_accepted_at=None,
            created_at=now,
        )
        db.add(user)
        db.flush()

    conflict = db.execute(select(User).where(User.join_code == spec["join_code"], User.user_id != user.user_id)).scalar_one_or_none()
    if conflict:
        conflict.join_code = _allocate_fallback_join_code(db, conflict.open_id or conflict.user_id, reserved_codes)
        db.flush()

    user.nickname = spec["nickname"]
    user.avatar = ""
    user.join_code = spec["join_code"]
    # Do not auto-accept agreement. Keep the same semantic state as a newly registered user.
    db.flush()
    return user


def _reset_active_pairs(db, user_ids: list[str]) -> int:
    if not user_ids:
        return 0

    pairs = db.execute(
        select(Pair).where(
            Pair.status == "active",
            or_(Pair.user_a_id.in_(user_ids), Pair.user_b_id.in_(user_ids)),
        )
    ).scalars().all()
    if not pairs:
        return 0

    now = _utc_now()
    pair_ids = [pair.pair_id for pair in pairs]
    for pair in pairs:
        pair.status = "unbound"
        pair.updated_at = now
    db.query(ActivePairLock).filter(
        or_(ActivePairLock.user_id.in_(user_ids), ActivePairLock.pair_id.in_(pair_ids))
    ).delete(synchronize_session=False)
    return len(pairs)


def seed_test_users(reset_active_pairs: bool = False) -> dict:
    db = SessionLocal()
    try:
        reserved_codes = {spec["join_code"] for spec in TEST_USERS.values()}
        users = [_seed_one_user(db, role, reserved_codes) for role in ("a", "b")]
        reset_count = _reset_active_pairs(db, [user.user_id for user in users]) if reset_active_pairs else 0
        db.commit()
        return {
            "users": [
                {
                    "role": role.upper(),
                    "user_id": user.user_id,
                    "open_id": user.open_id,
                    "nickname": user.nickname,
                    "join_code": user.join_code,
                }
                for role, user in zip(("a", "b"), users)
            ],
            "reset_active_pairs": reset_count,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed hidden test users into users table.")
    parser.add_argument("--reset-active-pairs", action="store_true", help="Unbind active pairs involving test users for repeated binding tests.")
    args = parser.parse_args()

    result = seed_test_users(reset_active_pairs=args.reset_active_pairs)
    print("Seeded hidden test users:")
    for item in result["users"]:
        print(f"- {item['role']}: user_id={item['user_id']} open_id={item['open_id']} join_code={item['join_code']}")
    if args.reset_active_pairs:
        print(f"Reset active pairs: {result['reset_active_pairs']}")


if __name__ == "__main__":
    main()
