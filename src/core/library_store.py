import json
import os
from datetime import date
from pathlib import Path


class LibraryStore:
    def __init__(self):
        config_dir = Path.home() / ".monovault"
        config_dir.mkdir(exist_ok=True)
        self._path = config_dir / "library.json"
        self._data: dict[str, str] = {}
        self._load()

    def record_if_new(self, file_path: str) -> str:
        if file_path not in self._data:
            mtime = os.path.getmtime(file_path)
            self._data[file_path] = date.fromtimestamp(mtime).isoformat()
            self.save()
        return self._data[file_path]

    def get(self, file_path: str) -> str:
        return self._data.get(file_path, "")

    def save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2))

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}
