import json
import logging
from pathlib import Path, PurePosixPath

logger = logging.getLogger(__name__)

_MISSING = object()  # sentinel: key absent from cache (not yet analyzed)


class BpmStore:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._data: dict[str, float | None] = {}
        self._path = base_dir / ".monovault" / "bpm_cache.json"
        self._load()

    def get(self, file_path: str) -> object:
        """Return cached BPM, None (analyzed, no result), or _MISSING (not yet analyzed)."""
        key = self._to_key(file_path)
        if key not in self._data:
            return _MISSING
        return self._data[key]

    def set(self, file_path: str, bpm: float | None) -> None:
        key = self._to_key(file_path)
        self._data[key] = bpm

    def remove(self, file_path: str) -> None:
        key = self._to_key(file_path)
        self._data.pop(key, None)

    def save(self) -> None:
        monovault_dir = self._base_dir / ".monovault"
        try:
            monovault_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(
                f"Cannot create .monovault directory in '{self._base_dir}': {e}. "
                "BPM cache skipped for this folder."
            )
            return
        self._path.write_text(json.dumps(self._data, indent=2))

    def _to_key(self, file_path: str) -> str:
        try:
            rel_path = Path(file_path).relative_to(self._base_dir)
            return str(PurePosixPath(rel_path))
        except ValueError:
            logger.warning(
                f"File '{file_path}' is outside base_dir '{self._base_dir}'. "
                "Using absolute path as key."
            )
            return str(PurePosixPath(file_path))

    def _load(self) -> None:
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text())
            else:
                self._data = {}
        except (json.JSONDecodeError, OSError, PermissionError):
            self._data = {}
