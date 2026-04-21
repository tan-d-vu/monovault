"""Tests for src/core/scanner.py.

The scanner is the system's entry point for files. Coverage here is about
boundary behavior: hostile filesystems (missing folders, missing files),
filtering (only audio extensions survive), and the happy path where a real
MP3 round-trips into a populated Track.

Audio fixtures are synthesized in-process via mutagen. That gives each test
a disposable, deterministic input without shipping binary blobs through git.

Note on tag visibility: the project's Mp3Parser accesses tags via
EasyID3-style string keys ("title", "artist", ...) but loads files through
plain mutagen.File(), which returns raw ID3 frames. The result is that
title/artist/album metadata in MP3 files is not surfaced. Scanner then
falls back to Path(file_path).stem / "Unknown" defaults. We test against
that observable behavior, not the theoretical behavior.
"""

from pathlib import Path

import pytest
from mutagen.id3 import COMM, ID3
from mutagen.mp3 import MP3

from src.core.scanner import Scanner

# Minimal MPEG1 Layer III frame: 128kbps, 44.1kHz, stereo, no padding, no CRC.
# Header byte layout: 0xFF 0xFB 0x90 0x00. Frame length for these params is
# floor(144 * 128000 / 44100) = 417 bytes. We pad with silence (zeros).
_SILENCE_FRAME = b"\xff\xfb\x90\x00" + b"\x00" * 413


def _make_valid_mp3(
    path: Path,
    *,
    comment: str = "",
    frames: int = 50,
) -> Path:
    """Write a minimal, mutagen-parseable MP3.

    Fifty silence frames (~1.3s) is comfortably above mutagen's header
    detection threshold. The resulting file is small (~21KB) and opens
    identically to a real MP3 from an encoder.

    An optional COMM (comment) frame carries space-separated categories —
    the one piece of metadata the app's parser actually reads from MP3.
    """
    path.write_bytes(_SILENCE_FRAME * frames)
    # Seed mutagen's info cache so MP3.info.length is non-zero on re-read
    MP3(str(path))

    if comment:
        tags = ID3()
        tags.add(COMM(encoding=3, lang="eng", text=comment))
        tags.save(str(path))

    return path


@pytest.mark.unit
class TestFindAudioFiles:
    def test_filters_to_audio_extensions(self, tmp_path):
        (tmp_path / "song.mp3").write_bytes(b"")
        (tmp_path / "track.flac").write_bytes(b"")
        (tmp_path / "notes.txt").write_text("not audio")
        (tmp_path / "cover.jpg").write_bytes(b"\xff\xd8\xff")

        scanner = Scanner()
        found = scanner._find_audio_files(tmp_path)

        names = sorted(Path(p).name for p in found)
        assert names == ["song.mp3", "track.flac"]

    def test_recurses_into_subdirectories(self, tmp_path):
        deep = tmp_path / "artist" / "album" / "disc1"
        deep.mkdir(parents=True)
        (deep / "11-track.mp3").write_bytes(b"")
        (tmp_path / "top.flac").write_bytes(b"")
        (tmp_path / "ignore.log").write_text("log")

        scanner = Scanner()
        found = scanner._find_audio_files(tmp_path)

        names = sorted(Path(p).name for p in found)
        assert names == ["11-track.mp3", "top.flac"]

    def test_empty_folder_returns_empty_list(self, tmp_path):
        scanner = Scanner()
        assert scanner._find_audio_files(tmp_path) == []

    def test_extensions_are_case_insensitive(self, tmp_path):
        (tmp_path / "loud.MP3").write_bytes(b"")
        (tmp_path / "quiet.Flac").write_bytes(b"")
        (tmp_path / "other.WAV").write_bytes(b"")

        scanner = Scanner()
        found = scanner._find_audio_files(tmp_path)

        names = sorted(Path(p).name for p in found)
        assert names == ["loud.MP3", "quiet.Flac"]


