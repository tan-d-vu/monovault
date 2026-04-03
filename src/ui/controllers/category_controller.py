"""Category controller — manages category CRUD and suggestions for the selected track."""

from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal

from ...core.categorizer import Categorizer
from ...models.track import Track


class CategoryController(QObject):
    """Category management for the currently selected track."""

    categories_changed = pyqtSignal(Track)
    suggestions_changed = pyqtSignal(list)
    track_details_changed = pyqtSignal(Track)

    def __init__(
        self,
        categorizer: Categorizer,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._categorizer = categorizer
        self._current_track: Optional[Track] = None

    @property
    def current_track(self) -> Optional[Track]:
        return self._current_track

    def select_track(self, track: Track) -> None:
        self._current_track = track
        self.track_details_changed.emit(track)
        self._refresh_suggestions()

    def add_category(self, category: str) -> bool:
        if not self._current_track:
            return False
        success = self._categorizer.add_category(self._current_track, category)
        if success:
            self.categories_changed.emit(self._current_track)
            self._refresh_suggestions()
        return success

    def remove_category(self, category: str) -> bool:
        if not self._current_track:
            return False
        success = self._categorizer.remove_category(self._current_track, category)
        if success:
            self.categories_changed.emit(self._current_track)
            self._refresh_suggestions()
        return success

    def accept_suggestion(self, category: str) -> bool:
        return self.add_category(category)

    def _refresh_suggestions(self) -> None:
        if not self._current_track:
            self.suggestions_changed.emit([])
            return
        suggestions = self._categorizer.get_suggestions(self._current_track)
        self.suggestions_changed.emit(suggestions)
