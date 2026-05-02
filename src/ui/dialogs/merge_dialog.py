from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QVBoxLayout,
)


class MergeDialog(QDialog):
    def __init__(self, sources: list[str], all_categories: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Merge Categories")
        self._target = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Merging these categories:"))

        sources_list = QListWidget()
        sources_list.addItems(sources)
        sources_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        sources_list.setMaximumHeight(120)
        layout.addWidget(sources_list)

        layout.addWidget(QLabel("Into target category:"))
        self._target_input = QLineEdit()
        completer = QCompleter(all_categories, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._target_input.setCompleter(completer)
        layout.addWidget(self._target_input)

        layout.addWidget(QLabel(
            "Tip: type an existing category name or a new one. Lowercase, no spaces."
        ))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        value = self._target_input.text().strip().lower()
        if not value or any(c.isspace() for c in value):
            return
        self._target = value
        self.accept()

    def target_value(self) -> str:
        return self._target
