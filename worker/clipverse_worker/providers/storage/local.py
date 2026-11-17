from __future__ import annotations

import shutil
from pathlib import Path


class LocalStorage:
    """Keeps everything in one folder on this computer (default: clipverseai/storage)."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents and p != self.root:
            raise ValueError(f"Storage key escapes the storage folder: {key}")
        return p

    def local_path(self, key: str) -> Path:
        return self._path(key)

    def put_file(self, local: Path, key: str) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if local.resolve() != dest:
            shutil.move(str(local), dest)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()

    def work_dir(self, key: str) -> Path:
        p = self._path(key)
        p.mkdir(parents=True, exist_ok=True)
        return p
