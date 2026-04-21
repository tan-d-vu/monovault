"""Format registry that dispatches to the correct parser by file extension."""

import logging
from pathlib import Path

from .base import BaseParser
from .flac_parser import FlacParser
from .mp3_parser import Mp3Parser

logger = logging.getLogger(__name__)


class MetadataRegistry:
    def __init__(self) -> None:
        self._parsers: list[BaseParser] = []

    def register(self, parser: BaseParser) -> None:
        self._parsers.append(parser)

    def get_parser(self, file_path: str) -> BaseParser | None:
        for parser in self._parsers:
            if parser.can_handle(file_path):
                return parser
        return None

    def supported_extensions(self) -> set[str]:
        result: set[str] = set()
        for parser in self._parsers:
            result |= parser.supported_extensions
        return result

    def is_supported(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.supported_extensions()


def create_default_registry() -> MetadataRegistry:
    registry = MetadataRegistry()
    registry.register(Mp3Parser())
    registry.register(FlacParser())
    return registry
