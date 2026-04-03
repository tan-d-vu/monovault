"""UI panels — folder tree, track table, details panel, playback bar."""

from PyQt6.QtWidgets import (
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
    QHeaderView,
    QAbstractItemView,
    QScrollArea,
    QSizePolicy,
    QStyle,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics, QIcon, QPixmap, QImage

from .styles import THEME
from .widgets import CategoryPill, SuggestionButton
from ..models.track import Track


def create_folder_panel() -> tuple[QWidget, QTreeWidget, QPushButton, QPushButton]:
    panel = QFrame()
    panel.setFrameStyle(QFrame.Shape.NoFrame)
    panel.setMinimumHeight(150)
    panel.setStyleSheet(f"background-color: {THEME['secondary_bg']};")

    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(4)

    folder_tree_widget = QTreeWidget()
    folder_tree_widget.setHeaderHidden(True)
    folder_tree_widget.setAlternatingRowColors(True)
    folder_tree_widget.setIndentation(0)
    folder_tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    folder_tree_widget.header().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
    layout.addWidget(folder_tree_widget)

    add_folder_btn = QPushButton("Add Folder")
    add_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    add_folder_btn.setStyleSheet(f"border: 1px solid {THEME['border']}; padding: 6px;")

    refresh_btn = QPushButton("Refresh")
    refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    refresh_btn.setStyleSheet(f"border: 1px solid {THEME['border']}; padding: 6px;")

    button_layout = QHBoxLayout()
    button_layout.addWidget(add_folder_btn, 1)
    button_layout.addWidget(refresh_btn, 1)
    layout.addLayout(button_layout)

    return panel, folder_tree_widget, add_folder_btn, refresh_btn


def create_track_table() -> tuple[QWidget, QLineEdit, QTableWidget]:
    panel = QFrame()
    panel.setFrameStyle(QFrame.Shape.NoFrame)

    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    search_input = QLineEdit()
    search_input.setPlaceholderText("Search tracks...")
    layout.addWidget(search_input)

    track_table_widget = QTableWidget()
    track_table_widget.setColumnCount(6)
    track_table_widget.setHorizontalHeaderLabels(
        ["#", "Title", "Artist", "Duration", "Comments", "Added"]
    )
    track_table_widget.setSelectionBehavior(
        QAbstractItemView.SelectionBehavior.SelectRows
    )
    track_table_widget.setSelectionMode(
        QAbstractItemView.SelectionMode.ExtendedSelection
    )
    track_table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    track_table_widget.setAlternatingRowColors(True)
    track_table_widget.setSortingEnabled(True)
    track_table_widget.horizontalHeader().setStretchLastSection(False)

    header = track_table_widget.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

    track_table_widget.verticalHeader().hide()
    layout.addWidget(track_table_widget)

    return panel, search_input, track_table_widget


def create_details_panel() -> tuple[
    QWidget,
    QLabel,
    QLabel,
    QLabel,
    QLabel,
    QLineEdit,
    QLabel,
    QLabel,
    QVBoxLayout,
    QVBoxLayout,
]:
    panel = QFrame()
    panel.setFrameStyle(QFrame.Shape.NoFrame)
    panel.setStyleSheet(f"background-color: {THEME['secondary_bg']};")

    layout = QVBoxLayout(panel)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(12)

    album_art_label = QLabel()
    album_art_label.setFixedSize(300, 300)
    album_art_label.setStyleSheet(
        f"background-color: {THEME['border']}; border-radius: 4px;"
    )
    album_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(album_art_label, 0, Qt.AlignmentFlag.AlignCenter)

    track_title = QLabel("No track selected")
    track_title.setStyleSheet("font-size: 14px; font-weight: bold;")
    layout.addWidget(track_title)

    track_info = QLabel("")
    track_info.setStyleSheet(f"color: {THEME['text_secondary']};")
    layout.addWidget(track_info)

    track_date_added = QLabel("")
    track_date_added.setStyleSheet(f"color: {THEME['text_secondary']};")
    track_date_added.hide()
    layout.addWidget(track_date_added)

    categories_header = QLabel("Categories")
    categories_header.setStyleSheet(
        f"font-weight: bold; color: {THEME['text_secondary']};"
    )
    layout.addWidget(categories_header)

    categories_scroll = QScrollArea()
    categories_scroll.setWidgetResizable(True)
    categories_scroll.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    categories_scroll.setStyleSheet("""
        QScrollArea {
            border: none;
            background: transparent;
        }
    """)
    categories_scroll.setAlignment(Qt.AlignmentFlag.AlignTop)

    categories_container = QWidget()
    categories_container.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
    )
    categories_layout = QVBoxLayout(categories_container)
    categories_layout.setContentsMargins(0, 0, 0, 0)
    categories_layout.setSpacing(2)
    categories_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    categories_scroll.setWidget(categories_container)
    layout.addWidget(categories_scroll)

    category_input = QLineEdit()
    category_input.setPlaceholderText("Add category...")
    layout.addWidget(category_input)

    suggestions_header = QLabel("Suggested Categories")
    suggestions_header.setStyleSheet(
        f"font-weight: bold; color: {THEME['text_secondary']};"
    )
    layout.addWidget(suggestions_header)

    suggestions_container = QWidget()
    suggestions_layout = QVBoxLayout(suggestions_container)
    suggestions_layout.setContentsMargins(0, 0, 0, 0)
    suggestions_layout.setSpacing(4)
    layout.addWidget(suggestions_container)

    layout.addStretch()

    return (
        panel,
        album_art_label,
        track_title,
        track_info,
        track_date_added,
        category_input,
        suggestions_header,
        suggestions_container,
        categories_layout,
        suggestions_layout,
    )


