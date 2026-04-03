import sys
import subprocess
import platform

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QFileDialog,
    QMessageBox,
    QMenu,
)
from PyQt6.QtCore import Qt, QEvent, QUrl
from PyQt6.QtGui import QDesktopServices

from .styles import STYLESHEET
from .panels import (
    create_folder_panel,
    create_track_table,
    create_details_panel,
    create_playback_bar,
    update_play_icon,
    update_track_details_ui,
    update_categories,
    update_suggestions,
    populate_track_table,
    populate_folder_tree,
    get_folder_width,
)
from ..core.library import LibraryManager
from ..core.library_store import LibraryStore
from ..core.scanner import Scanner
from ..core.playback import PlaybackEngine
from ..core.categorizer import Categorizer
from ..core.category_sources import ArtistCategorySource, SimilarCategoryCategorySource
from ..core.events import EventBus
from ..models.track import Track
from .controllers import PlaybackController, SearchController, CategoryController


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._bus = EventBus()
        self.library = LibraryManager()
        self.library_store = LibraryStore()
        self.scanner = Scanner(library_store=self.library_store)
        self.playback_engine = PlaybackEngine()

        self.categorizer = Categorizer(
            self.library,
            sources=[
                ArtistCategorySource(self.library),
                SimilarCategoryCategorySource(self.library),
            ],
        )

        self.playback_ctrl = PlaybackController(
            self.playback_engine, bus=self._bus, parent=self
        )
        self.search_ctrl = SearchController(self.library, bus=self._bus, parent=self)
        self.category_ctrl = CategoryController(
            self.categorizer, bus=self._bus, parent=self
        )

        self.all_tracks: list[Track] = []

        self._setup_ui()
        self._connect_controllers()
        self._subscribe_events()
        self._load_library()

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
        self.track_table_panel, self.search_input, self.track_table_widget = (
            create_track_table()
        )
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

        overall = QWidget()
        overall_layout = QVBoxLayout(overall)
        overall_layout.setContentsMargins(4, 4, 4, 4)
        overall_layout.setSpacing(4)
        overall_layout.addWidget(self._splitter, 1)
        overall_layout.addWidget(self.playback_bar)
        self.setCentralWidget(overall)

        self.add_folder_btn.clicked.connect(self._add_folder)
        self.refresh_btn.clicked.connect(self._refresh_library)
        self.folder_tree_widget.itemClicked.connect(self._on_folder_clicked)
        self.folder_tree_widget.customContextMenuRequested.connect(
            self._on_folder_context_menu
        )
        self.search_input.textChanged.connect(self.search_ctrl.on_text_changed)
        self.track_table_widget.itemDoubleClicked.connect(self._on_track_double_clicked)
        self.track_table_widget.itemSelectionChanged.connect(self._on_track_selected)
        self.track_table_widget.installEventFilter(self)
        self.category_input.returnPressed.connect(self._on_add_category_input)

    def _connect_controllers(self):
        self.playback_ctrl.now_playing_changed.connect(self.now_playing_label.setText)
        self.playback_ctrl.play_state_changed.connect(self._update_play_icon)
        self.playback_ctrl.time_display_changed.connect(self.time_label.setText)
        self.playback_ctrl.slider_position_changed.connect(
            self.position_slider.setValue
        )

        self.play_btn.clicked.connect(self.playback_ctrl.toggle_playback)
        self.position_slider.sliderMoved.connect(self.playback_ctrl.seek)
        self.volume_slider.sliderMoved.connect(self.playback_ctrl.set_volume)

        self.search_ctrl.results_changed.connect(self._on_search_results)

        self.category_ctrl.categories_changed.connect(self._on_categories_changed)
        self.category_ctrl.suggestions_changed.connect(self._on_suggestions_changed)
        self.category_ctrl.track_details_changed.connect(self._on_track_details_changed)

    def _subscribe_events(self):
        from ..core.events import CategoriesChanged

        self._bus.subscribe(CategoriesChanged, self._on_categories_event)

    def _on_categories_event(self, event):
        self._refresh_track_in_table(event.track)

    def _load_library(self):
        folders = self.library.get_folders()
        populate_folder_tree(self.folder_tree_widget, folders)

        if folders:
            folder_width = get_folder_width(self.folder_tree_widget, folders)
            self.folder_tree_widget.setColumnWidth(0, folder_width)
            self._splitter.setSizes([folder_width + 20, 500, 280])

        for folder in folders:
            self._scan_folder(folder)
        self._load_tracks()

    def _load_tracks(self):
        self.all_tracks = self.library.get_all_tracks()
        self.playback_ctrl.set_track_list(self.all_tracks)
        populate_track_table(self.track_table_widget, self.all_tracks)
        if self.all_tracks:
            self.track_table_widget.selectRow(0)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if folder:
            self.library.add_folder(folder)
            self._load_library()
            self._scan_folder(folder)

    def _scan_folder(self, folder_path: str):
        tracks = self.scanner.scan_folder(folder_path)
        for track in tracks:
            self.library.add_track(track)
        self._load_tracks()

    def _refresh_library(self):
        folders = self.library.get_folders()
        self.library.clear()
        for folder in folders:
            self._scan_folder(folder)
        QMessageBox.information(self, "Refresh Complete", "Library has been refreshed.")

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
        reply = QMessageBox.question(
            self,
            "Remove Folder",
            f"Remove '{folder}' from library?\nThis will remove all tracks from this folder.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.library.remove_folder(folder)
            self._load_library()
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

    def _on_search_results(self, tracks: list[Track]) -> None:
        self.all_tracks = tracks
        populate_track_table(self.track_table_widget, self.all_tracks)
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
                if self.playback_ctrl.current_track == None:
                    self.now_playing_label.setText("{} - {}".format(track.title, track.artist))
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
        self._refresh_track_in_table(track)

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

    def _refresh_track_in_table(self, track: Track):
        for i in range(self.track_table_widget.rowCount()):
            item = self.track_table_widget.item(i, 0)
            stored = item.data(Qt.ItemDataRole.UserRole) if item else None
            if stored and stored.id == track.id:
                self.track_table_widget.item(i, 4).setText(" ".join(track.categories))
                for col in range(6):
                    item = self.track_table_widget.item(i, col)
                    if item:
                        item.setData(Qt.ItemDataRole.UserRole, track)
                break

    def closeEvent(self, event):
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
