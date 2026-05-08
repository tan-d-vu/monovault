from unittest.mock import MagicMock

import pytest

from src.models.track import Track
from src.ui.controllers.search_controller import SearchController


def _make_track(title="Test", artist="Artist", categories=None, track_id=1):
    return Track(
        id=track_id,
        file_path=f"/tmp/test{track_id}.mp3",
        title=title,
        artist=artist,
        album="Album",
        duration=180.0,
        categories=categories or [],
        album_art=None,
        folder_path="/tmp",
    )


@pytest.mark.unit
class TestSearchController:
    def test_search_immediate_with_query(self, qapp):
        matching = _make_track(title="test track", track_id=1)
        non_matching = _make_track(title="other", track_id=2)
        repo = MagicMock()
        repo.get_all_tracks.return_value = [matching, non_matching]

        ctrl = SearchController(repo, debounce_ms=0)
        results = ctrl.search_immediate("test")
        assert results == [matching]

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
        repo.get_all_tracks.return_value = [_make_track(title="Rock", track_id=1)]

        ctrl = SearchController(repo, debounce_ms=0)
        results = ctrl.search_immediate("nonexistent")
        assert results == []

    def test_search_immediate_emits_results_changed_signal(self, qapp):
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
        repo = MagicMock()
        repo.get_all_tracks.return_value = [track]

        ctrl = SearchController(repo, debounce_ms=0)
        received = []
        ctrl.results_changed.connect(lambda r: received.extend(r))
        ctrl.search_immediate("test")

        assert len(received) == 1
        assert received[0].title == "Test"


@pytest.mark.unit
class TestCategorySearchSyntax:
    def test_quoted_exact_match_returns_matching_tracks(self, qapp):
        rock = _make_track(title="Rock Song", categories=["rock"], track_id=1)
        jazz = _make_track(title="Jazz Song", categories=["jazz"], track_id=2)
        repo = MagicMock()
        repo.get_all_tracks.return_value = [rock, jazz]

        ctrl = SearchController(repo, debounce_ms=0)
        results = ctrl.search_immediate('category:"rock"')
        assert results == [rock]

    def test_quoted_exact_match_excludes_superstring_categories(self, qapp):
        track = _make_track(categories=["rockabilly"])
        repo = MagicMock()
        repo.get_all_tracks.return_value = [track]

        ctrl = SearchController(repo, debounce_ms=0)
        results = ctrl.search_immediate('category:"rock"')
        assert results == []

    def test_unquoted_substring_match_returns_partial_matches(self, qapp):
        rockabilly = _make_track(categories=["rockabilly"], track_id=1)
        jazz = _make_track(categories=["jazz"], track_id=2)
        repo = MagicMock()
        repo.get_all_tracks.return_value = [rockabilly, jazz]

        ctrl = SearchController(repo, debounce_ms=0)
        results = ctrl.search_immediate("category:rock")
        assert results == [rockabilly]

    def test_prefix_is_case_insensitive(self, qapp):
        track = _make_track(categories=["rock"])
        repo = MagicMock()
        repo.get_all_tracks.return_value = [track]

        ctrl = SearchController(repo, debounce_ms=0)
        results = ctrl.search_immediate('CATEGORY:"rock"')
        assert results == [track]

    def test_value_match_is_case_insensitive(self, qapp):
        track = _make_track(categories=["Rock"])
        repo = MagicMock()
        repo.get_all_tracks.return_value = [track]

        ctrl = SearchController(repo, debounce_ms=0)
        results = ctrl.search_immediate('category:"rock"')
        assert results == [track]

    def test_empty_quoted_value_returns_untagged_tracks(self, qapp):
        tagged = _make_track(categories=["rock"], track_id=1)
        untagged = _make_track(categories=[], track_id=2)
        repo = MagicMock()
        repo.get_all_tracks.return_value = [tagged, untagged]

        ctrl = SearchController(repo, debounce_ms=0)
        results = ctrl.search_immediate('category:""')
        assert results == [untagged]

    def test_category_query_does_not_call_repo_search(self, qapp):
        repo = MagicMock()
        repo.get_all_tracks.return_value = []

        ctrl = SearchController(repo, debounce_ms=0)
        ctrl.search_immediate('category:"rock"')
        repo.search.assert_not_called()

    def test_plain_search_does_not_call_repo_search(self, qapp):
        matching = _make_track(categories=["rock"], track_id=1)
        repo = MagicMock()
        repo.get_all_tracks.return_value = [matching]

        ctrl = SearchController(repo, debounce_ms=0)
        results = ctrl.search_immediate("rock")

        repo.search.assert_not_called()
        assert results == [matching]


@pytest.mark.unit
class TestBooleanSearch:
    def _repo(self, tracks):
        repo = MagicMock()
        repo.get_all_tracks.return_value = tracks
        return repo

    def test_spaces_act_as_and(self, qapp):
        match = _make_track(title="Rock Jazz", track_id=1)
        no_match = _make_track(title="Rock", track_id=2)
        ctrl = SearchController(self._repo([match, no_match]), debounce_ms=0)
        assert ctrl.search_immediate("rock jazz") == [match]

    def test_ampersand_and(self, qapp):
        match = _make_track(title="Rock Jazz", track_id=1)
        no_match = _make_track(title="Rock", track_id=2)
        ctrl = SearchController(self._repo([match, no_match]), debounce_ms=0)
        assert ctrl.search_immediate("rock && jazz") == [match]

    def test_pipe_or(self, qapp):
        rock = _make_track(title="Rock", track_id=1)
        jazz = _make_track(title="Jazz", track_id=2)
        other = _make_track(title="Other", track_id=3)
        ctrl = SearchController(self._repo([rock, jazz, other]), debounce_ms=0)
        assert ctrl.search_immediate("rock || jazz") == [rock, jazz]

    def test_and_or_precedence(self, qapp):
        # "solo || beta && gamma" → solo OR (beta AND gamma)
        track_solo = _make_track(title="solo", artist="nobody", track_id=1)
        track_bg = _make_track(title="beta gamma", artist="nobody", track_id=2)
        track_beta = _make_track(title="beta", artist="nobody", track_id=3)
        ctrl = SearchController(self._repo([track_solo, track_bg, track_beta]), debounce_ms=0)

        results = ctrl.search_immediate("solo || beta && gamma")
        assert track_solo in results
        assert track_bg in results
        assert track_beta not in results

    def test_category_and_plain_term(self, qapp):
        match = _make_track(title="Hello", categories=["rock"], track_id=1)
        no_cat = _make_track(title="Hello", categories=["jazz"], track_id=2)
        no_title = _make_track(title="Other", categories=["rock"], track_id=3)
        ctrl = SearchController(self._repo([match, no_cat, no_title]), debounce_ms=0)
        assert ctrl.search_immediate("category:rock && hello") == [match]

    def test_dangling_operator_ignored(self, qapp):
        track = _make_track(title="Rock", track_id=1)
        other = _make_track(title="Jazz", track_id=2)
        ctrl = SearchController(self._repo([track, other]), debounce_ms=0)
        assert ctrl.search_immediate("rock &&") == [track]
