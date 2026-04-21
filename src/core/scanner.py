import os
from pathlib import Path

from ..models.track import Track
from .library_store import LibraryStore
from .metadata import is_supported, read_comment, read_comment_raw, read_metadata


class Scanner:
    def __init__(self):
        self.progress_callback: callable | None = None

    def scan_folder(self, folder_path: str) -> list[Track]:
        """Scan folder for audio files and create per-folder LibraryStore.

        Args:
            folder_path: Absolute path to folder to scan

        Returns:
            List of Track objects found in folder
        """
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return []

        # Create per-folder store for this folder
        store = LibraryStore(base_dir=folder)

        audio_files = self._find_audio_files(folder)
        tracks = []

        for i, file_path in enumerate(audio_files):
            track = self.process_file(file_path, folder_path, store)
            if track:
                tracks.append(track)

            if self.progress_callback:
                self.progress_callback(i + 1, len(audio_files))

        store.save()
        return tracks

    def _find_audio_files(self, folder: Path) -> list[str]:
        """Find all supported audio files in folder recursively."""
        audio_files = []
        for root, _dirs, files in os.walk(folder):
            for filename in files:
                file_path = os.path.join(root, filename)
                if is_supported(file_path):
                    audio_files.append(file_path)
        return audio_files

    def process_file(
        self,
        file_path: str,
        folder_path: str,
        store: LibraryStore | None = None,
    ) -> Track | None:
        """Process a single audio file.

        Args:
            file_path: Absolute path to file
            folder_path: Absolute path to containing folder
            store: Optional LibraryStore for recording date_added

        Returns:
            Track object, or None if metadata cannot be read
        """
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

        date_added = store.record_if_new(file_path) if store else ""

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
