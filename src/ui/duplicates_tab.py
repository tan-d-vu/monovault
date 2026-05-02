"""Duplicates tab — runs metadata duplicate detection and lists results.

Self-contained widget. The host (MainWindow) injects the LibraryManager
and a `confirm_delete` callable so this tab reuses the same trash flow
as the main track table without owning any controllers itself.
"""

from collections.abc import Callable

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.duplicates import find_duplicates
from ..core.library import LibraryManager
from ..models.track import Track

_COLUMN_LABELS = [
    "Group",
    "Title",
    "Artist",
    "Album",
    "Duration",
    "Comments",
    "Filename",
    "Location",
]
_GROUP_COL = 0
_COMMENTS_COL = 5


class _NumericItem(QTableWidgetItem):
    """Sorts numerically when the cell text is an int."""

    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            return int(self.text()) < int(other.text())
        except ValueError:
            return super().__lt__(other)


class DuplicatesTab(QWidget):
    track_selected = pyqtSignal(Track)

    def __init__(
        self,
        library: LibraryManager,
        confirm_delete: Callable[[list[Track]], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._library = library
        self._confirm_delete = confirm_delete
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        top_bar = QHBoxLayout()
        self._scan_btn = QPushButton("Find Duplicates")
        self._scan_btn.clicked.connect(self._on_scan_clicked)
        self._status_label = QLabel("Click Find Duplicates to scan.")
        top_bar.addWidget(self._scan_btn)
        top_bar.addSpacing(12)
        top_bar.addWidget(self._status_label, 1)
        layout.addLayout(top_bar)

        self._table = QTableWidget()
        self._table.setColumnCount(len(_COLUMN_LABELS))
        self._table.setHorizontalHeaderLabels(_COLUMN_LABELS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        vertical_header = self._table.verticalHeader()
        if vertical_header is not None:
            vertical_header.hide()
        header = self._table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.installEventFilter(self)
        layout.addWidget(self._table, 1)

    def invalidate(self) -> None:
        """Clear stale results — call when the library has been rescanned."""
        self._table.setRowCount(0)
        self._status_label.setText("Click Find Duplicates to scan.")

    def refresh_after_delete(self) -> None:
        """Drop rows whose tracks are no longer in the library; collapse single-track groups."""
        if self._table.rowCount() == 0:
            return
        surviving = [
            (group_id, track)
            for group_id, track in self._iter_rows()
            if self._library.get_track_by_id(track.id) is not None
        ]
        counts: dict[int, int] = {}
        for group_id, _ in surviving:
            counts[group_id] = counts.get(group_id, 0) + 1
        surviving = [(gid, t) for gid, t in surviving if counts[gid] > 1]
        self._populate_rows(surviving)
        self._update_status_from_rows(surviving)

    def _on_scan_clicked(self) -> None:
        tracks = self._library.get_all_tracks()
        if not tracks:
            self._table.setRowCount(0)
            self._status_label.setText("Library is empty.")
            return

        groups = find_duplicates(tracks)
        if not groups:
            self._table.setRowCount(0)
            self._status_label.setText("No duplicates found.")
            return

        rows: list[tuple[int, Track]] = []
        for group_id, group in enumerate(groups, start=1):
            for track in group.tracks:
                rows.append((group_id, track))
        self._populate_rows(rows)
        self._update_status_from_rows(rows)

    def _populate_rows(self, rows: list[tuple[int, Track]]) -> None:
        self._table.setUpdatesEnabled(False)
        try:
            self._table.setRowCount(len(rows))
            for row_index, (group_id, track) in enumerate(rows):
                self._set_row(row_index, group_id, track)
        finally:
            self._table.setUpdatesEnabled(True)

    def _set_row(self, row: int, group_id: int, track: Track) -> None:
        group_item = _NumericItem(str(group_id))
        group_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, _GROUP_COL, group_item)

        self._table.setItem(row, 1, QTableWidgetItem(track.title))
        self._table.setItem(row, 2, QTableWidgetItem(track.artist))
        self._table.setItem(row, 3, QTableWidgetItem(track.album))

        duration_item = QTableWidgetItem(track.duration_formatted)
        duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 4, duration_item)

        self._table.setItem(row, _COMMENTS_COL, QTableWidgetItem(track.comments or ""))
        self._table.setItem(row, 6, QTableWidgetItem(track.filename))
        self._table.setItem(row, 7, QTableWidgetItem(track.location))

        for col in range(self._table.columnCount()):
            item = self._table.item(row, col)
            if item is not None:
                item.setData(Qt.ItemDataRole.UserRole, track)

    def _iter_rows(self):
        for row in range(self._table.rowCount()):
            item = self._table.item(row, _GROUP_COL)
            if item is None:
                continue
            track = item.data(Qt.ItemDataRole.UserRole)
            if track is None:
                continue
            try:
                group_id = int(item.text())
            except ValueError:
                continue
            yield group_id, track

    def _update_status_from_rows(self, rows: list[tuple[int, Track]]) -> None:
        if not rows:
            self._status_label.setText("No duplicates remaining.")
            return
        group_count = len({group_id for group_id, _ in rows})
        track_count = len(rows)
        track_noun = "track" if track_count == 1 else "tracks"
        group_noun = "group" if group_count == 1 else "groups"
        self._status_label.setText(
            f"{group_count} {group_noun} · {track_count} {track_noun}"
        )

    def _on_selection_changed(self) -> None:
        items = self._table.selectedItems()
        if not items:
            return
        rows = sorted({item.row() for item in items})
        item = self._table.item(rows[0], _GROUP_COL)
        if item is None:
            return
        track = item.data(Qt.ItemDataRole.UserRole)
        if track is not None:
            self.track_selected.emit(track)

    def update_track(self, track: Track) -> None:
        """Refresh comment cell and stored Track for any rows showing this track."""
        for row in range(self._table.rowCount()):
            group_item = self._table.item(row, _GROUP_COL)
            if group_item is None:
                continue
            existing = group_item.data(Qt.ItemDataRole.UserRole)
            if existing is None or existing.id != track.id:
                continue
            comments_item = self._table.item(row, _COMMENTS_COL)
            if comments_item is not None:
                comments_item.setText(track.comments or "")
            for col in range(self._table.columnCount()):
                cell = self._table.item(row, col)
                if cell is not None:
                    cell.setData(Qt.ItemDataRole.UserRole, track)

    def _selected_tracks(self) -> list[Track]:
        rows = {item.row() for item in self._table.selectedItems()}
        tracks: list[Track] = []
        for row in rows:
            item = self._table.item(row, _GROUP_COL)
            if item is None:
                continue
            track = item.data(Qt.ItemDataRole.UserRole)
            if track is not None:
                tracks.append(track)
        return tracks

    def _on_context_menu(self, pos) -> None:
        tracks = self._selected_tracks()
        if not tracks:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("Move to Trash")
        viewport = self._table.viewport()
        anchor = viewport if viewport is not None else self._table
        action = menu.exec(anchor.mapToGlobal(pos))
        if action == delete_action:
            self._confirm_delete(tracks)

    def eventFilter(self, obj, event):
        if obj is self._table and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete:
                tracks = self._selected_tracks()
                if tracks:
                    self._confirm_delete(tracks)
                return True
        return super().eventFilter(obj, event)
