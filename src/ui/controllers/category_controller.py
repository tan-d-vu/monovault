"""Category controller — manages category CRUD and suggestions for the selected track."""

import logging

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from ...core.categorizer import Categorizer
from ...core.events import EventBus
from ...core.metadata import read_comment
from ...models.track import Track
from ..workers.metadata_worker import MetadataWriteWorker

logger = logging.getLogger(__name__)


class CategoryController(QObject):
    """Category management for the currently selected track."""

    categories_changed = pyqtSignal(Track)
    suggestions_changed = pyqtSignal(list)
    track_details_changed = pyqtSignal(Track)
    write_failed = pyqtSignal(str, str)

    def __init__(
        self,
        categorizer: Categorizer,
        bus: EventBus | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._categorizer = categorizer
        self._bus = bus
        self._current_track: Track | None = None
        self._write_pool = QThreadPool(self)
        self._write_pool.setMaxThreadCount(1)

    @property
    def current_track(self) -> Track | None:
        return self._current_track

    def select_track(self, track: Track) -> None:
        self._current_track = track
        self.track_details_changed.emit(track)
        if self._bus:
            from ...core.events import TrackSelected

            self._bus.publish(TrackSelected(track=track))
        self.categories_changed.emit(track)
        self._refresh_suggestions()

    def add_category(self, category: str) -> bool:
        if not self._current_track:
            return False
        validated = self._categorizer.parse_add_category(self._current_track, category)
        if validated is None:
            return False

        new_categories = list(self._current_track.categories) + [validated]
        self._categorizer.apply_categories(self._current_track, new_categories)
        self.categories_changed.emit(self._current_track)
        if self._bus:
            from ...core.events import CategoriesChanged

            self._bus.publish(CategoriesChanged(track=self._current_track))
        self._refresh_suggestions()
        self._schedule_write(self._current_track.file_path, new_categories)
        return True

    def remove_category(self, category: str) -> bool:
        if not self._current_track:
            return False
        validated = self._categorizer.parse_remove_category(self._current_track, category)
        if validated is None:
            return False

        new_categories = [c for c in self._current_track.categories if c.lower() != validated]
        self._categorizer.apply_categories(self._current_track, new_categories)
        self.categories_changed.emit(self._current_track)
        if self._bus:
            from ...core.events import CategoriesChanged

            self._bus.publish(CategoriesChanged(track=self._current_track))
        self._refresh_suggestions()
        self._schedule_write(self._current_track.file_path, new_categories)
        return True

    def clear_categories(self) -> bool:
        if not self._current_track:
            return False

        self._categorizer.apply_categories(self._current_track, [])
        self.categories_changed.emit(self._current_track)
        if self._bus:
            from ...core.events import CategoriesChanged

            self._bus.publish(CategoriesChanged(track=self._current_track))
        self._refresh_suggestions()
        self._schedule_write(self._current_track.file_path, [])
        return True

    def clear_categories_bulk(self, tracks: list[Track]) -> int:
        """Clear categories from multiple tracks. Returns count of tracks modified."""
        tracks_with_categories = [t for t in tracks if t.categories]
        if not tracks_with_categories:
            return 0

        for track in tracks_with_categories:
            self._categorizer.apply_categories(track, [])
            self.categories_changed.emit(track)
            if self._bus:
                from ...core.events import CategoriesChanged

                self._bus.publish(CategoriesChanged(track=track))
            self._schedule_write(track.file_path, [])

        if self._current_track and self._current_track in tracks_with_categories:
            self._refresh_suggestions()

        return len(tracks_with_categories)

    def accept_suggestion(self, category: str) -> bool:
        return self.add_category(category)

    def _schedule_write(self, file_path: str, categories: list[str]) -> None:
        worker = MetadataWriteWorker(file_path, categories)
        worker.signals.finished.connect(self._on_write_finished)
        self._write_pool.start(worker)

    def _on_write_finished(self, file_path: str, success: bool, error_msg: str) -> None:
        if success:
            logger.debug("Successfully wrote metadata for %s", file_path)
            return
        msg = error_msg or "Unknown error"
        logger.warning("Failed to write metadata for %s: %s", file_path, msg)
        self._revert_from_disk(file_path)
        self.write_failed.emit(file_path, msg)

    def _revert_from_disk(self, file_path: str) -> None:
        track = self._find_track_by_path(file_path)
        if track is None:
            return
        ground_truth = read_comment(file_path)
        self._categorizer.apply_categories(track, ground_truth)
        self.categories_changed.emit(track)
        if self._bus:
            from ...core.events import CategoriesChanged

            self._bus.publish(CategoriesChanged(track=track))
        if track is self._current_track:
            self._refresh_suggestions()

    def _find_track_by_path(self, file_path: str) -> Track | None:
        if self._current_track and self._current_track.file_path == file_path:
            return self._current_track
        return None

    def shutdown(self) -> None:
        # Cancel pending-but-not-started workers, then drain running ones.
        # Clear first so in-flight signals from cancelled workers don't deliver
        # to a partially-torn-down controller.
        self._write_pool.clear()
        self._write_pool.waitForDone(5000)

    def _refresh_suggestions(self) -> None:
        if not self._current_track:
            self.suggestions_changed.emit([])
            if self._bus:
                from ...core.events import SuggestionsChanged

                self._bus.publish(SuggestionsChanged(suggestions=[]))
            return
        suggestions = self._categorizer.get_suggestions(self._current_track)
        self.suggestions_changed.emit(suggestions)
        if self._bus:
            from ...core.events import SuggestionsChanged

            self._bus.publish(SuggestionsChanged(suggestions=suggestions))
