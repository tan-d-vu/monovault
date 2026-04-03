import json
import os
from pathlib import Path


class Config:
    def __init__(self):
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / "config.json"
        self.folders: list[str] = []
        self._load()

    def _get_config_dir(self) -> Path:
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", ""))
        else:
            base = Path.home()
        return base / ".monovault"

    def _load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.folders = data.get("folders", [])
            except (json.JSONDecodeError, IOError):
                self.folders = []
        else:
            self.folders = []

    def save(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"folders": self.folders}, f, indent=2)

    def add_folder(self, path: str) -> bool:
        if path not in self.folders:
            self.folders.append(path)
            self.save()
            return True
        return False

    def remove_folder(self, path: str) -> bool:
        if path in self.folders:
            self.folders.remove(path)
            self.save()
            return True
        return False

    def get_folders(self) -> list[str]:
        return list(self.folders)
