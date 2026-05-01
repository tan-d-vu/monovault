"""Modal dialog listing trashed tracks across all watched folders.

Shows the trash entries from every folder's `.monovault/trash/manifest.json`
in a single flat table. Users can multi-select and Restore (move files back
to their original paths), Delete Permanently (hard delete), or Empty Trash
(purge everything in every folder).

Entries whose source folder is no longer being watched are still shown but
their Restore is disabled — the manifest is the source of truth, hiding it
would lie to the user.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..core.trash import TrashEntry
from .controllers.delete_controller import DeleteController


class TrashDialog(QDialog):
    COLUMN_TITLE = 0
    COLUMN_ARTIST = 1
    COLUMN_FOLDER = 2
    COLUMN_DELETED_AT = 3

    def __init__(self, delete_ctrl: DeleteController, parent=None) -> None:
        super().__init__(parent)
        self._delete_ctrl = delete_ctrl
        self._rows: list[tuple[str, TrashEntry]] = []

        self.setWindowTitle("Trash")
        self.setMinimumSize(720, 420)
        self._build_ui()
        self._delete_ctrl.trash_changed.connect(self._refresh)
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(["Title", "Artist", "Folder", "Deleted"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self.COLUMN_TITLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COLUMN_ARTIST, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COLUMN_FOLDER, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COLUMN_DELETED_AT, QHeaderView.ResizeMode.ResizeToContents)
        self._table.itemSelectionChanged.connect(self._update_button_state)
        layout.addWidget(self._table)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self._restore_btn = QPushButton("Restore Selected")
        self._purge_btn = QPushButton("Delete Permanently")
        self._empty_btn = QPushButton("Empty Trash")
        self._close_btn = QPushButton("Close")

        self._restore_btn.clicked.connect(self._on_restore_clicked)
        self._purge_btn.clicked.connect(self._on_purge_clicked)
        self._empty_btn.clicked.connect(self._on_empty_clicked)
        self._close_btn.clicked.connect(self.accept)

        button_row.addWidget(self._restore_btn)
        button_row.addWidget(self._purge_btn)
        button_row.addStretch(1)
        button_row.addWidget(self._empty_btn)
        button_row.addWidget(self._close_btn)
        layout.addLayout(button_row)

    def _refresh(self) -> None:
        self._rows = self._delete_ctrl.list_all_trash()
        self._table.setRowCount(len(self._rows))
        for row_index, (folder_path, entry) in enumerate(self._rows):
            watched = self._delete_ctrl.is_folder_watched(folder_path)
            folder_label = folder_path if watched else f"{folder_path} (not watched)"

            title_item = QTableWidgetItem(entry.title or entry.original_relpath)
            title_item.setData(Qt.ItemDataRole.UserRole, row_index)
            artist_item = QTableWidgetItem(entry.artist)
            folder_item = QTableWidgetItem(folder_label)
            deleted_item = QTableWidgetItem(entry.deleted_at)

            if not watched:
                tooltip = "Source folder is no longer watched — cannot restore"
                for cell in (title_item, artist_item, folder_item, deleted_item):
                    cell.setToolTip(tooltip)

            self._table.setItem(row_index, self.COLUMN_TITLE, title_item)
            self._table.setItem(row_index, self.COLUMN_ARTIST, artist_item)
            self._table.setItem(row_index, self.COLUMN_FOLDER, folder_item)
            self._table.setItem(row_index, self.COLUMN_DELETED_AT, deleted_item)

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
        selected = self._selected_rows()
        restorable = [
            (folder_path, entry)
            for folder_path, entry in selected
            if self._delete_ctrl.is_folder_watched(folder_path)
        ]
        if not restorable:
            return
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
        if reply != QMessageBox.StandardButton.Yes:
            return
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
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._delete_ctrl.empty_trash()
