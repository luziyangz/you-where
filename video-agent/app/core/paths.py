from pathlib import Path

from app.core.config import settings


def storage_root() -> Path:
    return Path(settings.storage_root).resolve()


def storage_path(*parts: str) -> Path:
    root = storage_root()
    path = (root.joinpath(*parts)).resolve()
    if root != path and root not in path.parents:
        msg = "path escapes storage root"
        raise ValueError(msg)
    return path
