"""Tests for SearchController date filter integration."""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from src.core.date_filter import DatePreset
from src.models.track import Track
from src.ui.controllers.search_controller import SearchController


def _make_track(title="Track", date_added: str = "2020-01-01", track_id: int = 1) -> Track:
    return Track(
        id=track_id,
        file_path=f"/tmp/t{track_id}.mp3",
        title=title,
        artist="Artist",
        album="Album",
        duration=180.0,
        categories=[],
        album_art=None,
        folder_path="/tmp",
        date_added=date_added,
    )


def _today() -> str:
    return date.today().isoformat()


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


@pytest.mark.unit
class TestSearchControllerDateFilter:
    def test_set_date_filter_restricts_results(self, qapp):
        recent = _make_track(title="recent", date_added=_today(), track_id=1)
        old = _make_track(title="old", date_added="2000-01-01", track_id=2)
        repo = MagicMock()
        repo.get_all_tracks.return_value = [recent, old]
        ctrl = SearchController(repo)

        results = ctrl.search_immediate("")
        ctrl.set_date_filter(DatePreset.LAST_7_DAYS)

        emitted = []
        ctrl.results_changed.connect(emitted.append)
        ctrl.set_date_filter(DatePreset.LAST_7_DAYS)
        assert emitted[-1] == [recent]

    def test_date_filter_applies_on_top_of_boolean_search(self, qapp):
        recent_match = _make_track(title="jazz", date_added=_today(), track_id=1)
        recent_no_match = _make_track(title="rock", date_added=_today(), track_id=2)
        old_match = _make_track(title="jazz", date_added="2000-01-01", track_id=3)
        repo = MagicMock()
        repo.get_all_tracks.return_value = [recent_match, recent_no_match, old_match]
        ctrl = SearchController(repo)
        ctrl.set_date_filter(DatePreset.LAST_7_DAYS)

        results = ctrl.search_immediate("jazz")
        assert results == [recent_match]

    def test_set_date_filter_none_clears_filter(self, qapp):
        recent = _make_track(title="recent", date_added=_today(), track_id=1)
        old = _make_track(title="old", date_added="2000-01-01", track_id=2)
        repo = MagicMock()
        repo.get_all_tracks.return_value = [recent, old]
        ctrl = SearchController(repo)
        ctrl.set_date_filter(DatePreset.LAST_7_DAYS)

        results = ctrl.search_immediate("")
        assert results == [recent]

        ctrl.set_date_filter(None)
        results = ctrl.search_immediate("")
        assert results == [recent, old]

    def test_changing_date_filter_re_emits_results(self, qapp):
        recent = _make_track(title="recent", date_added=_today(), track_id=1)
        old = _make_track(title="old", date_added="2000-01-01", track_id=2)
        repo = MagicMock()
        repo.get_all_tracks.return_value = [recent, old]
        ctrl = SearchController(repo)

        emitted = []
        ctrl.results_changed.connect(emitted.append)
        ctrl.set_date_filter(DatePreset.LAST_7_DAYS)
        ctrl.set_date_filter(None)

        assert len(emitted) == 2
        assert emitted[0] == [recent]
        assert emitted[1] == [recent, old]
