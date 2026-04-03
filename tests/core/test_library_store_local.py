"""Tests for per-folder LibraryStore functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from src.core.library_store import LibraryStore


@pytest.mark.unit
def test_per_folder_store_creates_dotdir_on_save():
    """Should create .monovault/ dir lazily on first save."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        store = LibraryStore(base_dir=folder)

        # .monovault should not exist yet
        assert not (folder / ".monovault").exists()

        # Add a file (which triggers save)
        test_file = folder / "test.mp3"
        test_file.touch()
        store.record_if_new(str(test_file))

        # Now .monovault should exist
        assert (folder / ".monovault").exists()
        assert (folder / ".monovault" / "library.json").exists()


@pytest.mark.unit
def test_per_folder_store_uses_relative_keys():
    """Should use POSIX-relative keys in per-folder mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        store = LibraryStore(base_dir=folder)

        # Create a nested file
        subdir = folder / "sub"
        subdir.mkdir()
        test_file = subdir / "track.mp3"
        test_file.touch()

        store.record_if_new(str(test_file))
        store.save()

        # Check JSON has relative POSIX key
        data = json.loads((folder / ".monovault" / "library.json").read_text())
        assert "sub/track.mp3" in data
        assert str(test_file) not in data


@pytest.mark.unit
def test_record_if_new_relative_key():
    """Should use relative key for record_if_new."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        store = LibraryStore(base_dir=folder)

        test_file = folder / "track.mp3"
        test_file.touch()

        date_added = store.record_if_new(str(test_file))
        assert date_added
        assert "-" in date_added  # ISO date format


@pytest.mark.unit
def test_get_with_absolute_path():
    """Should get value using absolute path (converts to relative)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        store = LibraryStore(base_dir=folder)

        test_file = folder / "track.mp3"
        test_file.touch()

        date_added = store.record_if_new(str(test_file))
        retrieved = store.get(str(test_file))
        assert retrieved == date_added


@pytest.mark.unit
def test_save_readonly_dir_no_crash():
    """Should log warning and skip save on read-only .monovault dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        store = LibraryStore(base_dir=folder)

        # Create test file with accessible metadata
        test_file = folder / "track.mp3"
        test_file.touch()

        # Record it (this should work)
        store.record_if_new(str(test_file))

        # Test that we handle OSError during save gracefully
        # We can mock the mkdir to raise OSError
        from unittest.mock import patch

        store2 = LibraryStore(base_dir=folder)
        test_file2 = folder / "track2.mp3"
        test_file2.touch()
        store2.record_if_new(str(test_file2))

        # Mock mkdir to fail
        with patch.object(Path, "mkdir", side_effect=OSError("Permission denied")):
            # This should not crash
            store2.save()

        # Should still be able to get the value in memory
        assert store2.get(str(test_file2)) != ""


@pytest.mark.unit
def test_round_trip_save_load():
    """Should save and load data correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)

        # Create and save
        store1 = LibraryStore(base_dir=folder)
        test_file = folder / "track.mp3"
        test_file.touch()
        date1 = store1.record_if_new(str(test_file))
        store1.save()

        # Load in new store
        store2 = LibraryStore(base_dir=folder)
        date2 = store2.get(str(test_file))

        assert date1 == date2
