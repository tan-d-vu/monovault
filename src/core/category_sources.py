"""Pluggable category suggestion sources implementing ICategorySource."""

import logging
from ..models.track import Track
from .interfaces import ITrackRepository

logger = logging.getLogger(__name__)


class ArtistCategorySource:
    """Suggests categories from other tracks by the same artist."""

    def __init__(self, repository: ITrackRepository) -> None:
        self._repo = repository

    def get_suggestions(
        self, track: Track, existing_categories: set[str], max_results: int = 5
    ) -> list[tuple[str, str]]:
        if not track.artist:
            return []
        suggestions: list[tuple[str, str]] = []
        same_artist = self._repo.get_tracks_by_artist(track.artist)
        for t in same_artist:
            if t.id == track.id:
                continue
            for cat in t.categories:
                cat_lower = cat.lower()
                if cat_lower not in existing_categories:
                    if not any(s[0] == cat_lower for s in suggestions):
                        suggestions.append((cat_lower, "same artist"))
                        if len(suggestions) >= max_results:
                            return suggestions
        return suggestions


class SimilarCategoryCategorySource:
    """Suggests categories from tracks sharing any category with the current track."""

    def __init__(self, repository: ITrackRepository) -> None:
        self._repo = repository

    def get_suggestions(
        self, track: Track, existing_categories: set[str], max_results: int = 5
    ) -> list[tuple[str, str]]:
        if not track.categories:
            return []
        suggestions: list[tuple[str, str]] = []
        similar = self._repo.get_tracks_with_categories(track.categories)
        for t in similar:
            if t.id == track.id:
                continue
            for cat in t.categories:
                cat_lower = cat.lower()
                if cat_lower not in existing_categories:
                    if not any(s[0] == cat_lower for s in suggestions):
                        suggestions.append((cat_lower, "similar category"))
                        if len(suggestions) >= max_results:
                            return suggestions
        return suggestions
