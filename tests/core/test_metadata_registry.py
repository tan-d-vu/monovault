"""Tests for MetadataRegistry dispatch logic."""
import pytest
from unittest.mock import MagicMock
from src.core.metadata.registry import MetadataRegistry


def make_mock_parser(extensions: set[str]) -> MagicMock:
    parser = MagicMock()
    parser.supported_extensions = extensions
    parser.can_handle.side_effect = lambda path: any(
        path.lower().endswith(ext) for ext in extensions
    )
    return parser


@pytest.fixture()
def registry() -> MetadataRegistry:
    reg = MetadataRegistry()
    reg.register(make_mock_parser({".mp3"}))
    reg.register(make_mock_parser({".flac"}))
    return reg


class TestGetParser:
    def test_returns_mp3_parser_for_mp3(self, registry: MetadataRegistry) -> None:
        parser = registry.get_parser("song.mp3")
        assert parser is not None
        assert ".mp3" in parser.supported_extensions

    def test_returns_flac_parser_for_flac(self, registry: MetadataRegistry) -> None:
        parser = registry.get_parser("song.flac")
        assert parser is not None
        assert ".flac" in parser.supported_extensions

    def test_returns_none_for_unsupported_wav(self, registry: MetadataRegistry) -> None:
        parser = registry.get_parser("song.wav")
        assert parser is None

    def test_returns_none_for_unsupported_aac(self, registry: MetadataRegistry) -> None:
        parser = registry.get_parser("song.aac")
        assert parser is None

    def test_case_insensitive_extension(self, registry: MetadataRegistry) -> None:
        parser = registry.get_parser("SONG.MP3")
        assert parser is not None

    def test_returns_none_for_no_extension(self, registry: MetadataRegistry) -> None:
        parser = registry.get_parser("songfile")
        assert parser is None


class TestSupportedExtensions:
    def test_contains_mp3_and_flac(self, registry: MetadataRegistry) -> None:
        exts = registry.supported_extensions()
        assert ".mp3" in exts
        assert ".flac" in exts

    def test_empty_registry_returns_empty_set(self) -> None:
        reg = MetadataRegistry()
        assert reg.supported_extensions() == set()

    def test_single_parser_extensions(self) -> None:
        reg = MetadataRegistry()
        reg.register(make_mock_parser({".mp3"}))
        assert reg.supported_extensions() == {".mp3"}


class TestIsSupported:
    def test_mp3_is_supported(self, registry: MetadataRegistry) -> None:
        assert registry.is_supported("track.mp3") is True

    def test_flac_is_supported(self, registry: MetadataRegistry) -> None:
        assert registry.is_supported("track.flac") is True

    def test_wav_is_not_supported(self, registry: MetadataRegistry) -> None:
        assert registry.is_supported("track.wav") is False

    def test_empty_string_is_not_supported(self, registry: MetadataRegistry) -> None:
        assert registry.is_supported("") is False


class TestRegister:
    def test_register_adds_parser(self) -> None:
        reg = MetadataRegistry()
        parser = make_mock_parser({".ogg"})
        reg.register(parser)
        assert reg.get_parser("file.ogg") is parser

    def test_first_registered_wins(self) -> None:
        reg = MetadataRegistry()
        first = make_mock_parser({".mp3"})
        second = make_mock_parser({".mp3"})
        reg.register(first)
        reg.register(second)
        assert reg.get_parser("file.mp3") is first