def create_playback_bar() -> tuple[
    QWidget, QLabel, QPushButton, QSlider, QLabel, QSlider
]:
    bar = QFrame()
    bar.setFixedHeight(50)
    bar.setStyleSheet(
        f"background-color: {THEME['secondary_bg']}; border-top: 1px solid {THEME['border']};"
    )

    layout = QHBoxLayout(bar)
    layout.setContentsMargins(12, 8, 12, 8)
    layout.setSpacing(12)

    now_playing_label = QLabel("No track playing")
    now_playing_label.setStyleSheet(f"color: {THEME['text_secondary']};")
    now_playing_label.setFixedWidth(200)
    layout.addWidget(now_playing_label)

    play_btn = QPushButton()
    play_btn.setFixedSize(36, 36)
    play_btn.setStyleSheet(
        "QPushButton {"
        "  background-color: #1A1A1A;"
        "  border: 2px solid #444444;"
        ""
        "}"
        "QPushButton:hover {"
        "  background-color: #333333;"
        "}"
    )
    
    update_play_icon(play_btn, False)

    layout.addWidget(play_btn)

    position_slider = QSlider(Qt.Orientation.Horizontal)
    position_slider.setRange(0, 1000)
    position_slider.setValue(0)
    position_slider.setTracking(True)
    layout.addWidget(position_slider)

    time_label = QLabel("00:00 / 00:00")
    time_label.setFixedWidth(100)
    layout.addWidget(time_label)

    layout.addStretch()

    volume_icon = QLabel("🔊")
    layout.addWidget(volume_icon)

    volume_slider = QSlider(Qt.Orientation.Horizontal)
    volume_slider.setRange(0, 100)
    volume_slider.setValue(70)
    volume_slider.setFixedWidth(80)
    layout.addWidget(volume_slider)

    return bar, now_playing_label, play_btn, position_slider, time_label, volume_slider


def update_play_icon(play_btn: QPushButton, is_playing: bool) -> None:
    style = play_btn.style()
    std_icon = style.standardIcon(
        QStyle.StandardPixmap.SP_MediaPause
        if is_playing
        else QStyle.StandardPixmap.SP_MediaPlay
    )
    pixmap = std_icon.pixmap(24, 24)
    img = pixmap.toImage()
    for x in range(img.width()):
        for y in range(img.height()):
            pixel = img.pixel(x, y)
            if pixel != 0:
                img.setPixel(x, y, 0xFFFFFFFF)
    play_btn.setIcon(QIcon(QPixmap.fromImage(img)))


def update_track_details_ui(
    track: Track,
    track_title: QLabel,
    track_info: QLabel,
    track_date_added: QLabel,
    album_art_label: QLabel,
) -> None:
    track_title.setText(track.title)
    track_info.setText(f"{track.artist} - {track.album} ({track.duration_formatted})")

    if track.date_added:
        track_date_added.setText(f"Added: {track.date_added}")
        track_date_added.show()
    else:
        track_date_added.hide()

    if track.album_art:
        qimg = QImage.fromData(track.album_art)
        if not qimg.isNull():
            pixmap = QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(
                300,
                300,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            album_art_label.setPixmap(scaled)
        else:
            album_art_label.clear()
    else:
        album_art_label.clear()


def update_categories(
    track: Track, categories_layout: QVBoxLayout, on_remove=None
) -> None:
    while categories_layout.count():
        child = categories_layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()

    for cat in track.categories:
        pill = CategoryPill(cat)
        if on_remove:
            pill.remove_clicked.connect(on_remove)
        categories_layout.addWidget(pill)

    track.comments = " ".join(track.categories)


def update_suggestions(
    suggestions: list,
    suggestions_header: QLabel,
    suggestions_container: QWidget,
    suggestions_layout: QVBoxLayout,
    on_click,
) -> None:
    while suggestions_layout.count():
        child = suggestions_layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()

    if not suggestions:
        suggestions_header.hide()
        suggestions_container.hide()
    else:
        suggestions_header.show()
        suggestions_container.show()
        for cat, source in suggestions:
            btn = SuggestionButton(cat, source)
            btn.clicked_with_source.connect(on_click)
            suggestions_layout.addWidget(btn)


def populate_track_table(table: QTableWidget, tracks: list[Track]) -> None:
    table.setRowCount(len(tracks))

    for i, track in enumerate(tracks):
        num_item = QTableWidgetItem(str(i + 1))
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(i, 0, num_item)

        table.setItem(i, 1, QTableWidgetItem(track.title))
        table.setItem(i, 2, QTableWidgetItem(track.artist))

        dur_item = QTableWidgetItem(track.duration_formatted)
        dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(i, 3, dur_item)

        table.setItem(i, 4, QTableWidgetItem(track.comments or ""))

        added_item = QTableWidgetItem(track.date_added or "")
        added_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(i, 5, added_item)

        for col in range(6):
            item = table.item(i, col)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, track)

    for col in range(6):
        if col == 4:
            continue
        max_width = 0
        for i in range(len(tracks)):
            item = table.item(i, col)
            if item:
                width = table.fontMetrics().boundingRect(item.text()).width()
                max_width = max(max_width, width)
        if max_width > 0:
            table.setColumnWidth(col, max_width)


def populate_folder_tree(tree: QTreeWidget, folders: list[str]) -> None:
    tree.clear()
    for folder in folders:
        item = QTreeWidgetItem([folder])
        item.setCheckState(0, Qt.CheckState.Checked)
        item.setData(0, Qt.ItemDataRole.UserRole, folder)
        tree.addTopLevelItem(item)


def get_folder_width(tree: QTreeWidget, folders: list[str]) -> int:
    if not folders:
        return 200
    font = tree.font()
    metrics = QFontMetrics(font)
    max_width = max(metrics.horizontalAdvance(f) for f in folders)
    return max_width + 40
