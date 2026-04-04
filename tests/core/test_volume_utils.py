"""Tests for volume_utils module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.volume_utils import (
    ensure_volume_id,
    find_volume_by_id,
    generate_volume_id,
    get_mount_search_paths,
    read_volume_id,
    write_volume_id,
)


@pytest.mark.unit
def test_generate_volume_id_is_hex_uuid():
    """Generated volume ID should be 32-char hex string."""
    vol_id = generate_volume_id()
    assert isinstance(vol_id, str)
    assert len(vol_id) == 32
    assert all(c in "0123456789abcdef" for c in vol_id)


@pytest.mark.unit
def test_write_and_read_volume_id():
    """Should write and read volume_id successfully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        vol_id = write_volume_id(folder)
        read_id = read_volume_id(folder)
        assert read_id == vol_id
        assert (folder / ".monovault" / "volume_id").exists()


@pytest.mark.unit
def test_read_volume_id_missing():
    """Should return None for non-existent dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        result = read_volume_id(folder)
        assert result is None


@pytest.mark.unit
def test_ensure_volume_id_creates_new():
    """Should create new volume_id when missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        vol_id = ensure_volume_id(folder)
        assert vol_id is not None
        assert len(vol_id) == 32
        assert (folder / ".monovault" / "volume_id").exists()


@pytest.mark.unit
def test_ensure_volume_id_readonly():
    """Should return None on read-only dir without crash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        folder.chmod(0o444)  # Read-only
        try:
            result = ensure_volume_id(folder)
            assert result is None
        finally:
            folder.chmod(0o755)  # Restore permissions


@pytest.mark.unit
def test_ensure_volume_id_reads_existing():
    """When volume_id file exists, should read and return it without creating new."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        # Manually create volume_id file with specific ID
        fixed_id = "vol_abc123def456ghi789jkl0123"
        monovault_dir = folder / ".monovault"
        monovault_dir.mkdir(parents=True, exist_ok=True)
        volume_id_file = monovault_dir / "volume_id"
        volume_id_file.write_text(fixed_id)

        # Call ensure_volume_id
        result = ensure_volume_id(folder)

        # Should return the existing ID, not generate a new one
        assert result == fixed_id
        # Verify it's still the same file (not overwritten)
        assert volume_id_file.read_text().strip() == fixed_id


@pytest.mark.unit
def test_ensure_volume_id_generates_new_if_missing():
    """When no volume_id file, should generate new one."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        # Ensure no .monovault directory exists
        assert not (folder / ".monovault").exists()

        result = ensure_volume_id(folder)

        # Should generate a new ID
        assert result is not None
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)
        # Should create the file
        assert (folder / ".monovault" / "volume_id").exists()


@pytest.mark.unit
def test_ensure_volume_id_returns_none_on_read_only():
    """When write fails (OSError), should return None gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        # Create .monovault dir but make it read-only
        monovault_dir = folder / ".monovault"
        monovault_dir.mkdir(parents=True, exist_ok=True)
        monovault_dir.chmod(0o444)

        try:
            result = ensure_volume_id(folder)
            # Should return None due to permission error
            assert result is None
        finally:
            monovault_dir.chmod(0o755)  # Restore permissions


@pytest.mark.unit
def test_ensure_volume_id_idempotent():
    """Multiple calls to same folder return same ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)

        # Call three times
        id1 = ensure_volume_id(folder)
        id2 = ensure_volume_id(folder)
        id3 = ensure_volume_id(folder)

        # All should be identical
        assert id1 == id2 == id3
        assert id1 is not None
        assert len(id1) == 32


@pytest.mark.unit
def test_get_mount_search_paths_linux():
    """Should return Linux paths when platform is Linux."""
    with patch("src.core.volume_utils.platform.system", return_value="Linux"):
        with patch("src.core.volume_utils.os.getlogin", return_value="testuser"):
            paths = get_mount_search_paths()
            path_strs = [str(p) for p in paths]
            assert any("run/media/testuser" in p for p in path_strs)
            assert any("media/testuser" in p for p in path_strs)
            assert any("/mnt" in p for p in path_strs)


@pytest.mark.unit
def test_get_mount_search_paths_macos():
    """Should return macOS paths when platform is Darwin."""
    with patch("src.core.volume_utils.platform.system", return_value="Darwin"):
        paths = get_mount_search_paths()
        path_strs = [str(p) for p in paths]
        assert any("Volumes" in p for p in path_strs)


@pytest.mark.unit
def test_get_mount_search_paths_windows():
    """Should return drive letters for Windows."""
    with patch("src.core.volume_utils.platform.system", return_value="Windows"):
        with patch("src.core.volume_utils.Path.exists", return_value=True):
            paths = get_mount_search_paths()
            # Should have multiple drive letters
            assert len(paths) > 0


@pytest.mark.unit
def test_find_volume_by_id_found():
    """Should find volume by volume_id."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mount_root = Path(tmpdir)
        folder = mount_root / "usb_drive"
        folder.mkdir()
        vol_id = write_volume_id(folder)

        # Mock get_mount_search_paths to return tmpdir
        with patch(
            "src.core.volume_utils.get_mount_search_paths",
            return_value=[mount_root],
        ):
            found = find_volume_by_id(vol_id)
            assert found == folder


@pytest.mark.unit
def test_find_volume_by_id_not_found():
    """Should return None when volume not found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        unknown_id = generate_volume_id()

        with patch(
            "src.core.volume_utils.get_mount_search_paths",
            return_value=[folder],
        ):
            result = find_volume_by_id(unknown_id)
            assert result is None
