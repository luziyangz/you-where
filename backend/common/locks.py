from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Iterator


_LOCKS_GUARD = Lock()
_NAMED_LOCKS: dict[str, Lock] = {}


def _get_named_lock(key: str) -> Lock:
    with _LOCKS_GUARD:
        lock = _NAMED_LOCKS.get(key)
        if lock is None:
            lock = Lock()
            _NAMED_LOCKS[key] = lock
        return lock


@contextmanager
def acquire_named_locks(*keys: str) -> Iterator[None]:
    normalized_keys = sorted({key for key in keys if key})
    locks = [_get_named_lock(key) for key in normalized_keys]
    for lock in locks:
        lock.acquire()
    try:
        yield
    finally:
        for lock in reversed(locks):
            lock.release()
