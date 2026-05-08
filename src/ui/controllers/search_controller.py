"""Search controller — debounced search with result set management."""

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ...core.date_filter import DatePreset, apply_date_filter
from ...core.events import EventBus
from ...core.interfaces import ITrackRepository
from ...core.query_parser import evaluate, parse
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
        self._date_preset: DatePreset | None = None

    def on_text_changed(self, text: str) -> None:
        self._pending_query = text.strip()
        self._timer.start(self._debounce_ms)

    def search_immediate(self, query: str) -> list[Track]:
        self._timer.stop()
        self._pending_query = query.strip()
        return self._apply_filters()

    def get_all_tracks(self) -> list[Track]:
        tracks = apply_date_filter(self._repo.get_all_tracks(), self._date_preset)
        self.results_changed.emit(tracks)
        return tracks

    def set_date_filter(self, preset: DatePreset | None) -> None:
        self._date_preset = preset
        self._apply_filters()

    def _apply_filters(self) -> list[Track]:
        node = parse(self._pending_query)
        tracks = self._repo.get_all_tracks()
        if node is not None:
            tracks = [t for t in tracks if evaluate(node, t)]
        tracks = apply_date_filter(tracks, self._date_preset)
        self.results_changed.emit(tracks)
        return tracks

    def _execute_search(self) -> None:
        results = self._apply_filters()
        if self._bus:
            from ...core.events import SearchResultsChanged

            self._bus.publish(SearchResultsChanged(tracks=results, query=self._pending_query))
