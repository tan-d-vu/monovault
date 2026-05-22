"""Background QThread worker for BPM analysis."""

import logging

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from ...core.bpm_analyzer import analyze_bpm
from ...core.bpm_store import _MISSING, BpmStore
from ...models.track import Track

logger = logging.getLogger(__name__)


class BpmWorkerSignals(QObject):
    track_analyzed = pyqtSignal(int, object)  # track_id, float | None
    progress = pyqtSignal(int, int)           # done, total
    finished = pyqtSignal()


class BpmWorker(QThread):
    def __init__(
        self,
        tracks: list[Track],
        bpm_stores: dict[str, BpmStore],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._tracks = tracks
        self._bpm_stores = bpm_stores
        self._cancelled = False
        self.signals = BpmWorkerSignals()

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        uncached = [
            t for t in self._tracks
            if t.folder_path in self._bpm_stores
            and self._bpm_stores[t.folder_path].get(t.file_path) is _MISSING
        ]
        total = len(uncached)
        saved_stores: set[str] = set()

        for done, track in enumerate(uncached):
            if self._cancelled:
                break
            store = self._bpm_stores.get(track.folder_path)
            if store is None:
                continue
            bpm = analyze_bpm(track.file_path)
            store.set(track.file_path, bpm)
            saved_stores.add(track.folder_path)
            self.signals.track_analyzed.emit(track.id, bpm)
            self.signals.progress.emit(done + 1, total)

        if not self._cancelled:
            for folder_path in saved_stores:
                self._bpm_stores[folder_path].save()

        self.signals.finished.emit()
