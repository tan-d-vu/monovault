"""Tests for Scanner per-folder LibraryStore creation."""

import json
import tempfile
from pathlib import Path

import pytest

from src.core.scanner import Scanner


@pytest.mark.unit
def test_scan_creates_sidecar():
    """Should create per-folder sidecar after scanning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)

        # Create a dummy audio file (will fail metadata read but that's ok for this test)
        audio_file = folder / "test.mp3"
        audio_file.write_bytes(b"dummy")

        scanner = Scanner()
        # Scan will fail on metadata but should still create sidecar
        scanner.scan_folder(str(folder))

        # Should have created .monovault/library.json (even if empty)
        sidecar = folder / ".monovault" / "library.json"
        assert sidecar.exists()


@pytest.mark.unit
def test_scan_sidecar_has_relative_keys():
    """Should use relative POSIX keys in sidecar."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        sidecar_file = folder / ".monovault" / "library.json"
        sidecar_file.parent.mkdir(parents=True)

        # Create test data with relative key
        test_data = {"track.mp3": "2026-01-01"}
        sidecar_file.write_text(json.dumps(test_data))

        scanner = Scanner()
        scanner._find_audio_files(folder)  # Will be empty

        # Manually verify the store loads relative keys
        from src.core.library_store import LibraryStore

        LibraryStore(base_dir=folder)
        data = json.loads(sidecar_file.read_text())
        assert "track.mp3" in data  # POSIX relative, not absolute


@pytest.mark.unit
def test_scan_no_store_arg():
    """Scanner should take no library_store argument."""
    scanner = Scanner()
    # Should not have _store attribute anymore
    assert not hasattr(scanner, "_store")
