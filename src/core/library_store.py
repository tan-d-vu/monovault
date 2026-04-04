import json
import logging
import os
from datetime import date
from pathlib import Path, PurePosixPath

logger = logging.getLogger(__name__)


class LibraryStore:
    def __init__(self, base_dir: Path):
        """Initialize LibraryStore for per-folder mode.

        Args:
            base_dir: Folder path. Store file will be at base_dir/.monovault/library.json
        """
        self._base_dir = base_dir
        self._data: dict[str, str] = {}
        # Per-folder mode: store file at base_dir/.monovault/library.json
        # Don't create dir here — defer until first save (lazy creation)
        self._path = base_dir / ".monovault" / "library.json"
        self._load()

    def record_if_new(self, file_path: str) -> str:
        """Record file with date_added if not already recorded.

        Converts absolute path to relative POSIX key for storage.

        Args:
            file_path: Absolute file path

        Returns:
            ISO date string (date added)
        """
        key = self._to_key(file_path)
        if key not in self._data:
            mtime = os.path.getmtime(file_path)
            self._data[key] = date.fromtimestamp(mtime).isoformat()
            self.save()
        return self._data[key]

    def get(self, file_path: str) -> str:
        """Get date_added for a file.

        Converts absolute path to relative POSIX key for lookup.

        Args:
            file_path: Absolute file path

        Returns:
            ISO date string, or empty string if not found
        """
        key = self._to_key(file_path)
        return self._data.get(key, "")

    def save(self) -> None:
        """Save data to library.json.

        Creates .monovault/ dir lazily on first save.
        If creation fails (read-only filesystem), logs warning and skips save.
        """
        # Ensure .monovault/ dir exists
        monovault_dir = self._base_dir / ".monovault"
        try:
            monovault_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(
                f"Cannot create .monovault directory in '{self._base_dir}': {e}. "
                "Date-added tracking skipped for this folder."
            )
            return

        self._path.write_text(json.dumps(self._data, indent=2))

    def _to_key(self, file_path: str) -> str:
        """Convert file path to storage key.

        Converts absolute path to relative POSIX path from base_dir.
        Falls back to absolute POSIX path for files outside base_dir.

        Args:
            file_path: Absolute file path

        Returns:
            POSIX path string (relative if inside base_dir, absolute otherwise)
        """
        try:
            rel_path = Path(file_path).relative_to(self._base_dir)
            return str(PurePosixPath(rel_path))
        except ValueError:
            # File is outside base_dir (shouldn't happen, but handle gracefully)
            logger.warning(
                f"File '{file_path}' is outside base_dir '{self._base_dir}'. "
                "Using absolute path as key."
            )
            # Convert to POSIX format even for absolute paths
            return str(PurePosixPath(file_path))

    def _load(self) -> None:
        """Load data from library.json if it exists."""
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text())
            else:
                self._data = {}
        except (json.JSONDecodeError, OSError, PermissionError):
            self._data = {}
