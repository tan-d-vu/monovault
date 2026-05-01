"""Delete controller — moves tracks to per-folder trash and restores them.

Trash is one-folder-at-a-time on disk (each watched folder has its own
`.monovault/trash/`), but the controller exposes a single library-wide API:
delete a list of tracks regardless of folder, list/restore/purge across all
folders. It groups by `folder_path` internally and reuses a TrashManager
instance per folder.

File ops are synchronous: same-volume moves are essentially instant. If we
ever need to handle cross-volume music libraries, swap `_with_trash_manager`
to dispatch onto a QThreadPool without changing the signal contract.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtSignal

from ...core.library import LibraryManager
from ...core.library_store import LibraryStore
from ...core.playback import PlaybackEngine
from ...core.scanner import Scanner
from ...core.trash import TrashEntry, TrashManager
from ...models.track import Track

logger = logging.getLogger(__name__)


class DeleteController(QObject):
    """Move tracks to trash, restore from trash, purge."""

    delete_completed = pyqtSignal(int)
    delete_failed = pyqtSignal(str, int)
    restore_completed = pyqtSignal(list)
    restore_failed = pyqtSignal(str)
    trash_changed = pyqtSignal()

    def __init__(
        self,
        library: LibraryManager,
        playback: PlaybackEngine,
        scanner: Scanner,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._library = library
        self._playback = playback
        self._scanner = scanner
        self._trash_managers: dict[str, TrashManager] = {}

    def delete_tracks(self, tracks: list[Track]) -> None:
        """Move tracks to per-folder trash and remove them from the library.

        Stops playback if any of the tracks is the currently-playing one
        (and clears QMediaPlayer's source so Windows file handles are
        released before the move).
        """
        if not tracks:
            self.delete_completed.emit(0)
            return

        self._release_playback_if_holding(tracks)

        moved_count = 0
        first_error: str | None = None
        for folder_path, folder_tracks in self._group_by_folder(tracks).items():
            trash = self._trash_manager_for(folder_path)
            store = LibraryStore(Path(folder_path))
            for track in folder_tracks:
                try:
                    trash.move_to_trash(track)
                except (OSError, ValueError) as exc:
                    logger.warning("Failed to trash %s: %s", track.file_path, exc)
                    if first_error is None:
                        first_error = str(exc)
                    continue
                store.remove(track.file_path)
                self._library.delete_tracks([track.id])
                moved_count += 1

        if first_error is None:
            self.delete_completed.emit(moved_count)
        else:
            self.delete_failed.emit(first_error, moved_count)
        self.trash_changed.emit()

    def restore(self, entries: list[tuple[str, TrashEntry]]) -> None:
        """Restore trashed entries back into their original folders.

        `entries` is a list of (folder_path, TrashEntry) pairs because trash
        is per-folder and the TrashEntry alone doesn't know its folder.
        """
        if not entries:
            self.restore_completed.emit([])
            return

        restored_tracks: list[Track] = []
        first_error: str | None = None
        for folder_path, entry in entries:
            try:
                track = self._restore_one(folder_path, entry)
            except (OSError, KeyError, FileNotFoundError) as exc:
                logger.warning("Failed to restore %s: %s", entry.original_relpath, exc)
                if first_error is None:
                    first_error = str(exc)
                continue
            if track is not None:
                restored_tracks.append(track)

        if first_error is not None:
            self.restore_failed.emit(first_error)
        self.restore_completed.emit(restored_tracks)
        self.trash_changed.emit()

    def list_all_trash(self) -> list[tuple[str, TrashEntry]]:
        """All trash entries across watched folders, paired with folder paths."""
        result: list[tuple[str, TrashEntry]] = []
        for folder_path in self._library.get_folders():
            trash = self._trash_manager_for(folder_path)
            for entry in trash.list_entries():
                result.append((folder_path, entry))
        return result

    def purge(self, entries: list[tuple[str, TrashEntry]]) -> None:
        for folder_path, entry in entries:
            trash = self._trash_manager_for(folder_path)
            trash.purge(entry.trash_id)
        self.trash_changed.emit()

    def empty_trash(self) -> None:
        self.purge(self.list_all_trash())

    def is_folder_watched(self, folder_path: str) -> bool:
        return folder_path in self._library.get_folders()

    def _restore_one(self, folder_path: str, entry: TrashEntry) -> Track | None:
        trash = self._trash_manager_for(folder_path)
        restored_path = trash.restore(entry.trash_id)

        store = LibraryStore(Path(folder_path))
        track = self._scanner.process_file(str(restored_path), folder_path, store=None)
        if track is None:
            return None

        store.set(str(restored_path), entry.date_added)
        track.date_added = entry.date_added
        self._library.add_track(track)
        return track

    def _release_playback_if_holding(self, tracks: list[Track]) -> None:
        current = self._playback.current_track()
        if current is None:
            return
        if any(t.file_path == current for t in tracks):
            self._playback.stop()
            self._playback.player.setSource(QUrl())

    def _group_by_folder(self, tracks: list[Track]) -> dict[str, list[Track]]:
        grouped: dict[str, list[Track]] = defaultdict(list)
        for track in tracks:
            grouped[track.folder_path].append(track)
        return grouped

    def _trash_manager_for(self, folder_path: str) -> TrashManager:
        manager = self._trash_managers.get(folder_path)
        if manager is None:
            manager = TrashManager(Path(folder_path))
            self._trash_managers[folder_path] = manager
        return manager
