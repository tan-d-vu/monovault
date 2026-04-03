"""Category management — add/remove categories, delegate suggestions to sources."""

import logging
from typing import Optional
from ..models.track import Track
from .interfaces import ITrackRepository, ICategorySource
from .metadata import write_comment

logger = logging.getLogger(__name__)


class Categorizer:
    def __init__(
        self,
        library: ITrackRepository,
        sources: Optional[list] = None,
    ) -> None:
        self._library = library
        self._sources: list[ICategorySource] = sources or []

    def get_suggestions(
        self, track: Track, max_suggestions: int = 5
    ) -> list[tuple[str, str]]:
        if not track:
            return []
        existing = {c.lower() for c in track.categories}
        all_suggestions: list[tuple[str, str]] = []
        seen: set[str] = set()
        for source in self._sources:
            for cat, label in source.get_suggestions(track, existing, max_suggestions):
                if cat not in seen:
                    seen.add(cat)
                    all_suggestions.append((cat, label))
                    if len(all_suggestions) >= max_suggestions:
                        return all_suggestions
        return all_suggestions

    def add_category(self, track: Track, category: str) -> bool:
        """Add a category to the track and persist to file metadata."""
        category = category.strip().lower()
        if not category or category in [c.lower() for c in track.categories]:
            return False

        new_categories = track.categories + [category]
        success = write_comment(track.file_path, new_categories)

        if success:
            track.categories = new_categories
            self._library.update_track(track)

        return success

    def remove_category(self, track: Track, category: str) -> bool:
        """Remove a category from the track and persist to file metadata."""
        category_lower = category.lower()
        if category_lower not in [c.lower() for c in track.categories]:
            return False

        new_categories = [c for c in track.categories if c.lower() != category_lower]
        success = write_comment(track.file_path, new_categories)

        if success:
            track.categories = new_categories
            self._library.update_track(track)

        return success

    def clear_categories(self, track: Track) -> bool:
        success = write_comment(track.file_path, [])

        if success:
            track.categories = []
            self._library.update_track(track)

        return success
