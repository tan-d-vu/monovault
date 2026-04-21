"""Metadata package — backward-compatible API."""

from .registry import create_default_registry

_registry = create_default_registry()
SUPPORTED_EXTENSIONS = _registry.supported_extensions()


def is_supported(path: str) -> bool:
    return _registry.is_supported(path)


def read_metadata(file_path: str) -> dict:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return {}
    return parser.read_metadata(file_path)


def read_comment(file_path: str) -> list[str]:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return []
    return parser.read_comment(file_path)


def read_comment_raw(file_path: str) -> str:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return ""
    return parser.read_comment_raw(file_path)


def write_comment(file_path: str, categories: list[str]) -> bool:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return False
    return parser.write_comment(file_path, categories)


def write_comments(file_path: str, comments: str) -> bool:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return False
    return parser.write_comments(file_path, comments)


def get_album_art(file_path: str) -> bytes | None:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return None
    return parser.get_album_art(file_path)
