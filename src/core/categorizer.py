"""Category management — add/remove categories, delegate suggestions to sources."""

import logging

from ..models.track import Track
from .interfaces import ICategorySource, ITrackRepository

logger = logging.getLogger(__name__)


class Categorizer:
    def __init__(
        self,
        library: ITrackRepository,
        sources: list | None = None,
    ) -> None:
        self._library = library
        self._sources: list[ICategorySource] = sources or []

    def get_suggestions(self, track: Track, max_suggestions: int = 5) -> list[tuple[str, str]]:
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

    def parse_add_category(self, track: Track, category: str) -> str | None:
        """Normalize and validate a category for addition.

        Strips whitespace, lowercases, and rejects empty, multi-word, or
        duplicate values.
        """
        category = category.strip().lower()
        if not category:
            return None
        if any(c.isspace() for c in category):
            return None
        if category in [c.lower() for c in track.categories]:
            return None
        return category

    def parse_remove_category(self, track: Track, category: str) -> str | None:
        """Find the matching category to remove, case-insensitively.

        Returns the normalized (lowercased) category string if found, or None.
        """
        category_lower = category.lower()
        for c in track.categories:
            if c.lower() == category_lower:
                return category_lower
        return None

    def apply_categories(self, track: Track, categories: list[str]) -> None:
        """Overwrite the track's categories in-memory and update the library store."""
        track.categories = categories
        self._library.update_track(track)
