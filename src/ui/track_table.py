"""Track table components for the MusicVault UI."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol

from PyQt6.QtCore import QObject, QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
)

from ..core.date_filter import DatePreset
from ..models.track import Track


class TrackTableColumn(IntEnum):
    NUMBER = 0
    TITLE = 1
    ARTIST = 2
    DURATION = 3
    COMMENTS = 4
    LOCATION = 5
    DATE_ADDED = 6
    BPM = 7


class _NumericItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically instead of lexicographically."""

    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            return int(self.text()) < int(other.text())
        except ValueError:
            return super().__lt__(other)


@dataclass
class ColumnSpec:
    label: str
    resize_mode: QHeaderView.ResizeMode
    padding: int
    get_value: Callable[[Track, int], str]
    alignment: Qt.AlignmentFlag | None = None
    item_class: type[QTableWidgetItem] = QTableWidgetItem


COLUMN_SPECS: dict[TrackTableColumn, ColumnSpec] = {
    TrackTableColumn.NUMBER: ColumnSpec(
        label="#",
        resize_mode=QHeaderView.ResizeMode.Interactive,
        padding=8,
        get_value=lambda t, i: str(i + 1),
        alignment=Qt.AlignmentFlag.AlignCenter,
        item_class=_NumericItem,
    ),
    TrackTableColumn.TITLE: ColumnSpec(
        label="Title",
        resize_mode=QHeaderView.ResizeMode.Interactive,
        padding=4,
        get_value=lambda t, i: t.title,
    ),
    TrackTableColumn.ARTIST: ColumnSpec(
        label="Artist",
        resize_mode=QHeaderView.ResizeMode.Interactive,
        padding=4,
        get_value=lambda t, i: t.artist,
    ),
    TrackTableColumn.DURATION: ColumnSpec(
        label="Duration",
        resize_mode=QHeaderView.ResizeMode.Interactive,
        padding=4,
        get_value=lambda t, i: t.duration_formatted,
        alignment=Qt.AlignmentFlag.AlignCenter,
    ),
    TrackTableColumn.COMMENTS: ColumnSpec(
        label="Comments",
        resize_mode=QHeaderView.ResizeMode.Interactive,
        padding=4,
        get_value=lambda t, i: t.comments or "",
    ),
    TrackTableColumn.LOCATION: ColumnSpec(
        label="Location",
        resize_mode=QHeaderView.ResizeMode.Interactive,
        padding=30,
        get_value=lambda t, i: t.location,
    ),
    TrackTableColumn.DATE_ADDED: ColumnSpec(
        label="Date Added",
        resize_mode=QHeaderView.ResizeMode.Interactive,
        padding=30,
        get_value=lambda t, i: t.date_added or "",
        alignment=Qt.AlignmentFlag.AlignCenter,
    ),
    TrackTableColumn.BPM: ColumnSpec(
        label="~BPM",
        resize_mode=QHeaderView.ResizeMode.Interactive,
        padding=8,
        get_value=lambda t, i: str(round(t.bpm)) if t.bpm is not None else "",
        alignment=Qt.AlignmentFlag.AlignCenter,
        item_class=_NumericItem,
    ),
}

_HEADER_MIN_PADDING = 24


class ITrackTable(Protocol):
    def populate(self, tracks: list[Track]) -> None: ...
    def clear(self) -> None: ...


