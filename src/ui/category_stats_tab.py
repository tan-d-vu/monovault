"""Category stats tab — per-category usage statistics with filter-to-library action."""

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.category_stats import CategoryStats, compute_stats
from ..core.library import LibraryManager
from .dialogs.merge_dialog import MergeDialog

UNTAGGED_SENTINEL = "__UNTAGGED__"


class _NumericItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            return int(self.text()) < int(other.text())
        except ValueError:
            return super().__lt__(other)


class CategoryStatsTab(QWidget):
    category_filter_requested = pyqtSignal(str)
    rename_requested = pyqtSignal(str, str)
    merge_requested = pyqtSignal(list, str)
    delete_requested = pyqtSignal(list)

    def __init__(self, library: LibraryManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._library = library
        self._stats: CategoryStats | None = None
        self._orphan_threshold = 1
        self._dirty = True
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        top_bar = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search categories...")
        self._refresh_btn = QPushButton("Refresh")
        self._summary_label = QLabel("")
        top_bar.addWidget(self._search_input)
        top_bar.addWidget(self._refresh_btn)
        top_bar.addWidget(self._summary_label, 1)
        layout.addLayout(top_bar)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._category_table = QTableWidget()
        self._category_table.setColumnCount(3)
        self._category_table.setHorizontalHeaderLabels(["Category", "Count", "Flag"])
        self._configure_table(self._category_table)
        self._category_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._category_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._category_table.customContextMenuRequested.connect(self._on_context_menu)
        self._category_table.installEventFilter(self)

        self._pairs_table = QTableWidget()
        self._pairs_table.setColumnCount(2)
        self._pairs_table.setHorizontalHeaderLabels(["Pair", "Count"])
        self._configure_table(self._pairs_table)
        self._pairs_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        pairs_panel = QWidget()
        pairs_layout = QVBoxLayout(pairs_panel)
        pairs_layout.setContentsMargins(0, 0, 0, 0)
        pairs_layout.setSpacing(2)
        pairs_label = QLabel("Category Pairs")
        pairs_layout.addWidget(pairs_label)
        pairs_layout.addWidget(self._pairs_table)

        self._splitter.addWidget(self._category_table)
        self._splitter.addWidget(pairs_panel)
        self._splitter.setSizes([400, 300])
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setHandleWidth(1)
        layout.addWidget(self._splitter, 1)

        bottom_bar = QHBoxLayout()
        self._untagged_btn = QPushButton("Show untagged tracks (0)")
        bottom_bar.addWidget(self._untagged_btn)
        bottom_bar.addStretch()
        layout.addLayout(bottom_bar)

        self._search_input.textChanged.connect(self._apply_search_filter)
        self._refresh_btn.clicked.connect(self.refresh)
        self._category_table.itemDoubleClicked.connect(self._on_category_activated)
        self._untagged_btn.clicked.connect(
            lambda: self.category_filter_requested.emit(UNTAGGED_SENTINEL)
        )

    def _configure_table(self, table: QTableWidget) -> None:
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        vh = table.verticalHeader()
        if vh is not None:
            vh.hide()
        header = table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(True)

    def invalidate(self) -> None:
        if self.isVisible():
            self.refresh()
        else:
            self._dirty = True

    def refresh(self) -> None:
        self._stats = compute_stats(self._library.get_all_tracks())
        self._dirty = False
        self._populate_summary()
        self._populate_categories_table()
        self._populate_pairs_table()
        self._update_untagged_button()
        self._apply_search_filter(self._search_input.text())

    def show_if_dirty(self) -> None:
        if self._dirty:
            self.refresh()

    def _populate_summary(self) -> None:
        if self._stats is None:
            return
        self._summary_label.setText(
            f"{self._stats.unique_count()} unique · "
            f"{len(self._stats.orphans(self._orphan_threshold))} orphans · "
            f"{self._stats.untagged_count} untagged"
        )

    def _populate_categories_table(self) -> None:
        if self._stats is None:
            return
        sorted_cats = sorted(
            self._stats.counts.items(), key=lambda x: (-x[1], x[0])
        )
        self._category_table.setUpdatesEnabled(False)
        try:
            self._category_table.setRowCount(len(sorted_cats))
            for row, (name, count) in enumerate(sorted_cats):
                name_item = QTableWidgetItem(name)
                name_item.setData(Qt.ItemDataRole.UserRole, name)
                count_item = _NumericItem(str(count))
                flag = "⚠" if count <= self._orphan_threshold else ""
                flag_item = QTableWidgetItem(flag)
                if flag:
                    flag_item.setToolTip("Used on ≤1 track")
                self._category_table.setItem(row, 0, name_item)
                self._category_table.setItem(row, 1, count_item)
                self._category_table.setItem(row, 2, flag_item)
        finally:
            self._category_table.setUpdatesEnabled(True)

    def _populate_pairs_table(self) -> None:
        if self._stats is None:
            return
        pairs = self._stats.co_occurrences
        self._pairs_table.setUpdatesEnabled(False)
        try:
            self._pairs_table.setRowCount(len(pairs))
            for row, (a, b, n) in enumerate(pairs):
                self._pairs_table.setItem(row, 0, QTableWidgetItem(f"{a} + {b}"))
                self._pairs_table.setItem(row, 1, _NumericItem(str(n)))
        finally:
            self._pairs_table.setUpdatesEnabled(True)

    def _update_untagged_button(self) -> None:
        count = self._stats.untagged_count if self._stats else 0
        self._untagged_btn.setText(f"Show untagged tracks ({count})")

    def _apply_search_filter(self, query: str) -> None:
        q = query.lower()
        for row in range(self._category_table.rowCount()):
            item = self._category_table.item(row, 0)
            name = item.text() if item else ""
            self._category_table.setRowHidden(row, q != "" and q not in name.lower())

    def _on_category_activated(self, item: QTableWidgetItem) -> None:
        row = item.row()
        name_item = self._category_table.item(row, 0)
        if name_item is None:
            return
        category = name_item.data(Qt.ItemDataRole.UserRole)
        if category:
            self.category_filter_requested.emit(category)

    def _selected_categories(self) -> list[str]:
        rows = sorted({item.row() for item in self._category_table.selectedItems()})
        out: list[str] = []
        for row in rows:
            item = self._category_table.item(row, 0)
            if item is None:
                continue
            cat = item.data(Qt.ItemDataRole.UserRole)
            if cat:
                out.append(cat)
        return out

    def _on_context_menu(self, pos) -> None:
        selected = self._selected_categories()
        if not selected:
            return
        menu = QMenu(self)
        rename_action = menu.addAction("Rename...")
        merge_action = menu.addAction("Merge into...")
        menu.addSeparator()
        delete_action = menu.addAction("Delete from all tracks")
        rename_action.setEnabled(len(selected) == 1)
        viewport = self._category_table.viewport()
        anchor = viewport if viewport is not None else self._category_table
        action = menu.exec(anchor.mapToGlobal(pos))
        if action == rename_action and len(selected) == 1:
            self._prompt_rename(selected[0])
        elif action == merge_action:
            self._prompt_merge(selected)
        elif action == delete_action:
            self._prompt_delete(selected)

    def _prompt_rename(self, old: str) -> None:
        count = self._stats.counts.get(old, 0) if self._stats else 0
        new, ok = QInputDialog.getText(
            self, "Rename Category",
            f'Rename "{old}" (used by {count} tracks) to:',
            text=old,
        )
        if not ok:
            return
        new_norm = new.strip().lower()
        if not new_norm or any(c.isspace() for c in new_norm):
            QMessageBox.warning(self, "Invalid Name",
                "Category must be non-empty and contain no whitespace.")
            return
        if new_norm == old:
            return
        confirm = QMessageBox.question(
            self, "Confirm Rename",
            f'Rename "{old}" → "{new_norm}" on {count} tracks?\n'
            "This writes to file metadata and cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.rename_requested.emit(old, new_norm)

    def _prompt_merge(self, sources: list[str]) -> None:
        dialog = MergeDialog(sources, self._all_category_names(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        target = dialog.target_value()
        affected = sum(self._stats.counts.get(s, 0) for s in sources) if self._stats else 0
        confirm = QMessageBox.question(
            self, "Confirm Merge",
            f'Merge {len(sources)} categories into "{target}"?\n'
            f"Up to {affected} tracks will be modified.\n"
            "This writes to file metadata and cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.merge_requested.emit(sources, target)

    def _prompt_delete(self, categories: list[str]) -> None:
        affected = sum(self._stats.counts.get(c, 0) for c in categories) if self._stats else 0
        label = ", ".join(f'"{c}"' for c in categories)
        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {label} from all tracks?\n"
            f"{affected} tracks will be modified.\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(categories)

    def _all_category_names(self) -> list[str]:
        if not self._stats:
            return []
        return sorted(self._stats.counts.keys())

    def eventFilter(self, obj, event):
        if obj is self._category_table and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete:
                selected = self._selected_categories()
                if selected:
                    self._prompt_delete(selected)
                return True
        return super().eventFilter(obj, event)
