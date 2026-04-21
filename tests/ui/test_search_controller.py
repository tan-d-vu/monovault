from unittest.mock import MagicMock

import pytest

from src.models.track import Track
from src.ui.controllers.search_controller import SearchController


@pytest.mark.unit
class TestSearchController:
    def test_search_immediate_with_query(self, qapp):
        repo = MagicMock()
        repo.search.return_value = ["track1"]

        ctrl = SearchController(repo, debounce_ms=0)
        ctrl.search_immediate("test")
        repo.search.assert_called_once_with("test")

    def test_search_immediate_empty_returns_all(self, qapp):
        repo = MagicMock()
        repo.get_all_tracks.return_value = ["all"]

        ctrl = SearchController(repo, debounce_ms=0)
        ctrl.search_immediate("")
        repo.get_all_tracks.assert_called_once()

    def test_search_strips_whitespace(self, qapp):
        repo = MagicMock()
        repo.get_all_tracks.return_value = []

        ctrl = SearchController(repo, debounce_ms=0)

        ctrl.search_immediate("   ")
        repo.get_all_tracks.assert_called_once()

    def test_on_text_changed_starts_timer(self, qapp):
        repo = MagicMock()
        repo.get_all_tracks.return_value = []

        ctrl = SearchController(repo, debounce_ms=100)

        ctrl.on_text_changed("test")

        assert ctrl._timer.isActive()

    def test_on_text_changed_strips_whitespace(self, qapp):
        repo = MagicMock()
        repo.get_all_tracks.return_value = []

        ctrl = SearchController(repo, debounce_ms=0)

        ctrl.on_text_changed("  test  ")

        assert ctrl._pending_query == "test"

    def test_get_all_tracks_emits_results(self, qapp):
        repo = MagicMock()
        track = Track(
            id=1,
            file_path="/tmp/test.mp3",
            title="Test",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path="/tmp",
        )
        repo.get_all_tracks.return_value = [track]

        ctrl = SearchController(repo, debounce_ms=0)

        received = []
        ctrl.results_changed.connect(lambda r: received.extend(r))

        ctrl.get_all_tracks()

        assert len(received) == 1

    def test_search_with_no_matching_results(self, qapp):
        repo = MagicMock()
        repo.search.return_value = []

        ctrl = SearchController(repo, debounce_ms=0)

        results = ctrl.search_immediate("nonexistent")

        assert results == []

    def test_search_immediate_emits_results_changed_signal(self, qapp):
        repo = MagicMock()
        track = Track(
            id=1,
            file_path="/tmp/test.mp3",
            title="Test",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path="/tmp",
        )
        repo.search.return_value = [track]

        ctrl = SearchController(repo, debounce_ms=0)

        received = []
        ctrl.results_changed.connect(lambda r: received.extend(r))

        ctrl.search_immediate("test")

        assert len(received) == 1
        assert received[0].title == "Test"
