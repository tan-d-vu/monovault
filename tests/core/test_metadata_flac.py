"""Tests for FlacParser methods."""
import pytest
from unittest.mock import patch, MagicMock
import mutagen
from mutagen.flac import FLAC
from src.core.metadata.flac_parser import FlacParser


@pytest.fixture()
def parser() -> FlacParser:
    return FlacParser()


def _make_flac_audio(
    title: str = "Test Title",
    artist: str = "Test Artist",
    album: str = "Test Album",
    duration: float = 180.0,
    comment: str = "",
    picture_data: bytes | None = None,
) -> MagicMock:
    """Create a mock FLAC audio object (isinstance check uses spec=FLAC)."""
    audio = MagicMock(spec=FLAC)
    audio.info.length = duration

    audio.get.side_effect = lambda key, default=None: {
        "title": [title],
        "artist": [artist],
        "album": [album],
    }.get(key, default)

    tags = MagicMock()
    tags.get.side_effect = lambda key, default=None: (
        [comment] if key == "COMMENT" and comment else default
    )
    audio.tags = tags
    audio.tags.__bool__ = lambda self: True

    if picture_data:
        pic = MagicMock()
        pic.data = picture_data
        audio.pictures = [pic]
    else:
        audio.pictures = []

    return audio


class TestCanHandle:
    def test_handles_flac(self, parser: FlacParser) -> None:
        assert parser.can_handle("file.flac") is True

    def test_handles_flac_uppercase(self, parser: FlacParser) -> None:
        assert parser.can_handle("file.FLAC") is True

    def test_does_not_handle_mp3(self, parser: FlacParser) -> None:
        assert parser.can_handle("file.mp3") is False

    def test_does_not_handle_wav(self, parser: FlacParser) -> None:
        assert parser.can_handle("file.wav") is False


