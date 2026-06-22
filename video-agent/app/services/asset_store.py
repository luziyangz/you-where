from pathlib import Path

from app.core.paths import storage_path


def asset_path(*parts: str) -> Path:
    return storage_path(*parts)
