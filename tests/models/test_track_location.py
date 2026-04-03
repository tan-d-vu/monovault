"""Tests for Track.location property bug fix."""

import tempfile
from pathlib import Path

import pytest

from src.models.track import Track


@pytest.mark.unit
def test_location_returns_full_directory_path():
    """Should return the full directory path of the file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        subdir = folder / "sub"
        subdir.mkdir()
        file_path = subdir / "track.mp3"
        file_path.touch()

        track = Track(
            id=1,
            file_path=str(file_path),
            title="Test",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path=str(folder),
            comments="",
            date_added="2026-01-01",
        )

        # Location should be the full path to the file's directory
        assert track.location == str(subdir)


@pytest.mark.unit
def test_location_empty_file_path():
    """Should return empty string for empty file_path."""
    track = Track(
        id=1,
        file_path="",
        title="Test",
        artist="Artist",
        album="Album",
        duration=180.0,
        categories=[],
        album_art=None,
        folder_path="/tmp/music",
        comments="",
        date_added="2026-01-01",
    )

    assert track.location == ""


@pytest.mark.unit
def test_location_file_at_root():
    """Should return file's parent directory even at root level."""
    track = Track(
        id=1,
        file_path="/tmp/track.mp3",
        title="Test",
        artist="Artist",
        album="Album",
        duration=180.0,
        categories=[],
        album_art=None,
        folder_path="/tmp",
        comments="",
        date_added="2026-01-01",
    )

    # File is directly in /tmp, so location is /tmp
    assert track.location == "/tmp"
