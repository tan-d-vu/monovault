THEME = {
    "primary_bg": "#0A0A0A",
    "secondary_bg": "#1A1A1A",
    "accent": "#808080",
    "accent_hover": "#A0A0A0",
    "text_primary": "#E5E5E5",
    "text_secondary": "#999999",
    "border": "#333333",
    "success": "#666666",
    "warning": "#888888",
    "error": "#555555",
    "selected": "rgba(128, 128, 128, 0.2)",
    "hover": "rgba(255, 255, 255, 0.05)",
}

STYLESHEET = f"""
QMainWindow {{
    background-color: {THEME["primary_bg"]};
    color: {THEME["text_primary"]};
}}

QWidget {{
    background-color: {THEME["primary_bg"]};
    color: {THEME["text_primary"]};
}}

QTreeWidget, QTableWidget, QListWidget {{
    background-color: {THEME["secondary_bg"]};
    color: {THEME["text_primary"]};
    border: 1px solid {THEME["border"]};
    alternate-background-color: {THEME["primary_bg"]};
}}

QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
    background-color: {THEME["selected"]};
}}

QTreeWidget::item:hover, QTableWidget::item:hover, QListWidget::item:hover {{
    background-color: {THEME["hover"]};
}}

QHeaderView::section {{
    background-color: {THEME["secondary_bg"]};
    color: {THEME["text_primary"]};
    padding: 4px;
    border: 1px solid {THEME["border"]};
}}

QPushButton {{
    background-color: {THEME["accent"]};
    color: {THEME["text_primary"]};
    border: none;
    padding: 6px 12px;
    border-radius: 4px;
}}

QPushButton:hover {{
    background-color: {THEME["accent_hover"]};
}}

QPushButton:pressed {{
    background-color: {THEME["accent"]};
}}

QPushButton:disabled {{
    background-color: {THEME["border"]};
    color: {THEME["text_secondary"]};
}}

QLineEdit, QTextEdit {{
    background-color: {THEME["secondary_bg"]};
    color: {THEME["text_primary"]};
    border: 1px solid {THEME["border"]};
    padding: 6px;
    border-radius: 4px;
}}

QLineEdit:focus, QTextEdit:focus {{
    border: 1px solid {THEME["accent"]};
}}

QLabel {{
    background-color: transparent;
    color: {THEME["text_primary"]};
}}

QSlider::groove:horizontal {{
    background: {THEME["border"]};
    height: 4px;
}}

QSlider::handle:horizontal {{
    background: {THEME["accent"]};
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider::sub-page:horizontal {{
    background: {THEME["accent"]};
}}

QMenuBar {{
    background-color: {THEME["secondary_bg"]};
    color: {THEME["text_primary"]};
}}

QMenuBar::item:selected {{
    background-color: {THEME["hover"]};
}}

QMenu {{
    background-color: {THEME["secondary_bg"]};
    color: {THEME["text_primary"]};
    border: 1px solid {THEME["border"]};
}}

QMenu::item:selected {{
    background-color: {THEME["selected"]};
}}

QScrollBar:vertical {{
    background: {THEME["primary_bg"]};
    width: 10px;
}}

QScrollBar::handle:vertical {{
    background: {THEME["border"]};
    border-radius: 5px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {THEME["primary_bg"]};
    height: 10px;
}}

QScrollBar::handle:horizontal {{
    background: {THEME["border"]};
    border-radius: 5px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""
