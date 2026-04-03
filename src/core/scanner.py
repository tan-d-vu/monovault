from pathlib import Path
from typing import Optional
import os

from .metadata import is_supported, read_metadata, read_comment, read_comment_raw
from .library_store import LibraryStore
from ..models.track import Track


class Scanner:
    def __init__(self, library_store: Optional[LibraryStore] = None):
        self.progress_callback: Optional[callable] = None
        self._store = library_store

    def scan_folder(self, folder_path: str) -> list[Track]:
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return []

        audio_files = self._find_audio_files(folder)
        tracks = []

        for i, file_path in enumerate(audio_files):
            track = self.process_file(file_path, folder_path)
            if track:
                tracks.append(track)

            if self.progress_callback:
                self.progress_callback(i + 1, len(audio_files))

        return tracks

    def _find_audio_files(self, folder: Path) -> list[str]:
        audio_files = []
        for root, dirs, files in os.walk(folder):
            for filename in files:
                file_path = os.path.join(root, filename)
                if is_supported(file_path):
                    audio_files.append(file_path)
        return audio_files

    def process_file(self, file_path: str, folder_path: str) -> Optional[Track]:
        metadata = read_metadata(file_path)
        if not metadata:
            return None

        categories = read_comment(file_path)
        comments = read_comment_raw(file_path)

        title = metadata.get("title", "") or Path(file_path).stem
        artist = metadata.get("artist", "Unknown")
        album = metadata.get("album", "Unknown")
        duration = metadata.get("duration", 0.0)
        album_art = metadata.get("album_art")

        date_added = self._store.record_if_new(file_path) if self._store else ""

        return Track(
            id=0,
            file_path=file_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            categories=categories,
            album_art=album_art,
            folder_path=folder_path,
            comments=comments,
            date_added=date_added,
        )
