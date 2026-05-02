"""Search controller — debounced search with result set management."""

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
        bus: EventBus | None = None,
        debounce_ms: int = 0,
        parent: QObject | None = None,
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

            self._bus.publish(SearchResultsChanged(tracks=results, query=self._pending_query))

    def filter_by_category(self, category: str | None) -> None:
        """Emit results_changed with tracks matching `category` (case-insensitive),
        or with all untagged tracks if `category is None`.
        Cancels any pending debounced search.
        """
        self._timer.stop()
        all_tracks = self._repo.get_all_tracks()
        if category is None:
            results = [t for t in all_tracks if not t.categories]
        else:
            target = category.lower()
            results = [t for t in all_tracks if any(c.lower() == target for c in t.categories)]
        self._pending_query = ""
        self.results_changed.emit(results)
