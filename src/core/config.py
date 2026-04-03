import json
import os
from datetime import datetime
from pathlib import Path


class Config:
    def __init__(self):
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / "config.json"
        self.folders: list[str] = []
        self.volumes: dict[
            str, dict
        ] = {}  # volume_id -> {"paths": [...], "created_at": "..."}
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
                    self.volumes = data.get("volumes", {})
            except (json.JSONDecodeError, IOError):
                self.folders = []
                self.volumes = {}
        else:
            self.folders = []
            self.volumes = {}

    def save(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "folders": self.folders,
                    "volumes": self.volumes,
                },
                f,
                indent=2,
            )

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

    def register_volume(self, volume_id: str, folder_path: str) -> None:
        """Register a volume with a folder path.

        If volume_id already exists, appends folder_path if not already present.
        Otherwise creates a new volume entry.

        Args:
            volume_id: Unique volume identifier
            folder_path: Absolute path to the folder on this volume
        """
        if volume_id not in self.volumes:
            self.volumes[volume_id] = {
                "paths": [folder_path],
                "created_at": datetime.now().isoformat(),
            }
        else:
            paths = self.volumes[volume_id].get("paths", [])
            if folder_path not in paths:
                paths.append(folder_path)
                self.volumes[volume_id]["paths"] = paths

        self.save()

    def get_volume_paths(self, volume_id: str) -> list[str]:
        """Get all folder paths for a volume.

        Args:
            volume_id: Unique volume identifier

        Returns:
            List of folder paths, or empty list if volume not found
        """
        if volume_id in self.volumes:
            return self.volumes[volume_id].get("paths", [])
        return []

    def update_volume_path(self, volume_id: str, old_path: str, new_path: str) -> None:
        """Update a volume's path in both volumes and folders.

        Replaces old_path with new_path in the volume entry and in the
        global folders list.

        Args:
            volume_id: Unique volume identifier
            old_path: The old folder path to replace
            new_path: The new folder path to use
        """
        # Update in volumes
        if volume_id in self.volumes:
            paths = self.volumes[volume_id].get("paths", [])
            if old_path in paths:
                idx = paths.index(old_path)
                paths[idx] = new_path
                self.volumes[volume_id]["paths"] = paths

        # Update in folders
        if old_path in self.folders:
            idx = self.folders.index(old_path)
            self.folders[idx] = new_path

        self.save()
