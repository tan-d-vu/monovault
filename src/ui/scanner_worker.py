"""Background worker for scanning folders without blocking the UI thread.

The worker lives on a QThread; MainWindow owns the thread's lifecycle. The
underlying Scanner.scan_folder() remains a synchronous API (tests depend on
it); this worker reaches into the scanner's primitives to get per-file
progress and cancellation between files.
"""

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from ..core.library_store import LibraryStore
from ..core.scanner import Scanner
from ..models.track import Track

logger = logging.getLogger(__name__)


class ScannerWorker(QObject):
    """Scans folders sequentially and reports progress via signals.

    Emits one `folder_done(folder, tracks)` per folder (not per file) — this
    keeps bytes-heavy Track.album_art out of the signal hot path. All Qt UI
    updates must happen on the main thread; this worker only emits.
    """

    progress = pyqtSignal(int, int, str)
    folder_done = pyqtSignal(str, list)
    all_done = pyqtSignal()
    error = pyqtSignal(str, str)

    def __init__(self, scanner: Scanner) -> None:
        super().__init__()
        self._scanner = scanner
        self._folders: list[str] = []
        self._cancel = False

    def set_folders(self, folders: list[str]) -> None:
        """Queue folders for the next run(). Call from main thread before start()."""
        self._folders = list(folders)
        self._cancel = False

    def cancel(self) -> None:
        """Request cancellation. Checked between files."""
        self._cancel = True

    def run(self) -> None:
        """Entry point — invoked on the worker thread via QThread.started."""
        for folder in self._folders:
            if self._cancel:
                break
            try:
                tracks = self._scan_one(folder)
            except OSError as exc:
                logger.error("Scan failed for %s: %s", folder, exc)
                self.error.emit(folder, str(exc))
                continue
            except Exception as exc:
                # Broad catch intentional: a background worker must never crash silently.
                logger.error("Unexpected scan error for %s: %s", folder, exc)
                self.error.emit(folder, str(exc))
                continue

            if self._cancel:
                break
            self.folder_done.emit(folder, tracks)

        self.all_done.emit()

    def _scan_one(self, folder_path: str) -> list[Track]:
        """Scan a single folder, emitting per-file progress and honoring cancel."""
        from pathlib import Path

        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return []

        store = LibraryStore(base_dir=folder)
        audio_files = self._scanner._find_audio_files(folder)
        total = len(audio_files)
        tracks: list[Track] = []

        for index, file_path in enumerate(audio_files):
            if self._cancel:
                break
            track = self._scanner.process_file(file_path, folder_path, store)
            if track is not None:
                tracks.append(track)
            self.progress.emit(index + 1, total, file_path)

        store.save()
        return tracks
