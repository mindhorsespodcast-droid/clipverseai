"""Storage plug: where videos and clips live.

Phase 1 uses LocalStorage (a folder on the laptop). Later a cloud version
(Supabase Storage / R2 / S3) implements the same four methods.
Keys are always forward-slash paths like "projects/<id>/source.mp4".
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def local_path(self, key: str) -> Path:
        """A local file path for reading `key` (cloud versions download it first)."""

    def put_file(self, local: Path, key: str) -> None:
        """Store a finished local file under `key`."""

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...

    def work_dir(self, key: str) -> Path:
        """A local scratch folder for temporary files."""
