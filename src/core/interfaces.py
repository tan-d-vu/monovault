"""Protocol interfaces for core abstractions.

These protocols define the contracts that concrete implementations must satisfy.
Code depending on core services should type-hint against these protocols, not
against concrete classes, to enable easy swapping and testing.
"""

from typing import Optional, Protocol

from ..models.track import Track


class IMetadataParser(Protocol):
    """Reads and writes metadata for a specific audio format."""

    def can_handle(self, file_path: str) -> bool:
        """Return True if this parser supports the given file."""
        ...

    def read_metadata(self, file_path: str) -> dict:
        """Read title, artist, album, duration, album_art from file.
        Returns empty dict on failure."""
        ...

    def read_comment(self, file_path: str) -> list[str]:
        """Read categories from the COMMENT tag as a list of strings."""
        ...

    def read_comment_raw(self, file_path: str) -> str:
        """Read the raw COMMENT tag string."""
        ...

    def write_comment(self, file_path: str, categories: list[str]) -> bool:
        """Write categories to the COMMENT tag. Returns True on success."""
        ...

    def write_comments(self, file_path: str, comments: str) -> bool:
        """Write raw comment string. Returns True on success."""
        ...

    def get_album_art(self, file_path: str) -> Optional[bytes]:
        """Extract album art bytes, or None."""
        ...


class ITrackRepository(Protocol):
    """Stores and queries Track objects."""

    def add_track(self, track: Track) -> int:
        """Add or update a track. Returns the track ID."""
        ...

    def update_track(self, track: Track) -> None:
        """Update an existing track in the store."""
        ...

    def get_all_tracks(self) -> list[Track]:
        """Return all tracks."""
        ...

    def get_track_by_id(self, track_id: int) -> Optional[Track]:
        """Return a track by ID, or None."""
        ...

    def get_track_by_path(self, file_path: str) -> Optional[Track]:
        """Return a track by file path, or None."""
        ...

    def search(self, query: str) -> list[Track]:
        """Full-text search across title, artist, album, categories."""
        ...

    def get_tracks_by_artist(self, artist: str) -> list[Track]:
        """Return all tracks by a given artist (case-insensitive)."""
        ...

    def get_tracks_with_categories(self, categories: list[str]) -> list[Track]:
        """Return tracks that have any of the given categories."""
        ...


class ICategorySource(Protocol):
    """Provides category suggestions for a track."""

    def get_suggestions(
        self, track: Track, existing_categories: set[str], max_results: int = 5
    ) -> list[tuple[str, str]]:
        """Return list of (category, source_label) tuples.
        Must exclude categories already in existing_categories."""
        ...
