"""Track table components for the MusicVault UI."""

from enum import IntEnum
from typing import Protocol

from PyQt6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt

from ..models.track import Track


class TrackTableColumn(IntEnum):
    NUMBER = 0
    TITLE = 1
    ARTIST = 2
    DURATION = 3
    COMMENTS = 4
    LOCATION = 5
    DATE_ADDED = 6
    COUNT = 7


_COLUMN_LABELS = [
    "#",
    "Title",
    "Artist",
    "Duration",
    "Comments",
    "Location",
    "Date Added",
]

_COLUMN_RESIZE_MODES: dict[TrackTableColumn, QHeaderView.ResizeMode] = {
    TrackTableColumn.NUMBER: QHeaderView.ResizeMode.ResizeToContents,
    TrackTableColumn.TITLE: QHeaderView.ResizeMode.ResizeToContents,
    TrackTableColumn.ARTIST: QHeaderView.ResizeMode.ResizeToContents,
    TrackTableColumn.DURATION: QHeaderView.ResizeMode.ResizeToContents,
    TrackTableColumn.COMMENTS: QHeaderView.ResizeMode.Stretch,
    TrackTableColumn.LOCATION: QHeaderView.ResizeMode.Fixed,
    TrackTableColumn.DATE_ADDED: QHeaderView.ResizeMode.Interactive,
}


_PADDING_MAP = {
    TrackTableColumn.NUMBER: 8,
    TrackTableColumn.TITLE: 4,
    TrackTableColumn.ARTIST: 4,
    TrackTableColumn.DURATION: 4,
    TrackTableColumn.COMMENTS: 4,
    TrackTableColumn.LOCATION: 30,
    TrackTableColumn.DATE_ADDED: 30,
}


class ITrackTable(Protocol):
    def populate(self, tracks: list[Track]) -> None: ...
    def clear(self) -> None: ...


class TrackTableManager:
    def __init__(self, table: QTableWidget) -> None:
        self._table = table
        self._setup_table()

    def _setup_table(self) -> None:
        self._table.setColumnCount(TrackTableColumn.COUNT)
        self._table.setHorizontalHeaderLabels(_COLUMN_LABELS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.verticalHeader().hide()

        header = self._table.horizontalHeader()
        for col, mode in _COLUMN_RESIZE_MODES.items():
            header.setSectionResizeMode(col, mode)

    def populate(self, tracks: list[Track]) -> None:
        self._table.setRowCount(len(tracks))
        self._populate_rows(tracks)
        self._calculate_column_widths(tracks)

    def _populate_rows(self, tracks: list[Track]) -> None:
        for i, track in enumerate(tracks):
            self._set_row(i, track)

    def _set_row(self, row: int, track: Track) -> None:
        num_item = QTableWidgetItem(str(row + 1))
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, TrackTableColumn.NUMBER, num_item)

        self._table.setItem(row, TrackTableColumn.TITLE, QTableWidgetItem(track.title))
        self._table.setItem(
            row, TrackTableColumn.ARTIST, QTableWidgetItem(track.artist)
        )

        dur_item = QTableWidgetItem(track.duration_formatted)
        dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, TrackTableColumn.DURATION, dur_item)

        self._table.setItem(
            row, TrackTableColumn.COMMENTS, QTableWidgetItem(track.comments or "")
        )
        self._table.setItem(
            row, TrackTableColumn.LOCATION, QTableWidgetItem(track.location)
        )

        added_item = QTableWidgetItem(track.date_added or "")
        added_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        added_item.setData(
            Qt.ItemDataRole.TextAlignmentRole,
            int(Qt.AlignmentFlag.AlignCenter) | int(Qt.AlignmentFlag.AlignVCenter),
        )
        self._table.setItem(row, TrackTableColumn.DATE_ADDED, added_item)

        for col in range(TrackTableColumn.COUNT):
            item = self._table.item(row, col)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, track)

    def _calculate_column_widths(self, tracks: list[Track]) -> None:
        for col in TrackTableColumn:
            if col == TrackTableColumn.COMMENTS:
                continue
            max_width = 0
            for row in range(len(tracks)):
                item = self._table.item(row, col)
                if item:
                    width = self._table.fontMetrics().boundingRect(item.text()).width()
                    max_width = max(max_width, width)
            if max_width > 0:
                self._table.setColumnWidth(col, max_width + _PADDING_MAP[col])

    def clear(self) -> None:
        self._table.setRowCount(0)
