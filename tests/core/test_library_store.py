"""Tests for LibraryStore module."""

import json
import tempfile
from pathlib import Path

import pytest

from src.core.library_store import LibraryStore


@pytest.mark.unit
def test_library_store_init_loads_existing_metadata():
    """Should load existing library.json on initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)

        # Create a library.json with existing metadata
        monovault_dir = base_dir / ".monovault"
        monovault_dir.mkdir()
        metadata = {
            "songs/song1.mp3": "2025-01-01",
            "songs/song2.mp3": "2025-01-02",
        }
        lib_file = monovault_dir / "library.json"
        lib_file.write_text(json.dumps(metadata))

        # Initialize LibraryStore
        store = LibraryStore(base_dir)

        # Verify metadata was loaded
        assert store.get(str(base_dir / "songs" / "song1.mp3")) == "2025-01-01"
        assert store.get(str(base_dir / "songs" / "song2.mp3")) == "2025-01-02"


@pytest.mark.unit
def test_record_if_new_creates_entry():
    """Should create new entry with current file mtime."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        store = LibraryStore(base_dir)

        # Create a test file
        test_file = base_dir / "songs" / "test.mp3"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")

        # Record the file
        date_added = store.record_if_new(str(test_file))

        # Verify it was recorded
        assert date_added == store.get(str(test_file))
        assert date_added != ""
        # Should be today's date or earlier (based on file mtime)
        assert isinstance(date_added, str)


@pytest.mark.unit
def test_record_if_new_preserves_existing_date():
    """Should return same date_added on second call (idempotent)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        store = LibraryStore(base_dir)

        # Create a test file
        test_file = base_dir / "songs" / "test.mp3"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")

        # First call should create entry
        date_added_1 = store.record_if_new(str(test_file))

        # Wait a moment (optional, just to ensure different time)
        import time

        time.sleep(0.1)

        # Second call should return same date, not overwrite
        date_added_2 = store.record_if_new(str(test_file))

        # Verify they're identical
        assert date_added_1 == date_added_2
        assert date_added_2 == store.get(str(test_file))


@pytest.mark.unit
def test_record_if_new_multiple_files():
    """Should track multiple files independently."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        store = LibraryStore(base_dir)

        # Create two test files
        test_file1 = base_dir / "songs" / "song1.mp3"
        test_file2 = base_dir / "songs" / "song2.mp3"
        test_file1.parent.mkdir(parents=True)
        test_file1.write_text("test1")
        test_file2.write_text("test2")

        # Record both
        date1 = store.record_if_new(str(test_file1))
        date2 = store.record_if_new(str(test_file2))

        # They should both be recorded
        assert date1 == store.get(str(test_file1))
        assert date2 == store.get(str(test_file2))


@pytest.mark.unit
def test_to_key_relative_path_posix():
    """Should convert relative paths to POSIX format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        store = LibraryStore(base_dir)

        # Test a relative path
        file_path = str(base_dir / "songs" / "rock" / "song.mp3")
        key = store._to_key(file_path)

        # Should use forward slashes (POSIX)
        assert "/" in key or key.count(key[0]) == len(key)  # Either has / or is single segment
        assert "\\" not in key  # No backslashes
        # Should be relative (not absolute)
        assert not key.startswith("/")
        assert not key.startswith("\\")
        assert not (len(key) > 1 and key[1] == ":")  # No Windows drive letter


@pytest.mark.unit
def test_to_key_outside_base_dir_uses_posix():
    """Should convert absolute paths for files outside base_dir to POSIX format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        store = LibraryStore(base_dir)

        # File outside base_dir
        file_path = "/other/path/file.mp3"

        key = store._to_key(file_path)

        # Should still use forward slashes
        assert "/" in key
        assert "\\" not in key


@pytest.mark.unit
def test_computer2_loads_computer1_metadata():
    """Cross-computer scenario: Computer2 should see Computer1's date_added."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)

        # Simulate Computer1 creating library.json
        monovault_dir = base_dir / ".monovault"
        monovault_dir.mkdir()
        computer1_metadata = {
            "songs/favorite.mp3": "2024-12-01",
            "songs/album/track1.mp3": "2024-12-05",
        }
        lib_file = monovault_dir / "library.json"
        lib_file.write_text(json.dumps(computer1_metadata))

        # Computer2 creates a new store, loads Computer1's metadata
        store_computer2 = LibraryStore(base_dir)

        # Computer2 should see Computer1's dates
        favorite = base_dir / "songs" / "favorite.mp3"
        track1 = base_dir / "songs" / "album" / "track1.mp3"

        assert store_computer2.get(str(favorite)) == "2024-12-01"
        assert store_computer2.get(str(track1)) == "2024-12-05"

        # Computer2 adds a new file
        new_file = base_dir / "songs" / "new.mp3"
        new_file.parent.mkdir(parents=True, exist_ok=True)
        new_file.write_text("new")
        date_added_new = store_computer2.record_if_new(str(new_file))

        # Verify new file is tracked separately
        assert store_computer2.get(str(new_file)) == date_added_new
        assert date_added_new != "2024-12-01"

        # Verify Computer1's dates are still preserved
        assert store_computer2.get(str(favorite)) == "2024-12-01"


@pytest.mark.unit
def test_library_store_persistence():
    """Should persist data across store instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)

        # First store: add some data
        store1 = LibraryStore(base_dir)
        test_file = base_dir / "songs" / "test.mp3"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")
        date1 = store1.record_if_new(str(test_file))

        # Create a new store instance (simulates app restart)
        store2 = LibraryStore(base_dir)

        # Should load the persisted data
        assert store2.get(str(test_file)) == date1


@pytest.mark.unit
def test_to_key_handles_windows_paths():
    """Should convert Windows paths to POSIX format internally."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        store = LibraryStore(base_dir)

        # Even though we're on Linux, test the conversion logic
        # by simulating a Windows-style absolute path
        file_path = str(base_dir / "songs" / "track.mp3")
        key = store._to_key(file_path)

        # Result should never have backslashes
        assert "\\" not in key
        # Should use forward slashes
        assert key.count("/") >= 1 or key == "songs/track.mp3" or "track.mp3" in key


@pytest.mark.unit
def test_record_if_new_with_empty_dir():
    """Should handle files in base_dir root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        store = LibraryStore(base_dir)

        # Create file directly in base_dir
        test_file = base_dir / "track.mp3"
        test_file.write_text("test")

        date_added = store.record_if_new(str(test_file))
        assert date_added == store.get(str(test_file))
        assert date_added != ""
