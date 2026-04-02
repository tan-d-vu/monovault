from typing import Optional
from ..models.track import Track
from .metadata import write_comment


class Categorizer:
    def __init__(self, library):
        self.library = library

    def get_suggestions(
        self, track: Track, max_suggestions: int = 5
    ) -> list[tuple[str, str]]:
        if not track or not track.artist:
            return []

        suggestions = set()

        same_artist_tracks = self.library.get_tracks_by_artist(track.artist)
        for t in same_artist_tracks:
            if t.id != track.id:
                for cat in t.categories:
                    if cat.lower() not in [c.lower() for c in track.categories]:
                        suggestions.add(cat.lower())

        if track.categories:
            similar_tracks = self.library.get_tracks_with_categories(track.categories)
            for t in similar_tracks:
                if t.id != track.id:
                    for cat in t.categories:
                        if cat.lower() not in [c.lower() for c in track.categories]:
                            suggestions.add(cat.lower())

        existing_lower = {c.lower() for c in track.categories}
        filtered = [s for s in suggestions if s.lower() not in existing_lower]

        return [(s, self._get_source(s, track)) for s in filtered[:max_suggestions]]

    def _get_source(self, category: str, track: Track) -> str:
        same_artist = self.library.get_tracks_by_artist(track.artist)
        for t in same_artist:
            if t.id != track.id and category.lower() in [
                c.lower() for c in t.categories
            ]:
                return "same artist"

        if track.categories:
            similar = self.library.get_tracks_with_categories(track.categories)
            for t in similar:
                if t.id != track.id and category.lower() in [
                    c.lower() for c in t.categories
                ]:
                    return "similar category"

        return "library"

    def add_category(self, track: Track, category: str) -> bool:
        category = category.strip().lower()
        if not category or category in [c.lower() for c in track.categories]:
            return False

        new_categories = track.categories + [category]
        success = write_comment(track.file_path, new_categories)

        if success:
            track.categories = new_categories
            self.library.update_track(track)

        return success

    def remove_category(self, track: Track, category: str) -> bool:
        category_lower = category.lower()
        if category_lower not in [c.lower() for c in track.categories]:
            return False

        new_categories = [c for c in track.categories if c.lower() != category_lower]
        success = write_comment(track.file_path, new_categories)

        if success:
            track.categories = new_categories
            self.library.update_track(track)

        return success

    def clear_categories(self, track: Track) -> bool:
        success = write_comment(track.file_path, [])

        if success:
            track.categories = []
            self.library.update_track(track)

        return success
