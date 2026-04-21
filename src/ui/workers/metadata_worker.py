"""Background worker for writing category metadata to disk."""

import logging

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from ...core.metadata import write_comment

logger = logging.getLogger(__name__)


class MetadataWriteSignals(QObject):
    finished = pyqtSignal(str, bool, str)  # file_path, success, error_message


class MetadataWriteWorker(QRunnable):
    def __init__(
        self,
        file_path: str,
        categories: list[str],
        signals: MetadataWriteSignals | None = None,
    ) -> None:
        super().__init__()
        self._file_path = file_path
        self._categories = categories
        self.signals = signals or MetadataWriteSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        error_msg = ""
        try:
            success = write_comment(self._file_path, self._categories)
            self.signals.finished.emit(self._file_path, success, error_msg)
        except OSError as e:
            error_msg = str(e)
            logger.error("Failed to write metadata for %s: %s", self._file_path, e)
            self.signals.finished.emit(self._file_path, False, error_msg)
        except (
            Exception
        ) as e:  # broad catch intentional: background thread must never crash silently
            error_msg = str(e)
            logger.error("Unexpected error writing metadata for %s: %s", self._file_path, e)
            self.signals.finished.emit(self._file_path, False, error_msg)
