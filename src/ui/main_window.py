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
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QStyle,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QPoint, QEvent
from PyQt6.QtGui import QAction, QMouseEvent, QKeyEvent, QFontMetrics, QIcon

from .styles import THEME, STYLESHEET
from .widgets import CategoryPill, SuggestionButton
from ..core.library import LibraryManager
from ..core.library_store import LibraryStore
from ..core.scanner import Scanner
from ..core.playback import PlaybackEngine
from ..core.categorizer import Categorizer
from ..core.metadata import write_comments
from ..models.track import Track


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.library = LibraryManager()
        self.library_store = LibraryStore()
        self.scanner = Scanner(library_store=self.library_store)
        self.playback = PlaybackEngine()
        self.categorizer = Categorizer(self.library)

        self.all_tracks: list[Track] = []
        self.current_track: Optional[Track] = None
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._do_search)
        self._is_seeking = False

        self._splitter = None

        self._setup_ui()
        self._load_library()

    def _setup_ui(self):
        self.setWindowTitle("MonoVault")
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
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setHandleWidth(1)
        self._splitter = splitter

        main_layout.addWidget(self._splitter)

        self.playback_bar = self._create_playback_bar()

        overall = QWidget()
        overall_layout = QVBoxLayout(overall)
        overall_layout.setContentsMargins(4, 4, 4, 4)
        overall_layout.setSpacing(4)
        overall_layout.addWidget(self._splitter, 1)
        overall_layout.addWidget(self.playback_bar)

        self.setCentralWidget(overall)

    def _create_menu(self):
        return  # No menu for now

    def _create_folder_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.NoFrame)
        panel.setMinimumHeight(150)
        panel.setStyleSheet(f"background-color: {THEME['secondary_bg']};")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.folder_tree_widget = QTreeWidget()
        self.folder_tree_widget.setHeaderHidden(True)
        self.folder_tree_widget.setAlternatingRowColors(True)
        self.folder_tree_widget.setIndentation(0)
        self.folder_tree_widget.itemClicked.connect(self._on_folder_clicked)
        self.folder_tree_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.folder_tree_widget.customContextMenuRequested.connect(
            self._on_folder_context_menu
        )
        self.folder_tree_widget.header().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed
        )
        layout.addWidget(self.folder_tree_widget)

        self.add_folder_btn = QPushButton("Add Folder")
        self.add_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_folder_btn.setStyleSheet(
            f"border: 1px solid {THEME['border']}; padding: 6px;"
        )
        self.add_folder_btn.clicked.connect(self._add_folder)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet(
            f"border: 1px solid {THEME['border']}; padding: 6px;"
        )
        self.refresh_btn.clicked.connect(self._refresh_library)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_folder_btn, 1)
        button_layout.addWidget(self.refresh_btn, 1)
        layout.addLayout(button_layout)

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
        self.track_table_widget.setColumnCount(6)
        self.track_table_widget.setHorizontalHeaderLabels(
            ["#", "Title", "Artist", "Duration", "Comments", "Added"]
        )
        self.track_table_widget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.track_table_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.track_table_widget.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.track_table_widget.setAlternatingRowColors(True)
        self.track_table_widget.setSortingEnabled(True)
        self.track_table_widget.horizontalHeader().setStretchLastSection(False)
        self.track_table_widget.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.track_table_widget.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.track_table_widget.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.track_table_widget.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.track_table_widget.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.track_table_widget.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        self.track_table_widget.verticalHeader().hide()
        self.track_table_widget.itemDoubleClicked.connect(self._on_track_double_clicked)
        self.track_table_widget.itemSelectionChanged.connect(self._on_track_selected)
        self.track_table_widget.installEventFilter(self)
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

        self.track_date_added = QLabel("")
        self.track_date_added.setStyleSheet(f"color: {THEME['text_secondary']};")
        self.track_date_added.hide()
        layout.addWidget(self.track_date_added)

        categories_header = QLabel("Categories")
        categories_header.setStyleSheet(
            f"font-weight: bold; color: {THEME['text_secondary']};"
        )
        layout.addWidget(categories_header)

        self.categories_scroll = QScrollArea()
        self.categories_scroll.setWidgetResizable(True)
        self.categories_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.categories_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
        """)
        self.categories_scroll.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.categories_container = QWidget()
        self.categories_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.categories_layout = QVBoxLayout(self.categories_container)
        self.categories_layout.setContentsMargins(0, 0, 0, 0)
        self.categories_layout.setSpacing(2)
        self.categories_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.categories_scroll.setWidget(self.categories_container)
        layout.addWidget(self.categories_scroll)

        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("Add category...")
        self.category_input.returnPressed.connect(self._add_category)
        layout.addWidget(self.category_input)

        self.suggestions_header = QLabel("Suggested Categories")
        self.suggestions_header.setStyleSheet(
            f"font-weight: bold; color: {THEME['text_secondary']};"
        )
        layout.addWidget(self.suggestions_header)

        self.suggestions_container = QWidget()
        self.suggestions_layout = QVBoxLayout(self.suggestions_container)
        self.suggestions_layout.setContentsMargins(0, 0, 0, 0)
        self.suggestions_layout.setSpacing(4)
        layout.addWidget(self.suggestions_container)

        layout.addStretch()

        return panel

    def _create_playback_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(50)
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

        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(36, 36)
        self.play_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #1A1A1A;"
            "  border: 2px solid #444444;"
            ""
            "}"
            "QPushButton:hover {"
            "  background-color: #333333;"
            "}"
        )
        self.play_btn.clicked.connect(self._toggle_playback)
        self._update_play_icon(False)
        layout.addWidget(self.play_btn)

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

        if folders:
            font = self.folder_tree_widget.font()
            metrics = QFontMetrics(font)
            max_width = max(metrics.horizontalAdvance(f) for f in folders)
            folder_width = max_width + 40
            self.folder_tree_widget.setColumnWidth(0, folder_width)
            self._splitter.setSizes([folder_width + 20, 500, 280])

        for folder in folders:
            self._scan_folder(folder)
        self._load_tracks()

    def _load_tracks(self):
        self.all_tracks = self.library.get_all_tracks()
        self._populate_track_table(self.all_tracks)
        if self.all_tracks:
            self.track_table_widget.selectRow(0)

    def _populate_track_table(self, tracks: list[Track]):
        self.track_table_widget.setRowCount(len(tracks))

        for i, track in enumerate(tracks):
            num_item = QTableWidgetItem(str(i + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.track_table_widget.setItem(i, 0, num_item)

            self.track_table_widget.setItem(i, 1, QTableWidgetItem(track.title))
            self.track_table_widget.setItem(i, 2, QTableWidgetItem(track.artist))

            dur_item = QTableWidgetItem(track.duration_formatted)
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.track_table_widget.setItem(i, 3, dur_item)

            self.track_table_widget.setItem(
                i, 4, QTableWidgetItem(track.comments or "")
            )

            added_item = QTableWidgetItem(track.date_added or "")
            added_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.track_table_widget.setItem(i, 5, added_item)

            for col in range(6):
                item = self.track_table_widget.item(i, col)
                if item:
                    item.setData(Qt.ItemDataRole.UserRole, track)

        for col in range(6):
            if col == 4:
                continue
            max_width = 0
            for i in range(len(tracks)):
                item = self.track_table_widget.item(i, col)
                if item:
                    width = (
                        self.track_table_widget.fontMetrics()
                        .boundingRect(item.text())
                        .width()
                    )
                    max_width = max(max_width, width)
            if max_width > 0:
                self.track_table_widget.setColumnWidth(col, max_width)

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
        QTimer.singleShot(100, self._sync_play_icon)

    def _toggle_playback(self):
        if self.playback.is_playing():
            self.playback.pause()
            self._update_play_icon(False)
        elif self.current_track:
            self.playback.play()
            self._update_play_icon(True)

    def _update_play_icon(self, is_playing: bool):
        from PyQt6.QtGui import QPixmap, QIcon, QImage

        style = self.play_btn.style()
        if is_playing:
            std_icon = QStyle.StandardPixmap.SP_MediaPause
        else:
            std_icon = QStyle.StandardPixmap.SP_MediaPlay

        pixmap = style.standardIcon(std_icon).pixmap(24, 24)

        img = pixmap.toImage()
        for x in range(img.width()):
            for y in range(img.height()):
                pixel = img.pixel(x, y)
                if pixel != 0:
                    img.setPixel(x, y, 0xFFFFFFFF)

        self.play_btn.setIcon(QIcon(QPixmap.fromImage(img)))

    def _sync_play_icon(self):
        self._update_play_icon(self.playback.is_playing())

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
            self._update_play_icon(True)
        else:
            self._update_play_icon(False)

    def _show_track_details(self, track: Track):
        self.current_track = track
        self.track_title.setText(track.title)
        self.track_info.setText(
            f"{track.artist} - {track.album} ({track.duration_formatted})"
        )

        if track.date_added:
            self.track_date_added.setText(f"Added: {track.date_added}")
            self.track_date_added.show()
        else:
            self.track_date_added.hide()

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

        track.comments = " ".join(track.categories)

    def _update_suggestions(self, track: Track):
        while self.suggestions_layout.count():
            child = self.suggestions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        suggestions = self.categorizer.get_suggestions(track)
        if not suggestions:
            self.suggestions_header.hide()
            self.suggestions_container.hide()
        else:
            self.suggestions_header.show()
            self.suggestions_container.show()
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
                comments = " ".join(track.categories)
                self.track_table_widget.item(i, 4).setText(comments)
                for col in range(6):
                    item = self.track_table_widget.item(i, col)
                    if item:
                        item.setData(Qt.ItemDataRole.UserRole, track)
                break

    def closeEvent(self, event):
        self.playback.stop()
        event.accept()

    def eventFilter(self, obj, event):
        if obj == self.track_table_widget and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return:
                self._play_selected_track()
                return True
        return super().eventFilter(obj, event)

    def _play_selected_track(self):
        selected = self.track_table_widget.selectedItems()
        if selected:
            row = selected[0].row()
            track = self.track_table_widget.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if track:
                self._play_track(track)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
