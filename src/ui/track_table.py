"""Track table components for the MusicVault UI."""

from enum import IntEnum
from typing import Protocol

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

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

# Extra padding for header text minimum (accounts for sort indicator arrow)
_HEADER_MIN_PADDING = 24


class _NumericItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically instead of lexicographically."""

    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            return int(self.text()) < int(other.text())
        except ValueError:
            return super().__lt__(other)


class ITrackTable(Protocol):
    def populate(self, tracks: list[Track]) -> None: ...
    def clear(self) -> None: ...


class TrackTableManager:
    def __init__(self, table: QTableWidget) -> None:
        self._table = table
        self._last_tracks: list[Track] = []
        self._sort_column: int | None = None
        self._sort_order: Qt.SortOrder | None = None
        self._setup_table()

    def _setup_table(self) -> None:
        self._table.setColumnCount(TrackTableColumn.COUNT)
        self._table.setHorizontalHeaderLabels(_COLUMN_LABELS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)
        vertical_header = self._table.verticalHeader()
        if vertical_header is not None:
            vertical_header.hide()

        header = self._table.horizontalHeader()
        assert header is not None
        self._header: QHeaderView = header
        self._header.setStretchLastSection(False)
        self._header.setSortIndicatorShown(True)
        for col, mode in _COLUMN_RESIZE_MODES.items():
            self._header.setSectionResizeMode(col, mode)
        self._header.sectionClicked.connect(self._on_header_clicked)

    def _on_header_clicked(self, col: int) -> None:
        header = self._header
        if self._sort_column != col:
            # New column: sort ascending
            self._sort_column = col
            self._sort_order = Qt.SortOrder.AscendingOrder
            self._table.sortItems(col, Qt.SortOrder.AscendingOrder)
            header.setSortIndicator(col, Qt.SortOrder.AscendingOrder)
        elif self._sort_order == Qt.SortOrder.AscendingOrder:
            # Same column, ascending → descending
            self._sort_order = Qt.SortOrder.DescendingOrder
            self._table.sortItems(col, Qt.SortOrder.DescendingOrder)
            header.setSortIndicator(col, Qt.SortOrder.DescendingOrder)
        else:
            # Same column, descending → clear sort, restore original order
            self._sort_column = None
            self._sort_order = None
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            self._populate_rows(self._last_tracks)

    def populate(self, tracks: list[Track]) -> None:
        self._last_tracks = tracks
        self._sort_column = None
        self._sort_order = None
        self._header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self._table.setRowCount(len(tracks))
        self._populate_rows(tracks)
        self._calculate_column_widths(tracks)

    def _populate_rows(self, tracks: list[Track]) -> None:
        for i, track in enumerate(tracks):
            self._set_row(i, track)

    def _set_row(self, row: int, track: Track) -> None:
        num_item = _NumericItem(str(row + 1))
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, TrackTableColumn.NUMBER, num_item)

        self._table.setItem(row, TrackTableColumn.TITLE, QTableWidgetItem(track.title))
        self._table.setItem(row, TrackTableColumn.ARTIST, QTableWidgetItem(track.artist))

        dur_item = QTableWidgetItem(track.duration_formatted)
        dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, TrackTableColumn.DURATION, dur_item)

        self._table.setItem(row, TrackTableColumn.COMMENTS, QTableWidgetItem(track.comments or ""))
        self._table.setItem(row, TrackTableColumn.LOCATION, QTableWidgetItem(track.location))

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
        header_fm = self._header.fontMetrics()
        content_fm = self._header.fontMetrics()

        for col in TrackTableColumn:
            if col in (TrackTableColumn.COMMENTS, TrackTableColumn.COUNT):
                continue

            header_text_width = header_fm.boundingRect(_COLUMN_LABELS[col]).width()
            min_width = header_text_width + _HEADER_MIN_PADDING

            max_width = min_width
            for row in range(len(tracks)):
                item = self._table.item(row, col)
                if item:
                    content_width = content_fm.boundingRect(item.text()).width()
                    max_width = max(max_width, content_width + _PADDING_MAP[col])

            self._table.setColumnWidth(col, max_width)

    def clear(self) -> None:
        self._table.setRowCount(0)
