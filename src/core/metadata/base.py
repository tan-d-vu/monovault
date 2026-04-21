"""Base class with shared validation and logging for metadata parsers."""

import logging
from pathlib import Path

import mutagen

logger = logging.getLogger(__name__)


class BaseParser:
    supported_extensions: set[str] = set()

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.supported_extensions

    def _load_audio(self, file_path: str) -> mutagen.FileType | None:
        path = Path(file_path)
        if not path.exists():
            logger.warning("File not found: %s", file_path)
            return None
        try:
            audio = mutagen.File(file_path)
            if audio is None:
                logger.warning("Mutagen returned None for: %s", file_path)
            return audio
        except mutagen.MutagenError as e:
            logger.error("Failed to load audio file %s: %s", file_path, e)
            return None

    def _safe_tag_get(self, tags: dict, key: str, default: str = "") -> str:
        value = tags.get(key)
        if value is None:
            return default
        if isinstance(value, list) and value:
            return str(value[0])
        return str(value)
