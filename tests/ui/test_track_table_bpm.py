import pytest
from PyQt6.QtWidgets import QTableWidget

from src.models.track import Track
from src.ui.track_table import COLUMN_SPECS, TrackTableColumn, TrackTableManager


@pytest.fixture
def manager(qapp):
    table = QTableWidget()
    return TrackTableManager(table)


def _make_track(bpm: float | None = None) -> Track:
    return Track(
        id=1,
        file_path="/music/test.flac",
        title="Test",
        artist="Artist",
        album="Album",
        duration=180.0,
        categories=[],
        album_art=None,
        folder_path="/music",
        bpm=bpm,
    )


@pytest.mark.unit
def test_column_count(manager):
    assert manager._table.columnCount() == len(COLUMN_SPECS)


@pytest.mark.unit
def test_bpm_cell_renders_integer(manager):
    track = _make_track(bpm=128.7)
    manager.populate([track])
    item = manager._table.item(0, TrackTableColumn.BPM)
    assert item is not None
    assert item.text() == "129"  # int(round(128.7)) = 129


@pytest.mark.unit
def test_bpm_cell_renders_empty_for_none(manager):
    track = _make_track(bpm=None)
    manager.populate([track])
    item = manager._table.item(0, TrackTableColumn.BPM)
    assert item is not None
    assert item.text() == ""


@pytest.mark.unit
def test_update_bpm_patches_only_bpm_cell(manager):
    track = _make_track(bpm=None)
    manager.populate([track])
    result = manager.update_bpm(track.id, 140.0)
    assert result is True
    item = manager._table.item(0, TrackTableColumn.BPM)
    assert item is not None
    assert item.text() == "140"


@pytest.mark.unit
def test_update_bpm_returns_false_for_unknown_id(manager):
    assert manager.update_bpm(999, 128.0) is False
