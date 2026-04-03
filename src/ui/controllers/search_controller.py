"""Search controller — debounced search with result set management."""

from typing import Optional
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ...core.events import EventBus
from ...core.interfaces import ITrackRepository
from ...models.track import Track


class SearchController(QObject):
    """Manages search state. Emits results_changed when track list updates."""

    results_changed = pyqtSignal(list)

    def __init__(
        self,
        repository: ITrackRepository,
        bus: Optional[EventBus] = None,
        debounce_ms: int = 0,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repository
        self._bus = bus
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._execute_search)
        self._debounce_ms = debounce_ms
        self._pending_query: str = ""

    def on_text_changed(self, text: str) -> None:
        self._pending_query = text.strip()
        self._timer.start(self._debounce_ms)

    def search_immediate(self, query: str) -> list[Track]:
        self._timer.stop()
        q = query.strip()
        if q:
            results = self._repo.search(q)
        else:
            results = self._repo.get_all_tracks()
        self.results_changed.emit(results)
        return results

    def get_all_tracks(self) -> list[Track]:
        results = self._repo.get_all_tracks()
        self.results_changed.emit(results)
        return results

    def _execute_search(self) -> None:
        results = self.search_immediate(self._pending_query)
        if self._bus:
            from ...core.events import SearchResultsChanged

            self._bus.publish(
                SearchResultsChanged(tracks=results, query=self._pending_query)
            )
