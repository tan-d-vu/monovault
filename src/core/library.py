"""In-memory track store. Implements ITrackRepository."""

from ..models.track import Track
from .config import Config


class LibraryManager:
    def __init__(self):
        self.tracks: dict[int, Track] = {}
        self.next_id: int = 1
        self.config = Config()
        self.folders: list[str] = self.config.get_folders()

    def add_folder(self, path: str) -> bool:
        if self.config.add_folder(path):
            self.folders = self.config.get_folders()
            return True
        return False

    def remove_folder(self, path: str):
        if self.config.remove_folder(path):
            self.folders = self.config.get_folders()
            self.tracks = {tid: t for tid, t in self.tracks.items() if t.folder_path != path}

    def get_folders(self) -> list[str]:
        return list(self.folders)

    def add_track(self, track: Track) -> int:
        for existing_id, existing_track in self.tracks.items():
            if existing_track.file_path == track.file_path:
                track.id = existing_id
                self.tracks[existing_id] = track
                return existing_id

        track.id = self.next_id
        self.tracks[self.next_id] = track
        self.next_id += 1
        return track.id

    def update_track(self, track: Track) -> None:
        if track.id in self.tracks:
            self.tracks[track.id] = track

    def delete_tracks(self, track_ids: list[int]) -> list[Track]:
        """Remove tracks from the library and return the removed Track objects.

        Caller is responsible for any side effects (file moves, store updates).
        Unknown ids are silently skipped.
        """
        removed: list[Track] = []
        for track_id in track_ids:
            track = self.tracks.pop(track_id, None)
            if track is not None:
                removed.append(track)
        return removed

    def get_all_tracks(self) -> list[Track]:
        return list(self.tracks.values())

    def get_track_by_id(self, track_id: int) -> Track | None:
        return self.tracks.get(track_id)

    def get_track_by_path(self, file_path: str) -> Track | None:
        for track in self.tracks.values():
            if track.file_path == file_path:
                return track
        return None

    def search(self, query: str) -> list[Track]:
        q = query.lower()
        results = []
        for track in self.tracks.values():
            if (
                q in track.title.lower()
                or q in track.artist.lower()
                or q in track.album.lower()
                or any(q in cat.lower() for cat in track.categories)
            ):
                results.append(track)
        return results

    def get_tracks_by_artist(self, artist: str) -> list[Track]:
        return [t for t in self.tracks.values() if t.artist.lower() == artist.lower()]

    def get_tracks_with_categories(self, categories: list[str]) -> list[Track]:
        if not categories:
            return []
        results = []
        for track in self.tracks.values():
            for cat in categories:
                if cat.lower() in [c.lower() for c in track.categories]:
                    results.append(track)
                    break
        return results

    def clear(self):
        self.tracks.clear()
        self.next_id = 1