class TrackTableManager(QObject):
    date_filter_changed = pyqtSignal(object)  # DatePreset | None

    def __init__(self, table: QTableWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._table = table
        self._last_tracks: list[Track] = []
        self._sort_column: int | None = None
        self._sort_order: Qt.SortOrder | None = None
        self._row_by_track_id: dict[int, int] = {}
        self._active_date_preset: DatePreset | None = None
        self._setup_table()

    def _setup_table(self) -> None:
        self._table.setColumnCount(len(COLUMN_SPECS))
        self._table.setHorizontalHeaderLabels([spec.label for spec in COLUMN_SPECS.values()])
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
        self._header.setStretchLastSection(True)
        self._header.setSortIndicatorShown(True)
        self._header.setSectionsMovable(True)
        for col, spec in COLUMN_SPECS.items():
            self._header.setSectionResizeMode(col, spec.resize_mode)
        self._header.sectionClicked.connect(self._on_header_clicked)
        self._header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._header.customContextMenuRequested.connect(self._on_header_context_menu)

    def _on_header_clicked(self, col: int) -> None:
        header = self._header
        if self._sort_column != col:
            self._sort_column = col
            self._sort_order = Qt.SortOrder.AscendingOrder
            self._table.sortItems(col, Qt.SortOrder.AscendingOrder)
            header.setSortIndicator(col, Qt.SortOrder.AscendingOrder)
            self._rebuild_row_map()
        elif self._sort_order == Qt.SortOrder.AscendingOrder:
            self._sort_order = Qt.SortOrder.DescendingOrder
            self._table.sortItems(col, Qt.SortOrder.DescendingOrder)
            header.setSortIndicator(col, Qt.SortOrder.DescendingOrder)
            self._rebuild_row_map()
        else:
            self._sort_column = None
            self._sort_order = None
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            self._populate_rows(self._last_tracks)

    def populate(self, tracks: list[Track]) -> None:
        self._last_tracks = tracks
        self._sort_column = None
        self._sort_order = None
        self._row_by_track_id.clear()
        self._header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self._table.setRowCount(len(tracks))
        self._populate_rows(tracks)
        self._calculate_column_widths(tracks)

    def _populate_rows(self, tracks: list[Track]) -> None:
        for i, track in enumerate(tracks):
            self._set_row(i, track)
        self._rebuild_row_map()

    def _rebuild_row_map(self) -> None:
        self._row_by_track_id.clear()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, TrackTableColumn.NUMBER)
            if item is None:
                continue
            track = item.data(Qt.ItemDataRole.UserRole)
            if track is not None:
                self._row_by_track_id[track.id] = row

    def update_track(self, track: Track) -> bool:
        row = self._row_by_track_id.get(track.id)
        if row is None:
            return False
        comments_item = self._table.item(row, TrackTableColumn.COMMENTS)
        if comments_item is not None:
            comments_item.setText(" ".join(track.categories))
        for col in COLUMN_SPECS:
            item = self._table.item(row, col)
            if item is not None:
                item.setData(Qt.ItemDataRole.UserRole, track)
        return True

    def update_bpm(self, track_id: int, bpm: float | None) -> bool:
        row = self._row_by_track_id.get(track_id)
        if row is None:
            return False
        spec = COLUMN_SPECS[TrackTableColumn.BPM]
        text = str(round(bpm)) if bpm is not None else ""
        item = spec.item_class(text)
        if spec.alignment is not None:
            item.setTextAlignment(spec.alignment)
        num_item = self._table.item(row, TrackTableColumn.NUMBER)
        if num_item is not None:
            item.setData(Qt.ItemDataRole.UserRole, num_item.data(Qt.ItemDataRole.UserRole))
        self._table.setItem(row, TrackTableColumn.BPM, item)
        return True

    def _set_row(self, row: int, track: Track) -> None:
        for col, spec in COLUMN_SPECS.items():
            text = spec.get_value(track, row)
            item = spec.item_class(text)
            if spec.alignment is not None:
                item.setTextAlignment(spec.alignment)
            item.setData(Qt.ItemDataRole.UserRole, track)
            self._table.setItem(row, col, item)

    def _calculate_column_widths(self, tracks: list[Track]) -> None:
        header_fm = self._header.fontMetrics()
        content_fm = self._header.fontMetrics()

        for col, spec in COLUMN_SPECS.items():
            header_text_width = header_fm.boundingRect(spec.label).width()
            min_width = header_text_width + _HEADER_MIN_PADDING

            max_width = min_width
            for row in range(len(tracks)):
                item = self._table.item(row, col)
                if item:
                    content_width = content_fm.boundingRect(item.text()).width()
                    max_width = max(max_width, content_width + spec.padding)

            self._table.setColumnWidth(col, max_width)

    def _on_header_context_menu(self, pos: QPoint) -> None:
        logical_col = self._header.logicalIndexAt(pos)
        menu = QMenu()

        # Column visibility toggles
        for col in TrackTableColumn:
            spec = COLUMN_SPECS[col]
            action = menu.addAction(spec.label)
            action.setCheckable(True)
            action.setChecked(not self._header.isSectionHidden(col))
            action.triggered.connect(lambda checked, c=col: self._toggle_column(c, checked))

        # Date filter options when right-clicking the Date Added column
        if logical_col == TrackTableColumn.DATE_ADDED:
            menu.addSeparator()
            for preset in DatePreset:
                action = menu.addAction(preset.value)
                action.setCheckable(True)
                action.setChecked(self._active_date_preset == preset)
                action.triggered.connect(lambda checked, p=preset: self._set_date_preset(p))
            menu.addSeparator()
            clear_action = menu.addAction("Clear date filter")
            clear_action.setEnabled(self._active_date_preset is not None)
            clear_action.triggered.connect(lambda: self._set_date_preset(None))

        menu.exec(self._header.mapToGlobal(pos))

    def _toggle_column(self, col: int, show: bool) -> None:
        if show:
            self._header.showSection(col)
        else:
            self._header.hideSection(col)

    def _set_date_preset(self, preset: DatePreset | None) -> None:
        self._active_date_preset = preset
        self.date_filter_changed.emit(preset)

    def clear(self) -> None:
        self._table.setRowCount(0)
        self._row_by_track_id.clear()