class TestReadMetadata:
    def test_file_not_found_returns_empty(self, parser: FlacParser) -> None:
        result = parser.read_metadata("/nonexistent/file.flac")
        assert result == {}

    def test_mutagen_returns_none_returns_empty(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        with patch("mutagen.File", return_value=None):
            result = parser.read_metadata(str(fake))
        assert result == {}

    def test_mutagen_error_returns_empty(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        with patch("mutagen.File", side_effect=mutagen.MutagenError("bad")):
            result = parser.read_metadata(str(fake))
        assert result == {}

    def test_flac_tags_extracted_correctly(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        audio = _make_flac_audio(title="Song", artist="Band", album="LP", duration=240.0)
        with patch("mutagen.File", return_value=audio):
            result = parser.read_metadata(str(fake))
        assert result["title"] == "Song"
        assert result["artist"] == "Band"
        assert result["album"] == "LP"
        assert result["duration"] == 240.0
        assert result["album_art"] is None

    def test_picture_data_extracted(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        art = b"\x89PNG"
        audio = _make_flac_audio(picture_data=art)
        with patch("mutagen.File", return_value=audio):
            result = parser.read_metadata(str(fake))
        assert result["album_art"] == art

    def test_no_pictures_returns_none_art(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        audio = _make_flac_audio()
        with patch("mutagen.File", return_value=audio):
            result = parser.read_metadata(str(fake))
        assert result["album_art"] is None


class TestReadComment:
    def test_file_not_found_returns_empty_list(self, parser: FlacParser) -> None:
        result = parser.read_comment("/nonexistent/file.flac")
        assert result == []

    def test_mutagen_returns_none_returns_empty_list(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        with patch("mutagen.File", return_value=None):
            result = parser.read_comment(str(fake))
        assert result == []

    def test_no_tags_returns_empty_list(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        audio = MagicMock()
        audio.tags = None
        with patch("mutagen.File", return_value=audio):
            result = parser.read_comment(str(fake))
        assert result == []

    def test_comment_tag_splits_into_list(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        audio = _make_flac_audio(comment="jazz blues 70s")
        with patch("mutagen.File", return_value=audio):
            result = parser.read_comment(str(fake))
        assert result == ["jazz", "blues", "70s"]

    def test_empty_comment_returns_empty_list(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        audio = _make_flac_audio(comment="")
        with patch("mutagen.File", return_value=audio):
            result = parser.read_comment(str(fake))
        assert result == []


class TestReadCommentRaw:
    def test_file_not_found_returns_empty_string(self, parser: FlacParser) -> None:
        result = parser.read_comment_raw("/nonexistent/file.flac")
        assert result == ""

    def test_mutagen_returns_none_returns_empty_string(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        with patch("mutagen.File", return_value=None):
            result = parser.read_comment_raw(str(fake))
        assert result == ""

    def test_returns_raw_comment_text(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        audio = _make_flac_audio(comment="jazz blues 70s")
        with patch("mutagen.File", return_value=audio):
            result = parser.read_comment_raw(str(fake))
        assert result == "jazz blues 70s"

    def test_no_comment_returns_empty_string(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        audio = _make_flac_audio(comment="")
        with patch("mutagen.File", return_value=audio):
            result = parser.read_comment_raw(str(fake))
        assert result == ""


class TestWriteComment:
    def test_file_not_found_returns_false(self, parser: FlacParser) -> None:
        result = parser.write_comment("/nonexistent/file.flac", ["jazz"])
        assert result is False

    def test_mutagen_returns_none_returns_false(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        with patch("mutagen.File", return_value=None):
            result = parser.write_comment(str(fake), ["jazz"])
        assert result is False

    def test_mutagen_error_returns_false(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        with patch("mutagen.File", side_effect=mutagen.MutagenError("bad")):
            result = parser.write_comment(str(fake), ["jazz"])
        assert result is False

    def test_successful_write_returns_true(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        audio = MagicMock()
        audio.tags = MagicMock()
        audio.save.return_value = None
        with patch("mutagen.File", return_value=audio):
            result = parser.write_comment(str(fake), ["jazz", "blues"])
        assert result is True
        audio.save.assert_called_once()

    def test_joins_categories_with_space(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        audio = MagicMock()
        audio.tags = {}
        with patch("mutagen.File", return_value=audio):
            parser.write_comment(str(fake), ["a", "b", "c"])
        assert audio.tags["COMMENT"] == ["a b c"]


class TestWriteComments:
    def test_file_not_found_returns_false(self, parser: FlacParser) -> None:
        result = parser.write_comments("/nonexistent/file.flac", "raw string")
        assert result is False

    def test_mutagen_error_returns_false(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        with patch("mutagen.File", side_effect=mutagen.MutagenError("bad")):
            result = parser.write_comments(str(fake), "raw string")
        assert result is False

    def test_successful_write_returns_true(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        audio = MagicMock()
        audio.tags = {}
        with patch("mutagen.File", return_value=audio):
            result = parser.write_comments(str(fake), "jazz blues")
        assert result is True
        assert audio.tags["COMMENT"] == ["jazz blues"]
        audio.save.assert_called_once()


class TestGetAlbumArt:
    def test_mutagen_returns_none_returns_none(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        with patch("mutagen.File", return_value=None):
            result = parser.get_album_art(str(fake))
        assert result is None

    def test_flac_picture_returns_bytes(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        art = b"\x89PNG"
        audio = _make_flac_audio(picture_data=art)
        with patch("mutagen.File", return_value=audio):
            result = parser.get_album_art(str(fake))
        assert result == art

    def test_no_pictures_returns_none(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        audio = _make_flac_audio()
        with patch("mutagen.File", return_value=audio):
            result = parser.get_album_art(str(fake))
        assert result is None

    def test_mutagen_error_returns_none(self, parser: FlacParser, tmp_path) -> None:
        fake = tmp_path / "test.flac"
        fake.write_bytes(b"")
        with patch("mutagen.File", side_effect=mutagen.MutagenError("bad")):
            result = parser.get_album_art(str(fake))
        assert result is None
