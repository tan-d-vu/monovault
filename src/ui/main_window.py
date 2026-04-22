import os
import platform
import subprocess
import sys

from PyQt6.QtCore import QEvent, Qt, QThread, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
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
from .controllers import CategoryController, PlaybackController, SearchController
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

        self.all_tracks: list[Track] = []

        self._scan_thread: QThread | None = None
        self._scan_worker: ScannerWorker | None = None
        self._scan_announce_done = False

        self._setup_ui()
        self._connect_controllers()
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
            self.suggestions_header,
            self.suggestions_container,
            self.categories_layout,
            self.suggestions_layout,
        ) = create_details_panel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.folder_tree_panel)
        splitter.addWidget(self.track_table_panel)
        splitter.addWidget(self.details_panel)
        splitter.setSizes([200, 500, 280])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setHandleWidth(1)
        splitter.setCollapsible(2, False)
        self._splitter = splitter
        main_layout.addWidget(self._splitter)

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
        overall_layout.addWidget(self._splitter, 1)
        overall_layout.addWidget(self.scan_progress_bar)
        overall_layout.addWidget(self.playback_bar)
        self.setCentralWidget(overall)

        self.add_folder_btn.clicked.connect(self._add_folder)
        self.refresh_btn.clicked.connect(self._refresh_library)
        self.folder_tree_widget.itemClicked.connect(self._on_folder_clicked)
        self.folder_tree_widget.customContextMenuRequested.connect(self._on_folder_context_menu)
        self.search_input.textChanged.connect(self.search_ctrl.on_text_changed)
        self.track_table_widget.itemDoubleClicked.connect(self._on_track_double_clicked)
        self.track_table_widget.itemSelectionChanged.connect(self._on_track_selected)
        self.track_table_widget.installEventFilter(self)
        self.category_input.returnPressed.connect(self._on_add_category_input)
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

    def _on_write_failed(self, file_path: str, msg: str) -> None:
        self.statusBar().showMessage(
            f"Failed to save categories for {os.path.basename(file_path)}: {msg}", 5000
        )

    def _load_library(self):
        self._reassociate_volumes()
        folders = self.library.get_folders()
        populate_folder_tree(self.folder_tree_widget, folders)

        if folders:
            folder_width = get_folder_width(self.folder_tree_widget, folders)
            self.folder_tree_widget.setColumnWidth(0, folder_width)
            self._splitter.setSizes([folder_width + 20, 500, 280])

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
        if self._is_scanning():
            return

        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if not folder:
            return

        if not os.access(folder, os.W_OK):
            QMessageBox.warning(
                self,
                "Read-Only Folder",
                "This folder is read-only. MonoVault requires write access to store metadata.",
            )
            return

        self.library.add_folder(folder)
        self._register_volume(folder)
        self._load_library()

    def _refresh_library(self):
        if self._is_scanning():
            return
        folders = self.library.get_folders()
        self.library.clear()
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

        if self._scan_announce_done:
            self._scan_announce_done = False
            QMessageBox.information(self, "Refresh Complete", "Library has been refreshed.")

    def _on_scan_cancel_clicked(self) -> None:
        if self._scan_worker is not None:
            self._scan_worker.cancel()
            self.scan_status_label.setText("Cancelling...")

    def _on_folder_clicked(self, item, column):
        pass

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
            self._load_library()

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

    def _on_search_results(self, tracks: list[Track]) -> None:
        self.all_tracks = tracks
        self.track_table_manager.populate(self.all_tracks)
        self.playback_ctrl.set_track_list(self.all_tracks)

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
        category = self.category_input.text().strip()
        if category:
            self.category_ctrl.add_category(category)
            self.category_input.clear()

    def _on_categories_changed(self, track: Track) -> None:
        update_categories(track, self.categories_layout, self._on_remove_category)
        self.track_table_manager.update_track(track)

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
        return super().eventFilter(obj, event)

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
