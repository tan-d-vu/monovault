import os
import platform
import subprocess
import sys

from PyQt6.QtCore import QEvent, Qt, QThread, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.categorizer import Categorizer
from ..core.category_sources import ArtistCategorySource, SimilarCategoryCategorySource
from ..core.events import EventBus
from ..core.library import LibraryManager
from ..core.playback import PlaybackEngine
from ..core.scanner import Scanner
from ..core.volume_utils import ensure_volume_id, find_volume_by_id
from ..models.track import Track
from .category_stats_tab import UNTAGGED_SENTINEL, CategoryStatsTab
from .controllers import CategoryController, PlaybackController, SearchController
from .controllers.delete_controller import DeleteController
from .duplicates_tab import DuplicatesTab
from .panels import (
    create_details_panel,
    create_folder_panel,
    create_playback_bar,
    create_scan_progress_bar,
    create_track_table,
    get_folder_width,
    populate_folder_tree,
    update_categories,
    update_play_icon,
    update_suggestions,
    update_track_details_ui,
)
from .scanner_worker import ScannerWorker
from .styles import STYLESHEET
from .widgets import Toast


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._bus = EventBus()
        self.library = LibraryManager()
        self.scanner = Scanner()
        self.playback_engine = PlaybackEngine()

        self.categorizer = Categorizer(
            self.library,
            sources=[
                ArtistCategorySource(self.library),
                SimilarCategoryCategorySource(self.library),
            ],
        )

        self.playback_ctrl = PlaybackController(self.playback_engine, bus=self._bus, parent=self)
        self.search_ctrl = SearchController(self.library, bus=self._bus, parent=self)
        self.category_ctrl = CategoryController(self.categorizer, bus=self._bus, parent=self)
        self.delete_ctrl = DeleteController(
            self.library, self.playback_engine, self.scanner, parent=self
        )

        self.all_tracks: list[Track] = []

        self._scan_thread: QThread | None = None
        self._scan_worker: ScannerWorker | None = None
        self._scan_announce_done = False

        self._setup_ui()
        self._connect_controllers()
        self._connect_shortcuts()
        self._load_library()
        self.statusBar().showMessage("Ready")

    def _setup_ui(self):
        self.setWindowTitle("MonoVault")
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        (
            self.folder_tree_panel,
            self.folder_tree_widget,
            self.add_folder_btn,
            self.refresh_btn,
        ) = create_folder_panel()
        (
            self.track_table_panel,
            self.search_input,
            self.track_table_widget,
            self.track_table_manager,
        ) = create_track_table()
        (
            self.details_panel,
            self.album_art_label,
            self.track_title,
            self.track_info,
            self.track_date_added,
            self.category_input,
            self.category_input_hint,
            self.suggestions_header,
            self.suggestions_container,
            self.categories_layout,
            self.suggestions_layout,
        ) = create_details_panel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.folder_tree_panel)
        splitter.addWidget(self.track_table_panel)
        splitter.setSizes([200, 500])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(1)
        self._splitter = splitter

        self.duplicates_tab = DuplicatesTab(self.library, self._confirm_and_delete_tracks)
        self.duplicates_tab.track_selected.connect(self.category_ctrl.select_track)

        self.category_stats_tab = CategoryStatsTab(self.library)
        self.category_stats_tab.category_filter_requested.connect(
            self._on_category_filter_requested
        )

        self._tabs = QTabWidget()
        self._tabs.addTab(self._splitter, "Library")
        self._tabs.addTab(self.duplicates_tab, "Duplicates")
        self._tabs.addTab(self.category_stats_tab, "Categories")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        outer_splitter = QSplitter(Qt.Orientation.Horizontal)
        outer_splitter.addWidget(self._tabs)
        outer_splitter.addWidget(self.details_panel)
        outer_splitter.setSizes([700, 280])
        outer_splitter.setStretchFactor(0, 1)
        outer_splitter.setStretchFactor(1, 0)
        outer_splitter.setHandleWidth(1)
        outer_splitter.setCollapsible(1, False)
        self._outer_splitter = outer_splitter
        main_layout.addWidget(outer_splitter)

        (
            self.playback_bar,
            self.now_playing_label,
            self.play_btn,
            self.position_slider,
            self.time_label,
            self.volume_slider,
        ) = create_playback_bar()

        (
            self.scan_progress_bar,
            self.scan_status_label,
            self.scan_progress,
            self.scan_cancel_btn,
        ) = create_scan_progress_bar()

        overall = QWidget()
        overall_layout = QVBoxLayout(overall)
        overall_layout.setContentsMargins(4, 4, 4, 4)
        overall_layout.setSpacing(4)
        overall_layout.addWidget(self._outer_splitter, 1)
        overall_layout.addWidget(self.scan_progress_bar)
        overall_layout.addWidget(self.playback_bar)
        self.setCentralWidget(overall)

        self.toast = Toast(self)

        self.add_folder_btn.clicked.connect(self._add_folder)
        self.refresh_btn.clicked.connect(self._refresh_library)
        self.folder_tree_widget.customContextMenuRequested.connect(self._on_folder_context_menu)
        self.folder_tree_widget.itemChanged.connect(self._on_folder_item_changed)
        self.search_input.textChanged.connect(self.search_ctrl.on_text_changed)
        self.track_table_widget.itemDoubleClicked.connect(self._on_track_double_clicked)
        self.track_table_widget.itemSelectionChanged.connect(self._on_track_selected)
        self.track_table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.track_table_widget.customContextMenuRequested.connect(self._on_track_context_menu)
        self.track_table_widget.installEventFilter(self)
        self.category_input.returnPressed.connect(self._on_add_category_input)
        self.category_input.textChanged.connect(self._on_category_input_changed)
        self.scan_cancel_btn.clicked.connect(self._on_scan_cancel_clicked)

    def _connect_controllers(self):
        self.playback_ctrl.now_playing_changed.connect(self.now_playing_label.setText)
        self.playback_ctrl.play_state_changed.connect(self._update_play_icon)
        self.playback_ctrl.time_display_changed.connect(self.time_label.setText)
        self.playback_ctrl.slider_position_changed.connect(self.position_slider.setValue)

        self.play_btn.clicked.connect(self.playback_ctrl.toggle_playback)
        self.position_slider.sliderMoved.connect(self.playback_ctrl.seek)
        self.volume_slider.sliderMoved.connect(self.playback_ctrl.set_volume)

        self.search_ctrl.results_changed.connect(self._on_search_results)

        self.category_ctrl.categories_changed.connect(self._on_categories_changed)
        self.category_ctrl.suggestions_changed.connect(self._on_suggestions_changed)
        self.category_ctrl.track_details_changed.connect(self._on_track_details_changed)
        self.category_ctrl.write_failed.connect(self._on_write_failed)

        self.category_stats_tab.rename_requested.connect(self._on_category_rename_requested)
        self.category_stats_tab.merge_requested.connect(self._on_category_merge_requested)
        self.category_stats_tab.delete_requested.connect(self._on_category_delete_requested)

        self.delete_ctrl.delete_completed.connect(self._on_delete_completed)
        self.delete_ctrl.delete_failed.connect(self._on_delete_failed)
        self.delete_ctrl.restore_completed.connect(self._on_restore_completed)
        self.delete_ctrl.restore_failed.connect(self._on_restore_failed)

    def _connect_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.search_input.setFocus)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._refresh_library)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._add_folder)
        QShortcut(QKeySequence("Ctrl+Shift+T"), self).activated.connect(self._open_trash_dialog)

    def _on_write_failed(self, file_path: str, msg: str) -> None:
        self.toast.show_message(
            f"Failed to save categories for {os.path.basename(file_path)}: {msg}"
        )

    def _load_library(self):
        self._reassociate_volumes()
        folders = self.library.get_folders()
        existing_tracks = self.library.get_all_tracks()
        populate_folder_tree(self.folder_tree_widget, folders, existing_tracks or None)

        if folders:
            folder_width = get_folder_width(self.folder_tree_widget, folders)
            self.folder_tree_widget.setColumnWidth(0, folder_width)
            self._splitter.setSizes([folder_width + 20, 500])

        self._start_scan(folders, announce_done=False)

    def _reassociate_volumes(self) -> None:
        """Check each configured folder. If missing, attempt re-association.

        Iterates through all configured folders. For any that no longer exist,
        attempts to find the volume by its volume_id and update the path.
        """
        from pathlib import Path

        config = self.library.config
        for folder in list(config.folders):
            if Path(folder).exists():
                continue

            # Folder is missing — find its volume_id from config
            for vol_id, vol_info in config.volumes.items():
                if folder in vol_info.get("paths", []):
                    new_path = find_volume_by_id(vol_id)
                    if new_path:
                        new_folder = str(new_path)
                        config.update_volume_path(vol_id, folder, new_folder)
                    break

        self.library.folders = config.get_folders()

    def _register_volume(self, folder: str) -> None:
        """Create volume_id sidecar and register in global config.

        Args:
            folder: Absolute path to folder
        """
        from pathlib import Path

        vol_id = ensure_volume_id(Path(folder))
        if vol_id:
            self.library.config.register_volume(vol_id, folder)
        else:
            # Read-only folder — show non-modal warning
            QMessageBox.warning(
                self,
                "Read-Only Folder",
                f"Cannot create metadata in '{folder}'.\n"
                "Categories will still be saved in file tags,\n"
                "but date-added tracking won't be available for this folder.",
            )

    def _load_tracks(self):
        had_selection = self.track_table_widget.currentRow() >= 0
        self.all_tracks = self.library.get_all_tracks()
        self.playback_ctrl.set_track_list(self.all_tracks)
        self.track_table_manager.populate(self.all_tracks)
        if self.all_tracks and not had_selection:
            self.track_table_widget.selectRow(0)

    def _add_folder(self):
        from pathlib import Path

        if self._is_scanning():
            return

        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if not folder:
            return

        # Canonicalize before any downstream use so library.folders (which
        # Config.add_folder resolves) and track.folder_path (set by the scanner
        # from this same string) stay in sync within the session. Without this,
        # macOS symlinks like /tmp -> /private/tmp cause populate_folder_tree
        # to miss subfolders until the next launch.
        folder = str(Path(folder).resolve())

        if not os.access(folder, os.W_OK):
            QMessageBox.warning(
                self,
                "Read-Only Folder",
                "This folder is read-only. MonoVault requires write access to store metadata.",
            )
            return

        self.library.add_folder(folder)
        self._register_volume(folder)
        populate_folder_tree(self.folder_tree_widget, self.library.get_folders())
        self._start_scan([folder], announce_done=False)

    def _refresh_library(self):
        if self._is_scanning():
            return
        folders = self.library.get_folders()
        self.library.clear()
        self.duplicates_tab.invalidate()
        self.category_stats_tab.invalidate()
        self._load_tracks()
        self._start_scan(folders, announce_done=True)

    def _is_scanning(self) -> bool:
        return self._scan_thread is not None and self._scan_thread.isRunning()

    def _start_scan(self, folders: list[str], announce_done: bool) -> None:
        """Kick off a background scan of the given folders.

        announce_done=True shows the "Refresh Complete" dialog when finished.
        Folders that no longer exist are skipped — the worker would return an
        empty list for them anyway and spinning up a thread for nothing leaves
        tests and scripted shutdowns with a running QThread to clean up.
        """
        from pathlib import Path

        live_folders = [f for f in folders if Path(f).exists()]
        if not live_folders:
            self._load_tracks()
            return
        if self._is_scanning():
            return

        self._scan_announce_done = announce_done

        thread = QThread(self)
        worker = ScannerWorker(self.scanner)
        worker.set_folders(live_folders)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_scan_progress)
        worker.folder_done.connect(self._on_scan_folder_done)
        worker.error.connect(self._on_scan_error)
        worker.all_done.connect(self._on_scan_all_done)
        worker.all_done.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._scan_thread = thread
        self._scan_worker = worker

        self.add_folder_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.scan_progress.setValue(0)
        self.scan_status_label.setText("Scanning...")
        self.scan_progress_bar.show()

        thread.start()

    def _on_scan_progress(self, scanned: int, total: int, current_file: str) -> None:
        if total > 0:
            self.scan_progress.setMaximum(total)
            self.scan_progress.setValue(scanned)
        basename = os.path.basename(current_file) if current_file else ""
        self.scan_status_label.setText(f"Scanning {scanned}/{total} — {basename}")

    def _on_scan_folder_done(self, folder: str, tracks: list) -> None:
        for track in tracks:
            self.library.add_track(track)
        # Rebuild tree to show discovered subfolders
        all_tracks = self.library.get_all_tracks()
        folders = self.library.get_folders()
        populate_folder_tree(self.folder_tree_widget, folders, all_tracks)
        self._load_tracks()

    def _on_scan_error(self, folder: str, message: str) -> None:
        self.statusBar().showMessage(f"Scan failed for {folder}: {message}", 5000)

    def _on_scan_all_done(self) -> None:
        self.scan_progress_bar.hide()
        self.scan_status_label.setText("")
        self.add_folder_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self._scan_thread = None
        self._scan_worker = None
        self.category_stats_tab.invalidate()

        if self._scan_announce_done:
            self._scan_announce_done = False
            QMessageBox.information(self, "Refresh Complete", "Library has been refreshed.")

    def _on_scan_cancel_clicked(self) -> None:
        if self._scan_worker is not None:
            self._scan_worker.cancel()
            self.scan_status_label.setText("Cancelling...")

    def _on_folder_context_menu(self, pos):
        item = self.folder_tree_widget.itemAt(pos)
        if not item:
            return
        folder = item.data(0, Qt.ItemDataRole.UserRole)
        if not folder:
            return
        menu = QMenu(self)
        show_action = menu.addAction("Show Folder")
        menu.addSeparator()
        remove_action = menu.addAction("Remove Folder")
        action = menu.exec(self.folder_tree_widget.mapToGlobal(pos))
        if action == show_action:
            self._open_folder_in_explorer(folder)
        elif action == remove_action:
            self._remove_folder(folder)

    def _remove_folder(self, folder: str):
        if self._is_scanning():
            return
        reply = QMessageBox.question(
            self,
            "Remove Folder",
            f"Remove '{folder}' from library?\nThis will remove all tracks from this folder.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.library.remove_folder(folder)
            self.duplicates_tab.invalidate()
            populate_folder_tree(self.folder_tree_widget, self.library.get_folders())
            self._load_tracks()

    def _open_folder_in_explorer(self, folder: str):
        system = platform.system()
        try:
            if system == "Linux":
                subprocess.run(["xdg-open", folder], check=False)
            elif system == "Windows":
                subprocess.run(["explorer", folder], check=False)
            elif system == "Darwin":
                subprocess.run(["open", folder], check=False)
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _on_folder_item_changed(self, item, column: int) -> None:
        """Cascade checkbox changes between parent folders and subfolder children."""
        tree = self.folder_tree_widget
        tree.blockSignals(True)

        parent = item.parent()
        if parent is None:
            # Top-level folder changed — propagate to all children (unless partial)
            new_state = item.checkState(0)
            if new_state != Qt.CheckState.PartiallyChecked:
                for i in range(item.childCount()):
                    child = item.child(i)
                    if child:
                        child.setCheckState(0, new_state)
        else:
            # Subfolder changed — update parent to reflect aggregate state
            checked_count = sum(
                1
                for i in range(parent.childCount())
                if parent.child(i) and parent.child(i).checkState(0) == Qt.CheckState.Checked
            )
            total = parent.childCount()
            if checked_count == total:
                parent.setCheckState(0, Qt.CheckState.Checked)
            elif checked_count == 0:
                parent.setCheckState(0, Qt.CheckState.Unchecked)
            else:
                parent.setCheckState(0, Qt.CheckState.PartiallyChecked)

        tree.blockSignals(False)
        self._on_folder_filter_changed()

    def _on_folder_filter_changed(self) -> None:
        """Filter visible tracks based on checked folders and subfolders."""
        tree = self.folder_tree_widget
        checked_dirs: set[str] = set()

        for i in range(tree.topLevelItemCount()):
            top = tree.topLevelItem(i)
            if top is None or top.checkState(0) == Qt.CheckState.Unchecked:
                continue

            root_path = top.data(0, Qt.ItemDataRole.UserRole)

            if top.childCount() == 0:
                # No subfolders — include all tracks in this root folder
                checked_dirs.add(root_path)
            else:
                # Has subfolders — root-level files always follow parent state,
                # individual subfolders follow their own check state
                checked_dirs.add(root_path)
                for j in range(top.childCount()):
                    child = top.child(j)
                    if child and child.checkState(0) == Qt.CheckState.Checked:
                        checked_dirs.add(child.data(0, Qt.ItemDataRole.UserRole))

        all_tracks = self.library.get_all_tracks()
        visible_tracks = [t for t in all_tracks if os.path.dirname(t.file_path) in checked_dirs]
        self.all_tracks = visible_tracks
        self.playback_ctrl.set_track_list(self.all_tracks)
        self.track_table_manager.populate(self.all_tracks)

    def _on_search_results(self, tracks: list[Track]) -> None:
        self.all_tracks = tracks
        self.track_table_manager.populate(self.all_tracks)
        self.playback_ctrl.set_track_list(self.all_tracks)

    def _on_track_context_menu(self, pos) -> None:
        selected_rows = {item.row() for item in self.track_table_widget.selectedItems()}
        if not selected_rows:
            return

        selected_tracks: list[Track] = []
        for row in selected_rows:
            item = self.track_table_widget.item(row, 0)
            if item is None:
                continue
            track = item.data(Qt.ItemDataRole.UserRole)
            if track:
                selected_tracks.append(track)

        if not selected_tracks:
            return

        tracks_with_categories = [t for t in selected_tracks if t.categories]

        menu = QMenu(self)
        clear_action = menu.addAction("Clear Categories")
        if not tracks_with_categories:
            clear_action.setEnabled(False)
        menu.addSeparator()
        delete_action = menu.addAction("Move to Trash")

        action = menu.exec(self.track_table_widget.viewport().mapToGlobal(pos))
        if action == clear_action and tracks_with_categories:
            self._confirm_and_clear_categories(tracks_with_categories)
        elif action == delete_action:
            self._confirm_and_delete_tracks(selected_tracks)

    def _confirm_and_clear_categories(self, tracks: list[Track]) -> None:
        count = len(tracks)
        noun = "track" if count == 1 else "tracks"
        reply = QMessageBox.question(
            self,
            "Clear Categories",
            f"Clear all categories from {count} {noun}?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        cleared = self.category_ctrl.clear_categories_bulk(tracks)
        for track in tracks:
            self.track_table_manager.update_track(track)
        self.statusBar().showMessage(f"Cleared categories from {cleared} {noun}.", 3000)

    def _delete_selected_tracks(self) -> None:
        selected_rows = {item.row() for item in self.track_table_widget.selectedItems()}
        if not selected_rows:
            return
        tracks: list[Track] = []
        for row in selected_rows:
            item = self.track_table_widget.item(row, 0)
            if item is None:
                continue
            track = item.data(Qt.ItemDataRole.UserRole)
            if track:
                tracks.append(track)
        if tracks:
            self._confirm_and_delete_tracks(tracks)

    def _confirm_and_delete_tracks(self, tracks: list[Track]) -> None:
        count = len(tracks)
        noun = "track" if count == 1 else "tracks"
        reply = QMessageBox.question(
            self,
            "Move to Trash",
            f"Move {count} {noun} to Trash?\nYou can restore them from the Trash dialog.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.delete_ctrl.delete_tracks(tracks)

    def _on_delete_completed(self, count: int) -> None:
        if count == 0:
            return
        noun = "track" if count == 1 else "tracks"
        self.toast.show_message(f"Moved {count} {noun} to Trash")
        self._on_folder_filter_changed()
        self.duplicates_tab.refresh_after_delete()

    def _on_delete_failed(self, message: str, partial_count: int) -> None:
        if partial_count > 0:
            noun = "track" if partial_count == 1 else "tracks"
            self.toast.show_message(
                f"Moved {partial_count} {noun} to Trash; some failed: {message}"
            )
        else:
            self.toast.show_message(f"Failed to move tracks to Trash: {message}")
        self._on_folder_filter_changed()
        self.duplicates_tab.refresh_after_delete()

    def _on_restore_completed(self, tracks: list[Track]) -> None:
        if not tracks:
            return
        count = len(tracks)
        noun = "track" if count == 1 else "tracks"
        self.toast.show_message(f"Restored {count} {noun}")
        self._on_folder_filter_changed()

    def _on_restore_failed(self, message: str) -> None:
        self.toast.show_message(f"Restore failed: {message}")

    def _open_trash_dialog(self) -> None:
        from .trash_dialog import TrashDialog

        dialog = TrashDialog(self.delete_ctrl, parent=self)
        dialog.exec()

    def _on_track_double_clicked(self, item, column=None):
        row = item.row()
        track = self.track_table_widget.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if track:
            self.playback_ctrl.play_track(track)

    def _on_track_selected(self):
        selected = self.track_table_widget.selectedItems()
        if selected:
            row = selected[0].row()
            track = self.track_table_widget.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if track:
                self.category_ctrl.select_track(track)
                # Set the track in playback controller so play button works for default selected track on app start
                if self.playback_ctrl.current_track is None:
                    self.now_playing_label.setText(f"{track.title} - {track.artist}")
                    self.playback_ctrl.set_current_track(track)

    def _update_play_icon(self, is_playing: bool):
        update_play_icon(self.play_btn, is_playing)

    def _on_add_category_input(self):
        raw = self.category_input.text().strip()
        if not raw:
            return
        if any(c.isspace() for c in raw):
            self.category_input_hint.show()
            return
        self.category_input_hint.hide()
        self.category_ctrl.add_category(raw)
        self.category_input.clear()

    def _on_category_input_changed(self, _text: str) -> None:
        if self.category_input_hint.isVisible():
            self.category_input_hint.hide()

    def _on_categories_changed(self, track: Track) -> None:
        if track is self.category_ctrl.current_track:
            update_categories(track, self.categories_layout, self._on_remove_category)
        self.track_table_manager.update_track(track)
        self.duplicates_tab.update_track(track)
        self.category_stats_tab.invalidate()

    def _on_remove_category(self, category: str) -> None:
        self.category_ctrl.remove_category(category)

    def _on_suggestions_changed(self, suggestions: list) -> None:
        update_suggestions(
            suggestions,
            self.suggestions_header,
            self.suggestions_container,
            self.suggestions_layout,
            self._on_suggestion_clicked,
        )

    def _on_track_details_changed(self, track: Track) -> None:
        update_track_details_ui(
            track,
            self.track_title,
            self.track_info,
            self.track_date_added,
            self.album_art_label,
        )

    def _on_suggestion_clicked(self, category: str, source: str):
        self.category_ctrl.accept_suggestion(category)

    def _on_tab_changed(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if widget is self.category_stats_tab:
            self.category_stats_tab.show_if_dirty()

    def _on_category_filter_requested(self, category: str) -> None:
        cat = None if category == UNTAGGED_SENTINEL else category
        self.search_ctrl.filter_by_category(cat)
        self._tabs.setCurrentIndex(0)
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        label = "untagged tracks" if cat is None else f'category "{cat}"'
        self.statusBar().showMessage(f"Filtered to {label}", 5000)

    def _on_category_rename_requested(self, old: str, new: str) -> None:
        try:
            modified = self.category_ctrl.replace_everywhere({old}, new)
        except ValueError as e:
            self.toast.show_message(f"Rename failed: {e}")
            return
        self._announce_bulk(f'Renamed "{old}" → "{new}"', len(modified))

    def _on_category_merge_requested(self, sources: list, target: str) -> None:
        try:
            modified = self.category_ctrl.replace_everywhere(set(sources), target)
        except ValueError as e:
            self.toast.show_message(f"Merge failed: {e}")
            return
        self._announce_bulk(f'Merged {len(sources)} categories into "{target}"', len(modified))

    def _on_category_delete_requested(self, categories: list) -> None:
        try:
            modified = self.category_ctrl.replace_everywhere(set(categories), None)
        except ValueError as e:
            self.toast.show_message(f"Delete failed: {e}")
            return
        label = ", ".join(f'"{c}"' for c in categories)
        self._announce_bulk(f"Deleted {label}", len(modified))

    def _announce_bulk(self, what: str, count: int) -> None:
        noun = "track" if count == 1 else "tracks"
        self.statusBar().showMessage(f"{what} on {count} {noun}.", 5000)
        self.category_stats_tab.invalidate()

    def closeEvent(self, event):
        if self._scan_worker is not None:
            self._scan_worker.cancel()
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self._scan_thread.quit()
            self._scan_thread.wait(3000)
        self.category_ctrl.shutdown()
        self._bus.clear()
        self.playback_ctrl.stop()
        event.accept()

    def eventFilter(self, obj, event):
        if obj == self.track_table_widget and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                self._play_selected_track()
                return True
            if event.key() == Qt.Key.Key_Space:
                self._toggle_playback_for_selected_track()
                return True
            if event.key() == Qt.Key.Key_Delete:
                self._delete_selected_tracks()
                return True
        return super().eventFilter(obj, event)

    def _toggle_playback_for_selected_track(self) -> None:
        selected = self.track_table_widget.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        track = self.track_table_widget.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not track:
            return
        current = self.playback_ctrl.current_track
        if current is not None and current.id == track.id:
            self.playback_ctrl.toggle_playback()
            return
        self.playback_ctrl.play_track(track)

    def _play_selected_track(self):
        selected = self.track_table_widget.selectedItems()
        if selected:
            row = selected[0].row()
            track = self.track_table_widget.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if track:
                self.playback_ctrl.play_track(track)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
