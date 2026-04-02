import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QLabel,
    QPushButton,
    QSlider,
    QFrame,
    QSplitter,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
    QMenu,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QAction, QMouseEvent

from .styles import THEME, STYLESHEET
from .widgets import CategoryPill, SuggestionButton
from ..core.library import LibraryManager
from ..core.scanner import Scanner
from ..core.playback import PlaybackEngine
from ..core.categorizer import Categorizer
from ..models.track import Track


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.library = LibraryManager()
        self.scanner = Scanner()
        self.playback = PlaybackEngine()
        self.categorizer = Categorizer(self.library)

        self.all_tracks: list[Track] = []
        self.current_track: Optional[Track] = None
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._do_search)
        self._is_seeking = False

        self._setup_ui()
        self._load_library()

    def _setup_ui(self):
        self.setWindowTitle("MusicVault")
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(STYLESHEET)

        self._create_menu()
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        self.folder_tree = self._create_folder_panel()
        self.track_table = self._create_track_table()
        self.details_panel = self._create_details_panel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.folder_tree)
        splitter.addWidget(self.track_table)
        splitter.addWidget(self.details_panel)
        splitter.setSizes([200, 500, 280])

        main_layout.addWidget(splitter)

        self.playback_bar = self._create_playback_bar()

        overall = QWidget()
        overall_layout = QVBoxLayout(overall)
        overall_layout.setContentsMargins(4, 4, 4, 4)
        overall_layout.setSpacing(4)
        overall_layout.addWidget(splitter)
        overall_layout.addWidget(self.playback_bar)

        self.setCentralWidget(overall)

    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        add_folder = QAction("Add Folder", self)
        add_folder.triggered.connect(self._add_folder)
        file_menu.addAction(add_folder)

        refresh = QAction("Refresh Library", self)
        refresh.triggered.connect(self._refresh_library)
        file_menu.addAction(refresh)

        file_menu.addSeparator()

        quit = QAction("Quit", self)
        quit.triggered.connect(self.close)
        file_menu.addAction(quit)

    def _create_folder_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.NoFrame)
        panel.setStyleSheet(f"background-color: {THEME['secondary_bg']};")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Folders")
        header.setStyleSheet(f"font-weight: bold; color: {THEME['text_secondary']};")
        layout.addWidget(header)

        self.folder_tree_widget = QTreeWidget()
        self.folder_tree_widget.setHeaderHidden(True)
        self.folder_tree_widget.setAlternatingRowColors(True)
        self.folder_tree_widget.itemClicked.connect(self._on_folder_clicked)
        self.folder_tree_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.folder_tree_widget.customContextMenuRequested.connect(
            self._on_folder_context_menu
        )
        layout.addWidget(self.folder_tree_widget)

        return panel

    def _create_track_table(self) -> QWidget:
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search tracks...")
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        self.track_table_widget = QTableWidget()
        self.track_table_widget.setColumnCount(5)
        self.track_table_widget.setHorizontalHeaderLabels(
            ["#", "Title", "Artist", "Album", "Duration"]
        )
        self.track_table_widget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.track_table_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.track_table_widget.setAlternatingRowColors(True)
        self.track_table_widget.horizontalHeader().setStretchLastSection(True)
        self.track_table_widget.verticalHeader().hide()
        self.track_table_widget.itemDoubleClicked.connect(self._on_track_double_clicked)
        self.track_table_widget.itemSelectionChanged.connect(self._on_track_selected)
        layout.addWidget(self.track_table_widget)

        return panel

    def _create_details_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.NoFrame)
        panel.setStyleSheet(f"background-color: {THEME['secondary_bg']};")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.album_art_label = QLabel()
        self.album_art_label.setFixedSize(200, 200)
        self.album_art_label.setStyleSheet(
            f"background-color: {THEME['border']}; border-radius: 4px;"
        )
        self.album_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.album_art_label, 0, Qt.AlignmentFlag.AlignCenter)

        self.track_title = QLabel("No track selected")
        self.track_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.track_title)

        self.track_info = QLabel("")
        self.track_info.setStyleSheet(f"color: {THEME['text_secondary']};")
        layout.addWidget(self.track_info)

        categories_header = QLabel("Categories")
        categories_header.setStyleSheet(
            f"font-weight: bold; color: {THEME['text_secondary']};"
        )
        layout.addWidget(categories_header)

        self.categories_container = QWidget()
        self.categories_layout = QVBoxLayout(self.categories_container)
        self.categories_layout.setContentsMargins(0, 0, 0, 0)
        self.categories_layout.setSpacing(4)
        layout.addWidget(self.categories_container)

        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("Add category...")
        self.category_input.returnPressed.connect(self._add_category)
        layout.addWidget(self.category_input)

        suggestions_header = QLabel("Suggested Categories")
        suggestions_header.setStyleSheet(
            f"font-weight: bold; color: {THEME['text_secondary']};"
        )
        layout.addWidget(suggestions_header)

        self.suggestions_container = QWidget()
        self.suggestions_layout = QVBoxLayout(self.suggestions_container)
        self.suggestions_layout.setContentsMargins(0, 0, 0, 0)
        self.suggestions_layout.setSpacing(4)
        layout.addWidget(self.suggestions_container)

        layout.addStretch()

        return panel

    def _create_playback_bar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet(
            f"background-color: {THEME['secondary_bg']}; border-top: 1px solid {THEME['border']};"
        )

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self.now_playing_label = QLabel("No track playing")
        self.now_playing_label.setStyleSheet(f"color: {THEME['text_secondary']};")
        self.now_playing_label.setFixedWidth(200)
        layout.addWidget(self.now_playing_label)

        self.prev_btn = QPushButton("<<")
        self.prev_btn.setFixedWidth(40)
        self.prev_btn.clicked.connect(self._prev_track)
        layout.addWidget(self.prev_btn)

        self.play_btn = QPushButton("Play")
        self.play_btn.setFixedWidth(60)
        self.play_btn.clicked.connect(self._toggle_playback)
        layout.addWidget(self.play_btn)

        self.next_btn = QPushButton(">>")
        self.next_btn.setFixedWidth(40)
        self.next_btn.clicked.connect(self._next_track)
        layout.addWidget(self.next_btn)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.setValue(0)
        self.position_slider.setTracking(True)
        self.position_slider.sliderMoved.connect(self._on_seek)
        layout.addWidget(self.position_slider)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFixedWidth(100)
        layout.addWidget(self.time_label)

        layout.addStretch()

        self.volume_icon = QLabel("🔊")
        layout.addWidget(self.volume_icon)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.sliderMoved.connect(self._on_volume_changed)
        layout.addWidget(self.volume_slider)

        self.playback.position_changed.connect(self._on_position_changed)
        self.playback.duration_changed.connect(self._on_duration_changed)
        self.playback.playback_state_changed.connect(self._on_playback_state_changed)

        return bar

    def _load_library(self):
        self.folder_tree_widget.clear()
        folders = self.library.get_folders()

        for folder in folders:
            item = QTreeWidgetItem([folder])
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setData(0, Qt.ItemDataRole.UserRole, folder)
            self.folder_tree_widget.addTopLevelItem(item)

        for folder in folders:
            self._scan_folder(folder)
        self._load_tracks()

    def _load_tracks(self):
        self.all_tracks = self.library.get_all_tracks()
        self._populate_track_table(self.all_tracks)

    def _populate_track_table(self, tracks: list[Track]):
        self.track_table_widget.setRowCount(len(tracks))

        for i, track in enumerate(tracks):
            self.track_table_widget.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.track_table_widget.setItem(i, 1, QTableWidgetItem(track.title))
            self.track_table_widget.setItem(i, 2, QTableWidgetItem(track.artist))
            self.track_table_widget.setItem(i, 3, QTableWidgetItem(track.album))
            self.track_table_widget.setItem(
                i, 4, QTableWidgetItem(track.duration_formatted)
            )

            for col in range(5):
                item = self.track_table_widget.item(i, col)
                if item:
                    item.setData(Qt.ItemDataRole.UserRole, track)

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
        remove_action = menu.addAction("Remove Folder")
        action = menu.exec(self.folder_tree_widget.mapToGlobal(pos))
        if action == remove_action:
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

    def _on_search_changed(self, text):
        self.search_timer.start(1500)

    def _do_search(self):
        query = self.search_input.text().strip()
        if query:
            self.all_tracks = self.library.search(query)
        else:
            self.all_tracks = self.library.get_all_tracks()
        self._populate_track_table(self.all_tracks)

    def _on_track_double_clicked(self, item, column=None):
        row = item.row()
        track = self.track_table_widget.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if track:
            self._play_track(track)

    def _on_track_selected(self):
        selected = self.track_table_widget.selectedItems()
        if selected:
            row = selected[0].row()
            track = self.track_table_widget.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if track:
                self._show_track_details(track)

    def _play_track(self, track: Track):
        self.current_track = track
        self.playback.load_track(track.file_path)
        self.playback.play()
        self.now_playing_label.setText(f"{track.title} - {track.artist}")
        self.play_btn.setText("Pause")

    def _toggle_playback(self):
        if self.playback.is_playing():
            self.playback.pause()
            self.play_btn.setText("Play")
        elif self.current_track:
            self.playback.play()
            self.play_btn.setText("Pause")

    def _prev_track(self):
        if not self.all_tracks or not self.current_track:
            return
        try:
            idx = next(
                i
                for i, t in enumerate(self.all_tracks)
                if t.file_path == self.current_track.file_path
            )
            if idx > 0:
                self._play_track(self.all_tracks[idx - 1])
        except StopIteration:
            pass

    def _next_track(self):
        if not self.all_tracks or not self.current_track:
            return
        try:
            idx = next(
                i
                for i, t in enumerate(self.all_tracks)
                if t.file_path == self.current_track.file_path
            )
            if idx < len(self.all_tracks) - 1:
                self._play_track(self.all_tracks[idx + 1])
        except StopIteration:
            pass

    def _on_seek(self, position):
        if self._is_seeking:
            return
        self._is_seeking = True
        try:
            duration = self.playback.get_duration()
            if duration > 0:
                seek_pos = int(position / 1000 * duration)
                self.playback.seek(seek_pos)
        finally:
            self._is_seeking = False

    def _on_volume_changed(self, value):
        self.playback.set_volume(value)

    def _on_position_changed(self, position):
        if self._is_seeking:
            return
        self._is_seeking = True
        try:
            duration = self.playback.get_duration()
            if duration > 0:
                self.position_slider.setValue(int(position / duration * 1000))

            current_secs = position // 1000
            mins, secs = divmod(current_secs, 60)
            current_time = f"{mins:02d}:{secs:02d}"

            total_secs = duration // 1000
            mins, secs = divmod(total_secs, 60)
            total_time = f"{mins:02d}:{secs:02d}"

            self.time_label.setText(f"{current_time} / {total_time}")
        finally:
            self._is_seeking = False

    def _on_duration_changed(self, duration):
        self.position_slider.setValue(0)
        if duration > 0:
            total_secs = duration // 1000
            mins, secs = divmod(total_secs, 60)
            total_time = f"{mins:02d}:{secs:02d}"
            self.time_label.setText(f"00:00 / {total_time}")

    def _on_playback_state_changed(self, state):
        from PyQt6.QtMultimedia import QMediaPlayer

        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("Pause")
        else:
            self.play_btn.setText("Play")

    def _show_track_details(self, track: Track):
        self.current_track = track
        self.track_title.setText(track.title)
        self.track_info.setText(
            f"{track.artist} - {track.album} ({track.duration_formatted})"
        )

        if track.album_art:
            from PyQt6.QtGui import QPixmap, QImage

            qimg = QImage.fromData(track.album_art)
            if not qimg.isNull():
                pixmap = QPixmap.fromImage(qimg)
                scaled = pixmap.scaled(
                    200,
                    200,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.album_art_label.setPixmap(scaled)
            else:
                self.album_art_label.clear()
        else:
            self.album_art_label.clear()

        self._update_categories(track)
        self._update_suggestions(track)

    def _update_categories(self, track: Track):
        while self.categories_layout.count():
            child = self.categories_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for cat in track.categories:
            pill = CategoryPill(cat)
            pill.remove_clicked.connect(lambda c: self._remove_category(c))
            self.categories_layout.addWidget(pill)

    def _update_suggestions(self, track: Track):
        while self.suggestions_layout.count():
            child = self.suggestions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        suggestions = self.categorizer.get_suggestions(track)
        for cat, source in suggestions:
            btn = SuggestionButton(cat, source)
            btn.clicked_with_source.connect(self._on_suggestion_clicked)
            self.suggestions_layout.addWidget(btn)

    def _add_category(self):
        if not self.current_track:
            return
        category = self.category_input.text().strip()
        if category and self.categorizer.add_category(self.current_track, category):
            self._update_categories(self.current_track)
            self._update_suggestions(self.current_track)
            self.category_input.clear()
            self._refresh_track_in_table(self.current_track)

    def _remove_category(self, category: str):
        if not self.current_track:
            return
        if self.categorizer.remove_category(self.current_track, category):
            self._update_categories(self.current_track)
            self._update_suggestions(self.current_track)
            self._refresh_track_in_table(self.current_track)

    def _on_suggestion_clicked(self, category: str, source: str):
        if not self.current_track:
            return
        if self.categorizer.add_category(self.current_track, category):
            self._update_categories(self.current_track)
            self._update_suggestions(self.current_track)
            self._refresh_track_in_table(self.current_track)

    def _refresh_track_in_table(self, track: Track):
        for i in range(self.track_table_widget.rowCount()):
            item = self.track_table_widget.item(i, 0)
            stored = item.data(Qt.ItemDataRole.UserRole) if item else None
            if stored and stored.id == track.id:
                for col in range(5):
                    item = self.track_table_widget.item(i, col)
                    if item:
                        item.setData(Qt.ItemDataRole.UserRole, track)
                break

    def closeEvent(self, event):
        self.playback.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
