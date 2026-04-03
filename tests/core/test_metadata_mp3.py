"""Tests for Mp3Parser methods."""
import pytest
from unittest.mock import patch, MagicMock
import mutagen
from src.core.metadata.mp3_parser import Mp3Parser


@pytest.fixture()
def parser() -> Mp3Parser:
    return Mp3Parser()


def _make_mp3_audio(
    title: str = "Test Title",
    artist: str = "Test Artist",
    album: str = "Test Album",
    duration: float = 180.0,
    comm_text: str = "",
    apic_data: bytes | None = None,
) -> MagicMock:
    audio = MagicMock()
    audio.info.length = duration

    tags = MagicMock()
    tags.get.side_effect = lambda key, default=None: {
        "title": [title],
        "artist": [artist],
        "album": [album],
    }.get(key, default)

    comm_frame = MagicMock()
    comm_frame.text = [comm_text] if comm_text else []

    tags.getall.side_effect = lambda key: {
        "COMM": [comm_frame] if comm_text else [],
        "APIC": [MagicMock(data=apic_data)] if apic_data else [],
        "covr": [],
    }.get(key, [])

    audio.tags = tags
    audio.tags.__bool__ = lambda self: True
    return audio


class TestCanHandle:
    def test_handles_mp3(self, parser: Mp3Parser) -> None:
        assert parser.can_handle("file.mp3") is True

    def test_handles_mp3_uppercase(self, parser: Mp3Parser) -> None:
        assert parser.can_handle("file.MP3") is True

    def test_does_not_handle_flac(self, parser: Mp3Parser) -> None:
        assert parser.can_handle("file.flac") is False

    def test_does_not_handle_wav(self, parser: Mp3Parser) -> None:
        assert parser.can_handle("file.wav") is False


