from datetime import date, timedelta

import pytest

from src.core.date_filter import DatePreset, apply_date_filter, cutoff_date
from src.models.track import Track


def _make_track(date_added: str, track_id: int = 1) -> Track:
    return Track(
        id=track_id,
        file_path=f"/tmp/t{track_id}.mp3",
        title="Track",
        artist="Artist",
        album="Album",
        duration=180.0,
        categories=[],
        album_art=None,
        folder_path="/tmp",
        date_added=date_added,
    )


def _on_cutoff(preset: DatePreset) -> Track:
    return _make_track(cutoff_date(preset).isoformat())


def _before_cutoff(preset: DatePreset) -> Track:
    return _make_track((cutoff_date(preset) - timedelta(days=1)).isoformat())


@pytest.mark.unit
class TestCutoffDate:
    def test_last_7_days_is_7_days_ago(self):
        assert cutoff_date(DatePreset.LAST_7_DAYS) == date.today() - timedelta(days=7)

    def test_last_30_days_is_30_days_ago(self):
        assert cutoff_date(DatePreset.LAST_30_DAYS) == date.today() - timedelta(days=30)

    def test_last_3_months_is_90_days_ago(self):
        assert cutoff_date(DatePreset.LAST_3_MONTHS) == date.today() - timedelta(days=90)

    def test_this_year_is_jan_1(self):
        assert cutoff_date(DatePreset.THIS_YEAR) == date(date.today().year, 1, 1)


@pytest.mark.unit
class TestApplyDateFilter:
    def test_none_preset_returns_all_tracks_unchanged(self):
        tracks = [_make_track("2020-01-01", 1), _make_track("2024-06-01", 2)]
        assert apply_date_filter(tracks, None) is tracks

    def test_track_on_cutoff_date_passes(self):
        for preset in DatePreset:
            track = _on_cutoff(preset)
            assert apply_date_filter([track], preset) == [track], f"failed for {preset}"

    def test_track_before_cutoff_is_excluded(self):
        for preset in DatePreset:
            track = _before_cutoff(preset)
            assert apply_date_filter([track], preset) == [], f"failed for {preset}"

    def test_last_7_days_boundary(self):
        on = _on_cutoff(DatePreset.LAST_7_DAYS)
        before = _before_cutoff(DatePreset.LAST_7_DAYS)
        result = apply_date_filter([on, before], DatePreset.LAST_7_DAYS)
        assert result == [on]

    def test_last_30_days_boundary(self):
        on = _on_cutoff(DatePreset.LAST_30_DAYS)
        before = _before_cutoff(DatePreset.LAST_30_DAYS)
        result = apply_date_filter([on, before], DatePreset.LAST_30_DAYS)
        assert result == [on]

    def test_last_3_months_boundary(self):
        on = _on_cutoff(DatePreset.LAST_3_MONTHS)
        before = _before_cutoff(DatePreset.LAST_3_MONTHS)
        result = apply_date_filter([on, before], DatePreset.LAST_3_MONTHS)
        assert result == [on]

    def test_this_year_boundary(self):
        on = _on_cutoff(DatePreset.THIS_YEAR)
        before = _before_cutoff(DatePreset.THIS_YEAR)
        result = apply_date_filter([on, before], DatePreset.THIS_YEAR)
        assert result == [on]
