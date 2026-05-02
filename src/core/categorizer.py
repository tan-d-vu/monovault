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

    def replace_categories_everywhere(
        self, sources: set[str], target: str | None
    ) -> list[Track]:
        """Replace each of `sources` (case-insensitive) with `target` on every track.

        rename: sources={"rock"}, target="metal"
        merge:  sources={"rock", "punk"}, target="metal"
        delete: sources={"rock"}, target=None
        """
        target_norm: str | None = None
        if target is not None:
            target_norm = target.strip().lower()
            if not target_norm:
                raise ValueError("target cannot be empty")
            if any(c.isspace() for c in target_norm):
                raise ValueError("target cannot contain whitespace")

        source_set = {s.strip().lower() for s in sources if s.strip()}
        if target_norm is not None:
            source_set.discard(target_norm)
        if not source_set:
            return []

        modified: list[Track] = []
        for track in self._library.get_all_tracks():
            lowered = [c.lower() for c in track.categories]
            if not any(s in lowered for s in source_set):
                continue
            new_cats: list[str] = []
            seen: set[str] = set()
            for c in track.categories:
                cl = c.lower()
                if cl in source_set:
                    if target_norm is None:
                        continue
                    replacement = target_norm
                else:
                    replacement = cl
                if replacement in seen:
                    continue
                seen.add(replacement)
                new_cats.append(replacement)
            track.categories = new_cats
            track.comments = " ".join(new_cats)
            self._library.update_track(track)
            modified.append(track)
        return modified