class TestReadMetadata:
    def test_file_not_found_returns_empty(self, parser: Mp3Parser) -> None:
        result = parser.read_metadata("/nonexistent/file.mp3")
        assert result == {}

    def test_mutagen_returns_none_returns_empty(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        with patch("mutagen.File", return_value=None):
            result = parser.read_metadata(str(fake))
        assert result == {}

    def test_mutagen_error_returns_empty(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        with patch("mutagen.File", side_effect=mutagen.MutagenError("bad")):
            result = parser.read_metadata(str(fake))
        assert result == {}

    def test_tags_present_extracts_correctly(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = _make_mp3_audio(title="Song", artist="Band", album="LP", duration=240.0)
        with patch("mutagen.File", return_value=audio):
            result = parser.read_metadata(str(fake))
        assert result["title"] == "Song"
        assert result["artist"] == "Band"
        assert result["album"] == "LP"
        assert result["duration"] == 240.0
        assert result["album_art"] is None

    def test_tags_absent_returns_defaults(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = MagicMock()
        audio.tags = None
        audio.info.length = 0.0
        with patch("mutagen.File", return_value=audio):
            result = parser.read_metadata(str(fake))
        assert result["title"] == ""
        assert result["artist"] == ""
        assert result["album"] == ""

    def test_album_art_extracted_from_apic(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        art_bytes = b"\xff\xd8\xff"
        audio = _make_mp3_audio(apic_data=art_bytes)
        with patch("mutagen.File", return_value=audio):
            result = parser.read_metadata(str(fake))
        assert result["album_art"] == art_bytes


class TestReadComment:
    def test_file_not_found_returns_empty_list(self, parser: Mp3Parser) -> None:
        result = parser.read_comment("/nonexistent/file.mp3")
        assert result == []

    def test_mutagen_returns_none_returns_empty_list(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        with patch("mutagen.File", return_value=None):
            result = parser.read_comment(str(fake))
        assert result == []

    def test_no_tags_returns_empty_list(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = MagicMock()
        audio.tags = None
        with patch("mutagen.File", return_value=audio):
            result = parser.read_comment(str(fake))
        assert result == []

    def test_comm_tag_splits_into_list(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = _make_mp3_audio(comm_text="rock pop 90s")
        with patch("mutagen.File", return_value=audio):
            result = parser.read_comment(str(fake))
        assert result == ["rock", "pop", "90s"]

    def test_empty_comm_tag_returns_empty_list(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = _make_mp3_audio(comm_text="")
        with patch("mutagen.File", return_value=audio):
            result = parser.read_comment(str(fake))
        assert result == []


class TestReadCommentRaw:
    def test_file_not_found_returns_empty_string(self, parser: Mp3Parser) -> None:
        result = parser.read_comment_raw("/nonexistent/file.mp3")
        assert result == ""

    def test_mutagen_returns_none_returns_empty_string(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        with patch("mutagen.File", return_value=None):
            result = parser.read_comment_raw(str(fake))
        assert result == ""

    def test_returns_raw_comm_text(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = _make_mp3_audio(comm_text="rock pop 90s")
        with patch("mutagen.File", return_value=audio):
            result = parser.read_comment_raw(str(fake))
        assert result == "rock pop 90s"

    def test_no_comm_tag_returns_empty_string(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = _make_mp3_audio(comm_text="")
        with patch("mutagen.File", return_value=audio):
            result = parser.read_comment_raw(str(fake))
        assert result == ""


class TestWriteComment:
    def test_file_not_found_returns_false(self, parser: Mp3Parser) -> None:
        result = parser.write_comment("/nonexistent/file.mp3", ["rock"])
        assert result is False

    def test_mutagen_returns_none_returns_false(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        with patch("mutagen.File", return_value=None):
            result = parser.write_comment(str(fake), ["rock"])
        assert result is False

    def test_mutagen_error_returns_false(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        with patch("mutagen.File", side_effect=mutagen.MutagenError("bad")):
            result = parser.write_comment(str(fake), ["rock"])
        assert result is False

    def test_successful_write_returns_true(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = MagicMock()
        audio.tags = MagicMock()
        audio.save.return_value = None
        with patch("mutagen.File", return_value=audio):
            result = parser.write_comment(str(fake), ["rock", "pop"])
        assert result is True
        audio.save.assert_called_once()

    def test_joins_categories_with_space(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = MagicMock()
        audio.tags = MagicMock()
        with patch("mutagen.File", return_value=audio):
            with patch("mutagen.id3.COMM") as mock_comm:
                parser.write_comment(str(fake), ["a", "b", "c"])
                mock_comm.assert_called_once_with(encoding=3, lang="eng", text="a b c")


class TestWriteComments:
    def test_file_not_found_returns_false(self, parser: Mp3Parser) -> None:
        result = parser.write_comments("/nonexistent/file.mp3", "raw string")
        assert result is False

    def test_mutagen_error_returns_false(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        with patch("mutagen.File", side_effect=mutagen.MutagenError("bad")):
            result = parser.write_comments(str(fake), "raw string")
        assert result is False

    def test_successful_write_returns_true(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = MagicMock()
        audio.tags = MagicMock()
        with patch("mutagen.File", return_value=audio):
            result = parser.write_comments(str(fake), "rock pop")
        assert result is True
        audio.save.assert_called_once()


class TestGetAlbumArt:
    def test_mutagen_returns_none_returns_none(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        with patch("mutagen.File", return_value=None):
            result = parser.get_album_art(str(fake))
        assert result is None

    def test_no_tags_returns_none(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = MagicMock()
        audio.tags = None
        with patch("mutagen.File", return_value=audio):
            result = parser.get_album_art(str(fake))
        assert result is None

    def test_apic_tag_returns_bytes(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        art = b"\xff\xd8\xff"
        audio = _make_mp3_audio(apic_data=art)
        with patch("mutagen.File", return_value=audio):
            result = parser.get_album_art(str(fake))
        assert result == art

    def test_no_art_returns_none(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        audio = _make_mp3_audio()
        with patch("mutagen.File", return_value=audio):
            result = parser.get_album_art(str(fake))
        assert result is None

    def test_mutagen_error_returns_none(self, parser: Mp3Parser, tmp_path) -> None:
        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"")
        with patch("mutagen.File", side_effect=mutagen.MutagenError("bad")):
            result = parser.get_album_art(str(fake))
        assert result is None
