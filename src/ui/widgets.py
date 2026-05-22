from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QWidget

from .styles import THEME


class SeekSlider(QSlider):
    """Horizontal seek slider that jumps directly to the clicked position.

    The default QSlider steps by pageStep on click (rather than jumping).
    This subclass overrides mouse handling so both clicks and drags move
    the handle — and emit sliderMoved — to the exact cursor position.
    """

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setValue(self._value_at(event.position().x()))
            self.sliderMoved.emit(self.value())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.setValue(self._value_at(event.position().x()))
            self.sliderMoved.emit(self.value())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def _value_at(self, x: float) -> int:
        ratio = max(0.0, min(1.0, x / max(self.width(), 1)))
        return int(self.minimum() + ratio * (self.maximum() - self.minimum()))


class ClickableLabel(QLabel):
    """QLabel that emits clicked() on left mouse press."""

    clicked = pyqtSignal()

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CategoryPill(QWidget):
    remove_clicked = pyqtSignal(str)

    def __init__(self, category: str, parent=None):
        super().__init__(parent)
        self.category = category
        self._setup_ui()

    def _setup_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {THEME["accent"]};
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
                padding: 4px 8px;}}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(4)

        label = QLabel(self.category)
        label.setStyleSheet(f"color: {THEME['text_primary']}; background: transparent;")
        layout.addWidget(label)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {THEME["text_primary"]};
                border: none;
                font-size: 14px;
                padding: 0;
            }}
            QPushButton:hover {{
                color: {THEME["error"]};
            }}
        """)
        close_btn.clicked.connect(lambda: self.remove_clicked.emit(self.category))
        layout.addWidget(close_btn)


class SuggestionButton(QPushButton):
    clicked_with_source = pyqtSignal(str, str)

    def __init__(self, category: str, source: str, parent=None):
        super().__init__(category, parent)
        self.category = category
        self.source = source
        self.setToolTip(f"Source: {source}")
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["secondary_bg"]};
                color: {THEME["text_secondary"]};
                border: 1px solid {THEME["border"]};
                padding: 4px 8px;
                border-radius: 4px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {THEME["hover"]};
                color: {THEME["text_primary"]};
                border-color: {THEME["accent"]};
            }}
        """)
        self.clicked.connect(lambda: self.clicked_with_source.emit(self.category, self.source))


class Toast(QLabel):
    DEFAULT_DURATION_MS = 4000
    MARGIN = 16

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {THEME["secondary_bg"]};
                color: {THEME["text_primary"]};
                border: 1px solid {THEME["error"]};
                border-radius: 6px;
                padding: 10px 14px;
            }}
        """)
        self.setMinimumWidth(240)
        self.setMaximumWidth(360)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, duration_ms: int = DEFAULT_DURATION_MS) -> None:
        self.setText(text)
        self.adjustSize()
        self._reposition()
        self.raise_()
        self.show()
        self._timer.start(duration_ms)

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = parent.width() - self.width() - self.MARGIN
        y = parent.height() - self.height() - self.MARGIN
        self.move(max(self.MARGIN, x), max(self.MARGIN, y))