@pytest.mark.unit
class TestProcessFile:
    def test_nonexistent_file_returns_none(self, tmp_path):
        scanner = Scanner()
        result = scanner.process_file(
            str(tmp_path / "missing.mp3"), str(tmp_path), store=None
        )
        assert result is None

    def test_unreadable_metadata_returns_none(self, tmp_path):
        bogus = tmp_path / "fake.mp3"
        bogus.write_bytes(b"not actually an mp3")

        scanner = Scanner()
        result = scanner.process_file(str(bogus), str(tmp_path), store=None)
        assert result is None

    def test_valid_mp3_returns_populated_track(self, tmp_path):
        audio = _make_valid_mp3(tmp_path / "guard-clauses.mp3", comment="rock pop")

        scanner = Scanner()
        track = scanner.process_file(str(audio), str(tmp_path), store=None)

        assert track is not None
        # Parser can't extract ID3 title frames, so scanner falls back to stem.
        # Artist/album are returned as empty strings by the parser — scanner's
        # "Unknown" default only kicks in when the key is absent, which it isn't.
        assert track.title == "guard-clauses"
        assert track.artist == ""
        assert track.album == ""
        assert track.categories == ["rock", "pop"]
        assert track.comments == "rock pop"
        assert track.file_path == str(audio)
        assert track.folder_path == str(tmp_path)
        assert track.duration > 0


@pytest.mark.unit
class TestScanFolder:
    def test_nonexistent_folder_returns_empty(self, tmp_path):
        scanner = Scanner()
        assert scanner.scan_folder(str(tmp_path / "does-not-exist")) == []

    def test_path_to_file_returns_empty(self, tmp_path):
        lone_file = tmp_path / "oops.mp3"
        lone_file.write_bytes(b"")

        scanner = Scanner()
        assert scanner.scan_folder(str(lone_file)) == []

    def test_creates_sidecar_library_json(self, tmp_path):
        scanner = Scanner()
        scanner.scan_folder(str(tmp_path))

        sidecar = tmp_path / ".monovault" / "library.json"
        assert sidecar.exists()

    def test_returns_tracks_for_valid_files(self, tmp_path):
        _make_valid_mp3(tmp_path / "alpha.mp3")
        _make_valid_mp3(tmp_path / "beta.mp3")

        scanner = Scanner()
        tracks = scanner.scan_folder(str(tmp_path))

        assert len(tracks) == 2
        titles = sorted(t.title for t in tracks)
        assert titles == ["alpha", "beta"]

    def test_skips_files_that_fail_metadata(self, tmp_path):
        _make_valid_mp3(tmp_path / "readable.mp3")
        (tmp_path / "bad.mp3").write_bytes(b"garbage")

        scanner = Scanner()
        tracks = scanner.scan_folder(str(tmp_path))

        assert len(tracks) == 1
        assert tracks[0].title == "readable"

    def test_progress_callback_called_per_file(self, tmp_path):
        _make_valid_mp3(tmp_path / "one.mp3")
        _make_valid_mp3(tmp_path / "two.mp3")
        _make_valid_mp3(tmp_path / "three.mp3")

        received: list[tuple[int, int]] = []

        scanner = Scanner()
        scanner.progress_callback = lambda done, total: received.append((done, total))
        scanner.scan_folder(str(tmp_path))

        assert received == [(1, 3), (2, 3), (3, 3)]

    def test_date_added_recorded_in_sidecar(self, tmp_path):
        _make_valid_mp3(tmp_path / "tracked.mp3")

        scanner = Scanner()
        tracks = scanner.scan_folder(str(tmp_path))

        assert tracks[0].date_added  # non-empty ISO date string

        import json

        sidecar = tmp_path / ".monovault" / "library.json"
        data = json.loads(sidecar.read_text())
        assert "tracked.mp3" in data


@pytest.mark.unit
class TestScannerConstruction:
    def test_scanner_has_no_private_store(self):
        """Scanner is per-folder; no shared _store should leak between calls."""
        scanner = Scanner()
        assert not hasattr(scanner, "_store")

    def test_progress_callback_defaults_to_none(self):
        scanner = Scanner()
        assert scanner.progress_callback is None
