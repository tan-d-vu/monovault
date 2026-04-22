"""Tests for TrackTableManager row-index map and update_track."""

import pytest
from PyQt6.QtWidgets import QTableWidget

from src.models.track import Track
from src.ui.track_table import TrackTableColumn, TrackTableManager


def _make_track(track_id: int, title: str, artist: str = "Artist") -> Track:
    return Track(
        id=track_id,
        file_path=f"/tmp/track_{track_id}.mp3",
        title=title,
        artist=artist,
        album="Album",
        duration=180.0,
        categories=[],
        album_art=None,
        folder_path="/tmp",
    )


@pytest.fixture
def five_tracks() -> list[Track]:
    return [
        _make_track(10, "Alpha", artist="Zeta"),
        _make_track(20, "Bravo", artist="Yankee"),
        _make_track(30, "Charlie", artist="Xray"),
        _make_track(40, "Delta", artist="Whiskey"),
        _make_track(50, "Echo", artist="Victor"),
    ]


@pytest.mark.unit
def test_populate_builds_row_map(qapp, five_tracks):
    table = QTableWidget()
    manager = TrackTableManager(table)

    manager.populate(five_tracks)

    assert len(manager._row_by_track_id) == 5
    for i, track in enumerate(five_tracks):
        assert manager._row_by_track_id[track.id] == i


@pytest.mark.unit
def test_update_track_updates_comments_cell(qapp, five_tracks):
    table = QTableWidget()
    manager = TrackTableManager(table)
    manager.populate(five_tracks)

    target = five_tracks[3]
    target.categories = ["rock", "instrumental"]

    assert manager.update_track(target) is True

    comments_item = table.item(3, TrackTableColumn.COMMENTS)
    assert comments_item is not None
    assert comments_item.text() == "rock instrumental"
    assert len(manager._row_by_track_id) == 5


@pytest.mark.unit
def test_update_track_unknown_id_returns_false(qapp, five_tracks):
    table = QTableWidget()
    manager = TrackTableManager(table)
    manager.populate(five_tracks)

    stranger = _make_track(999, "Unknown")

    assert manager.update_track(stranger) is False


@pytest.mark.unit
def test_update_track_after_sort_targets_new_row(qapp, five_tracks):
    table = QTableWidget()
    manager = TrackTableManager(table)
    manager.populate(five_tracks)

    # Sort by title descending so "Echo" (id=50) ends up in row 0 and
    # "Alpha" (id=10) ends up in row 4.
    manager._on_header_clicked(TrackTableColumn.TITLE)
    manager._on_header_clicked(TrackTableColumn.TITLE)

    alpha = five_tracks[0]
    alpha.categories = ["ambient"]

    assert manager.update_track(alpha) is True

    new_row = manager._row_by_track_id[alpha.id]
    assert new_row == 4
    comments_item = table.item(new_row, TrackTableColumn.COMMENTS)
    assert comments_item is not None
    assert comments_item.text() == "ambient"

    # Original row 0 now belongs to "Echo" and must not have been touched.
    echo_comments = table.item(0, TrackTableColumn.COMMENTS)
    assert echo_comments is not None
    assert echo_comments.text() == ""


@pytest.mark.unit
def test_update_track_refreshes_userrole_on_all_columns(qapp, five_tracks):
    table = QTableWidget()
    manager = TrackTableManager(table)
    manager.populate(five_tracks)

    target = five_tracks[2]
    target.categories = ["jazz"]
    manager.update_track(target)

    from PyQt6.QtCore import Qt

    for col in range(TrackTableColumn.COUNT):
        item = table.item(2, col)
        assert item is not None
        stored = item.data(Qt.ItemDataRole.UserRole)
        assert stored is target


@pytest.mark.unit
def test_clear_empties_row_map(qapp, five_tracks):
    table = QTableWidget()
    manager = TrackTableManager(table)
    manager.populate(five_tracks)

    manager.clear()

    assert manager._row_by_track_id == {}
