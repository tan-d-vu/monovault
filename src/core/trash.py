"""Per-folder app-managed trash for deleted tracks.

Each watched folder gets its own trash directory at:
    {folder}/.monovault/trash/
        manifest.json   — metadata for trashed entries in THIS folder
        <uuid>.<ext>    — moved audio files (uuid-named to avoid collisions)

Files are moved (not copied) so the operation is fast on the same volume.
Manifest writes are atomic (tmp + os.replace) so a crash during write can't
strand a trashed file with no metadata to restore it.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from ..models.track import Track

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrashEntry:
    trash_id: str
    trash_filename: str
    original_relpath: str
    deleted_at: str
    title: str
    artist: str
    album: str
    duration: float
    categories: list[str]
    comments: str
    date_added: str

    def to_dict(self) -> dict:
        return {
            "trash_filename": self.trash_filename,
            "original_relpath": self.original_relpath,
            "deleted_at": self.deleted_at,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "categories": list(self.categories),
            "comments": self.comments,
            "date_added": self.date_added,
        }

    @classmethod
    def from_dict(cls, trash_id: str, data: dict) -> TrashEntry:
        return cls(
            trash_id=trash_id,
            trash_filename=data["trash_filename"],
            original_relpath=data["original_relpath"],
            deleted_at=data.get("deleted_at", ""),
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            duration=float(data.get("duration", 0.0)),
            categories=list(data.get("categories", [])),
            comments=data.get("comments", ""),
            date_added=data.get("date_added", ""),
        )


class TrashManager:
    """Owns the trash directory and manifest for a single watched folder."""

    def __init__(self, folder_root: Path):
        self._folder_root = Path(folder_root)
        self._trash_dir = self._folder_root / ".monovault" / "trash"
        self._manifest_path = self._trash_dir / "manifest.json"
        self._data: dict[str, dict] = {}
        self._load_manifest()

    def move_to_trash(self, track: Track) -> str:
        """Move the track's file into trash and record manifest. Returns trash_id."""
        source = Path(track.file_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        try:
            original_relpath = str(
                PurePosixPath(source.relative_to(self._folder_root))
            )
        except ValueError as exc:
            raise ValueError(
                f"Track file '{source}' is not under folder root '{self._folder_root}'"
            ) from exc

        self._trash_dir.mkdir(parents=True, exist_ok=True)

        trash_id = uuid.uuid4().hex
        extension = source.suffix
        trash_filename = f"{trash_id}{extension}"
        destination = self._trash_dir / trash_filename

        shutil.move(str(source), str(destination))

        entry = TrashEntry(
            trash_id=trash_id,
            trash_filename=trash_filename,
            original_relpath=original_relpath,
            deleted_at=datetime.now().isoformat(timespec="seconds"),
            title=track.title,
            artist=track.artist,
            album=track.album,
            duration=track.duration,
            categories=list(track.categories),
            comments=track.comments,
            date_added=track.date_added,
        )
        self._data[trash_id] = entry.to_dict()
        self._save_manifest()
        return trash_id

    def restore(self, trash_id: str) -> Path:
        """Move a trashed file back to its original path. Returns the actual path written.

        On collision (file already exists at original path), restore as
        '<stem> (restored).<ext>', escalating to '(restored 2)', '(restored 3)', ...
        """
        if trash_id not in self._data:
            raise KeyError(f"Unknown trash id: {trash_id}")

        entry_data = self._data[trash_id]
        source = self._trash_dir / entry_data["trash_filename"]
        if not source.exists():
            raise FileNotFoundError(f"Trashed file missing on disk: {source}")

        original = self._folder_root / entry_data["original_relpath"]
        destination = self._resolve_collision(original)

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

        del self._data[trash_id]
        self._save_manifest()
        return destination

    def purge(self, trash_id: str) -> None:
        """Permanently delete a trashed file and remove its manifest entry."""
        entry_data = self._data.pop(trash_id, None)
        if entry_data is None:
            return

        target = self._trash_dir / entry_data["trash_filename"]
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(f"Failed to unlink trashed file {target}: {exc}")
        self._save_manifest()

    def list_entries(self) -> list[TrashEntry]:
        return [TrashEntry.from_dict(tid, data) for tid, data in self._data.items()]

    def get(self, trash_id: str) -> TrashEntry | None:
        data = self._data.get(trash_id)
        return TrashEntry.from_dict(trash_id, data) if data else None

    def folder_root(self) -> Path:
        return self._folder_root

    def _resolve_collision(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        candidate = path.with_name(f"{stem} (restored){suffix}")
        n = 2
        while candidate.exists():
            candidate = path.with_name(f"{stem} (restored {n}){suffix}")
            n += 1
        return candidate

    def _load_manifest(self) -> None:
        try:
            if self._manifest_path.exists():
                self._data = json.loads(self._manifest_path.read_text())
            else:
                self._data = {}
        except (json.JSONDecodeError, OSError, PermissionError):
            self._data = {}

    def _save_manifest(self) -> None:
        self._trash_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self._manifest_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(self._data, indent=2))
        os.replace(tmp_path, self._manifest_path)
