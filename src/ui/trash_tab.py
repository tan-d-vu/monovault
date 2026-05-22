"""Trash tab — inline view of trashed tracks.

Shows trash entries from every watched folder's .monovault/trash/manifest.json
in a single flat table.  Users can multi-select and Restore, Delete Permanently,
or Empty Trash without leaving the main window.

Double-click or Enter on a row plays the trashed file via the play_requested
signal so users can preview before deciding to restore or purge.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.trash import TrashEntry
from .controllers.delete_controller import DeleteController


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


class TrashTab(QWidget):
    COLUMN_TITLE = 0
    COLUMN_ARTIST = 1
    COLUMN_ALBUM = 2
    COLUMN_DURATION = 3
    COLUMN_CATEGORIES = 4
    COLUMN_ORIGINAL_PATH = 5
    COLUMN_DELETED_AT = 6

    play_requested = pyqtSignal(str, str)  # (trash_file_path, display_label)

    def __init__(self, delete_ctrl: DeleteController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._delete_ctrl = delete_ctrl
        self._rows: list[tuple[str, TrashEntry]] = []
        self._build_ui()
        self._delete_ctrl.trash_changed.connect(self.refresh)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        self._table = QTableWidget(0, 7, self)
        self._table.setHorizontalHeaderLabels(
            ["Title", "Artist", "Album", "Duration", "Categories", "Original Path", "Deleted At"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.installEventFilter(self)
        self._table.itemDoubleClicked.connect(self._on_double_clicked)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self.COLUMN_TITLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COLUMN_ARTIST, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COLUMN_ALBUM, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COLUMN_DURATION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COLUMN_CATEGORIES, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            self.COLUMN_ORIGINAL_PATH, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            self.COLUMN_DELETED_AT, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.itemSelectionChanged.connect(self._update_button_state)
        layout.addWidget(self._table, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self._restore_btn = QPushButton("Restore Selected")
        self._purge_btn = QPushButton("Delete Permanently")
        self._empty_btn = QPushButton("Empty Trash")

        self._restore_btn.clicked.connect(self._on_restore_clicked)
        self._purge_btn.clicked.connect(self._on_purge_clicked)
        self._empty_btn.clicked.connect(self._on_empty_clicked)

        button_row.addWidget(self._restore_btn)
        button_row.addWidget(self._purge_btn)
        button_row.addStretch(1)
        button_row.addWidget(self._empty_btn)
        layout.addLayout(button_row)

    def refresh(self) -> None:
        """Reload trash entries from disk."""
        self._rows = self._delete_ctrl.list_all_trash()
        self._table.setRowCount(len(self._rows))

        for row_index, (folder_path, entry) in enumerate(self._rows):
            watched = self._delete_ctrl.is_folder_watched(folder_path)
            original_abs = str(Path(folder_path) / entry.original_relpath)

            title_item = QTableWidgetItem(entry.title or entry.original_relpath)
            title_item.setData(Qt.ItemDataRole.UserRole, row_index)
            artist_item = QTableWidgetItem(entry.artist)
            album_item = QTableWidgetItem(entry.album)
            duration_item = QTableWidgetItem(_fmt_duration(entry.duration))
            duration_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            categories_item = QTableWidgetItem(", ".join(entry.categories))
            path_item = QTableWidgetItem(original_abs)
            deleted_item = QTableWidgetItem(entry.deleted_at)

            if not watched:
                tooltip = "Source folder is no longer watched — cannot restore"
                for cell in (
                    title_item, artist_item, album_item, duration_item,
                    categories_item, path_item, deleted_item,
                ):
                    cell.setToolTip(tooltip)

            self._table.setItem(row_index, self.COLUMN_TITLE, title_item)
            self._table.setItem(row_index, self.COLUMN_ARTIST, artist_item)
            self._table.setItem(row_index, self.COLUMN_ALBUM, album_item)
            self._table.setItem(row_index, self.COLUMN_DURATION, duration_item)
            self._table.setItem(row_index, self.COLUMN_CATEGORIES, categories_item)
            self._table.setItem(row_index, self.COLUMN_ORIGINAL_PATH, path_item)
            self._table.setItem(row_index, self.COLUMN_DELETED_AT, deleted_item)

        count = len(self._rows)
        if count == 0:
            self._status_label.setText("Trash is empty.")
        else:
            noun = "track" if count == 1 else "tracks"
            self._status_label.setText(f"{count} {noun} in Trash.")

        self._empty_btn.setEnabled(bool(self._rows))
        self._update_button_state()

    def _selected_rows(self) -> list[tuple[str, TrashEntry]]:
        indices = sorted({item.row() for item in self._table.selectedItems()})
        return [self._rows[i] for i in indices if 0 <= i < len(self._rows)]

    def _update_button_state(self) -> None:
        selected = self._selected_rows()
        self._purge_btn.setEnabled(bool(selected))
        any_restorable = any(
            self._delete_ctrl.is_folder_watched(folder_path) for folder_path, _ in selected
        )
        self._restore_btn.setEnabled(any_restorable)

    def _on_restore_clicked(self) -> None:
        restorable = [
            (fp, entry)
            for fp, entry in self._selected_rows()
            if self._delete_ctrl.is_folder_watched(fp)
        ]
        if restorable:
            self._delete_ctrl.restore(restorable)

    def _on_purge_clicked(self) -> None:
        selected = self._selected_rows()
        if not selected:
            return
        count = len(selected)
        noun = "track" if count == 1 else "tracks"
        reply = QMessageBox.question(
            self,
            "Delete Permanently",
            f"Permanently delete {count} {noun}?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._delete_ctrl.purge(selected)

    def _on_empty_clicked(self) -> None:
        if not self._rows:
            return
        count = len(self._rows)
        noun = "track" if count == 1 else "tracks"
        reply = QMessageBox.question(
            self,
            "Empty Trash",
            f"Permanently delete all {count} {noun} in Trash?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._delete_ctrl.empty_trash()

    def _on_double_clicked(self, item) -> None:
        self._play_selected()

    def eventFilter(self, obj, event) -> bool:
        if obj == self._table and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                self._play_selected()
                return True
        return super().eventFilter(obj, event)

    def _play_selected(self) -> None:
        selected = self._table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if row < 0 or row >= len(self._rows):
            return
        folder_path, entry = self._rows[row]
        trash_file = Path(folder_path) / ".monovault" / "trash" / entry.trash_filename
        label = f"{entry.title} - {entry.artist}" if entry.artist else entry.title
        self.play_requested.emit(str(trash_file), label)
