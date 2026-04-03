"""Tests for LibraryManager — ITrackRepository conformance and behavior."""

import pytest

from src.core.interfaces import ITrackRepository
from src.core.library import LibraryManager
from src.models.track import Track


def make_track(
    track_id: int = 1,
    file_path: str = "/tmp/song.mp3",
    title: str = "Test Song",
    artist: str = "Test Artist",
    album: str = "Test Album",
    categories: list[str] | None = None,
) -> Track:
    return Track(
        id=track_id,
        file_path=file_path,
        title=title,
        artist=artist,
        album=album,
        duration=180.0,
        categories=categories if categories is not None else ["rock"],
        album_art=None,
        folder_path="/tmp",
        comments="",
        date_added="2025-01-01",
    )


@pytest.fixture
def library() -> LibraryManager:
    return LibraryManager()


class TestLibraryManager:
    # ------------------------------------------------------------------
    # Protocol conformance
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_conforms_to_itrackrepo_protocol(self, library: LibraryManager) -> None:
        """LibraryManager must satisfy ITrackRepository structurally."""
        repo: ITrackRepository = library  # type: ignore[assignment]
        assert repo is library

    # ------------------------------------------------------------------
    # add_track
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_add_track_returns_positive_int(self, library: LibraryManager, sample_track: Track) -> None:
        track_id = library.add_track(sample_track)
        assert isinstance(track_id, int)
        assert track_id > 0

    @pytest.mark.unit
    def test_add_track_deduplicates_by_file_path(self, library: LibraryManager, sample_track: Track) -> None:
        """Adding a track with the same file_path updates in place, no duplicate."""
        first_id = library.add_track(sample_track)

        updated = make_track(track_id=99, file_path=sample_track.file_path, title="Updated Title")
        second_id = library.add_track(updated)

        assert second_id == first_id
        assert len(library.get_all_tracks()) == 1
        assert library.get_track_by_id(first_id).title == "Updated Title"  # type: ignore[union-attr]

    @pytest.mark.unit
    def test_add_multiple_tracks_get_distinct_ids(self, library: LibraryManager) -> None:
        id1 = library.add_track(make_track(file_path="/tmp/a.mp3"))
        id2 = library.add_track(make_track(file_path="/tmp/b.mp3"))
        assert id1 != id2
        assert len(library.get_all_tracks()) == 2

    # ------------------------------------------------------------------
    # get_track_by_id
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_get_track_by_id_found(self, library: LibraryManager, sample_track: Track) -> None:
        track_id = library.add_track(sample_track)
        result = library.get_track_by_id(track_id)
        assert result is not None
        assert result.file_path == sample_track.file_path

    @pytest.mark.unit
    def test_get_track_by_id_not_found(self, library: LibraryManager) -> None:
        assert library.get_track_by_id(9999) is None

    # ------------------------------------------------------------------
    # get_track_by_path
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_get_track_by_path_found(self, library: LibraryManager, sample_track: Track) -> None:
        library.add_track(sample_track)
        result = library.get_track_by_path(sample_track.file_path)
        assert result is not None
        assert result.title == sample_track.title

    @pytest.mark.unit
    def test_get_track_by_path_not_found(self, library: LibraryManager) -> None:
        assert library.get_track_by_path("/nonexistent/path.mp3") is None

    # ------------------------------------------------------------------
    # get_all_tracks
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_get_all_tracks_empty(self, library: LibraryManager) -> None:
        assert library.get_all_tracks() == []

    @pytest.mark.unit
    def test_get_all_tracks_with_multiple(self, library: LibraryManager, sample_tracks: list[Track]) -> None:
        for track in sample_tracks:
            library.add_track(track)
        all_tracks = library.get_all_tracks()
        assert len(all_tracks) == len(sample_tracks)

    # ------------------------------------------------------------------
    # update_track
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_update_track_changes_stored_track(self, library: LibraryManager, sample_track: Track) -> None:
        track_id = library.add_track(sample_track)
        stored = library.get_track_by_id(track_id)
        assert stored is not None

        modified = make_track(track_id=track_id, file_path=sample_track.file_path, title="New Title")
        modified.id = track_id
        library.update_track(modified)

        result = library.get_track_by_id(track_id)
        assert result is not None
        assert result.title == "New Title"

    @pytest.mark.unit
    def test_update_track_nonexistent_is_noop(self, library: LibraryManager) -> None:
        ghost = make_track(track_id=999, file_path="/ghost.mp3")
        ghost.id = 999
        # Should not raise
        library.update_track(ghost)
        assert library.get_track_by_id(999) is None

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_search_by_title(self, library: LibraryManager, sample_track: Track) -> None:
        library.add_track(sample_track)
        results = library.search("Test Song")
        assert len(results) == 1
        assert results[0].title == sample_track.title

    @pytest.mark.unit
    def test_search_by_artist(self, library: LibraryManager, sample_track: Track) -> None:
        library.add_track(sample_track)
        results = library.search("Test Artist")
        assert any(t.artist == "Test Artist" for t in results)

    @pytest.mark.unit
    def test_search_by_category(self, library: LibraryManager, sample_track: Track) -> None:
        library.add_track(sample_track)
        results = library.search("rock")
        assert len(results) >= 1

    @pytest.mark.unit
    def test_search_case_insensitive(self, library: LibraryManager, sample_track: Track) -> None:
        library.add_track(sample_track)
        results = library.search("TEST SONG")
        assert len(results) == 1

    @pytest.mark.unit
    def test_search_no_results(self, library: LibraryManager, sample_track: Track) -> None:
        library.add_track(sample_track)
        results = library.search("zzznomatch999")
        assert results == []

    # ------------------------------------------------------------------
    # get_tracks_by_artist
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_get_tracks_by_artist_found(self, library: LibraryManager, sample_track: Track) -> None:
        library.add_track(sample_track)
        results = library.get_tracks_by_artist("Test Artist")
        assert len(results) == 1

    @pytest.mark.unit
    def test_get_tracks_by_artist_case_insensitive(self, library: LibraryManager, sample_track: Track) -> None:
        library.add_track(sample_track)
        results = library.get_tracks_by_artist("test artist")
        assert len(results) == 1

    @pytest.mark.unit
    def test_get_tracks_by_artist_not_found(self, library: LibraryManager, sample_track: Track) -> None:
        library.add_track(sample_track)
        results = library.get_tracks_by_artist("Unknown Artist")
        assert results == []

    # ------------------------------------------------------------------
    # get_tracks_with_categories
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_get_tracks_with_categories_found(self, library: LibraryManager, sample_track: Track) -> None:
        library.add_track(sample_track)
        results = library.get_tracks_with_categories(["rock"])
        assert len(results) == 1

    @pytest.mark.unit
    def test_get_tracks_with_categories_any_match(
        self, library: LibraryManager, sample_track: Track, sample_track_no_categories: Track
    ) -> None:
        library.add_track(sample_track)          # has ["rock", "instrumental"]
        library.add_track(sample_track_no_categories)  # has []
        results = library.get_tracks_with_categories(["instrumental", "pop"])
        assert len(results) == 1
        assert results[0].file_path == sample_track.file_path

    @pytest.mark.unit
    def test_get_tracks_with_categories_case_insensitive(
        self, library: LibraryManager, sample_track: Track
    ) -> None:
        library.add_track(sample_track)
        results = library.get_tracks_with_categories(["ROCK"])
        assert len(results) == 1

    @pytest.mark.unit
    def test_get_tracks_with_categories_not_found(
        self, library: LibraryManager, sample_track: Track
    ) -> None:
        library.add_track(sample_track)
        results = library.get_tracks_with_categories(["classical"])
        assert results == []

    @pytest.mark.unit
    def test_get_tracks_with_categories_empty_input(
        self, library: LibraryManager, sample_track: Track
    ) -> None:
        library.add_track(sample_track)
        results = library.get_tracks_with_categories([])
        assert results == []
