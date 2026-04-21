"""Tests for Config volumes functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.config import Config


@pytest.mark.unit
def test_register_volume_new():
    """Should create new volume entry with path and timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()
            config.register_volume("vol123", "/path/to/folder")

            assert "vol123" in config.volumes
            assert "/path/to/folder" in config.volumes["vol123"]["paths"]
            assert "created_at" in config.volumes["vol123"]


@pytest.mark.unit
def test_register_volume_existing_adds_path():
    """Should add path to existing volume without duplication."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()
            config.register_volume("vol123", "/path1")
            config.register_volume("vol123", "/path2")
            config.register_volume("vol123", "/path1")  # Duplicate

            paths = config.volumes["vol123"]["paths"]
            assert len(paths) == 2
            assert "/path1" in paths
            assert "/path2" in paths


@pytest.mark.unit
def test_get_volume_paths():
    """Should return paths list for volume."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()
            config.register_volume("vol123", "/path1")
            config.register_volume("vol123", "/path2")

            paths = config.get_volume_paths("vol123")
            assert paths == ["/path1", "/path2"]


@pytest.mark.unit
def test_get_volume_paths_unknown():
    """Should return empty list for unknown volume."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()
            paths = config.get_volume_paths("unknown_vol")
            assert paths == []


@pytest.mark.unit
def test_update_volume_path():
    """Should replace old path in volumes and folders."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()
            config.add_folder("/old/path")
            config.register_volume("vol123", "/old/path")

            config.update_volume_path("vol123", "/old/path", "/new/path")

            assert "/new/path" in config.volumes["vol123"]["paths"]
            assert "/old/path" not in config.volumes["vol123"]["paths"]
            assert "/new/path" in config.folders
            assert "/old/path" not in config.folders


@pytest.mark.unit
def test_save_load_round_trip_with_volumes():
    """Should persist volumes through save/load cycle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)

        # Create and save
        with patch.object(Config, "_get_config_dir", return_value=config_dir):
            config1 = Config()
            config1.add_folder("/music/path")
            config1.register_volume("vol_abc", "/music/path")

            # Verify saved
            saved_file = config_dir / "config.json"
            assert saved_file.exists()
            data = json.loads(saved_file.read_text())
            assert "volumes" in data
            assert "vol_abc" in data["volumes"]

            # Load in new config
            config2 = Config()
            assert "vol_abc" in config2.volumes
            assert "/music/path" in config2.volumes["vol_abc"]["paths"]


@pytest.mark.unit
def test_register_volume_normalizes_trailing_slash():
    """Should detect same path with/without trailing slash as duplicate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()
            # Register with trailing slash
            config.register_volume("vol_usb", f"{tmpdir}/mnt/usb/")
            # Register without trailing slash - should be deduplicated
            config.register_volume("vol_usb", f"{tmpdir}/mnt/usb")

            paths = config.volumes["vol_usb"]["paths"]
            assert len(paths) == 1, "Should have only one path (trailing slash normalized)"


@pytest.mark.unit
def test_register_volume_normalizes_symlinks():
    """Should normalize symlinks to canonical form."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create a real directory and a symlink to it
        real_dir = tmppath / "real_music"
        real_dir.mkdir()

        symlink_dir = tmppath / "link_music"
        try:
            symlink_dir.symlink_to(real_dir)
        except OSError:
            # Skip test on systems that don't support symlinks (e.g., Windows)
            pytest.skip("Symlinks not supported on this system")

        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()
            # Register using both symlink and real path
            config.register_volume("vol_music", str(symlink_dir))
            config.register_volume("vol_music", str(real_dir))

            paths = config.volumes["vol_music"]["paths"]
            assert len(paths) == 1, "Should deduplicate symlink and real path"


@pytest.mark.unit
def test_add_folder_normalizes_trailing_slash():
    """Should detect same folder with/without trailing slash as duplicate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()
            # Add with trailing slash
            result1 = config.add_folder(f"{tmpdir}/music/")
            assert result1 is True

            # Add without trailing slash - should be deduplicated
            result2 = config.add_folder(f"{tmpdir}/music")
            assert result2 is False, "Should not add duplicate path"

            assert len(config.folders) == 1


@pytest.mark.unit
def test_add_folder_normalizes_symlinks():
    """Should normalize symlinks to canonical form."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create a real directory and a symlink to it
        real_dir = tmppath / "real_music"
        real_dir.mkdir()

        symlink_dir = tmppath / "link_music"
        try:
            symlink_dir.symlink_to(real_dir)
        except OSError:
            # Skip test on systems that don't support symlinks
            pytest.skip("Symlinks not supported on this system")

        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()
            # Add using both symlink and real path
            result1 = config.add_folder(str(symlink_dir))
            assert result1 is True

            result2 = config.add_folder(str(real_dir))
            assert result2 is False, "Should deduplicate symlink and real path"

            assert len(config.folders) == 1


@pytest.mark.unit
def test_cross_computer_same_volume_different_paths():
    """Test scenario: Computer1 and Computer2 add different paths to same volume."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()

            # Computer1 mounts flash drive at D:\FlashDrive\
            config.register_volume("flash_drive_001", f"{tmpdir}/D/music")

            # Computer2 mounts same flash drive at /Volumes/FlashDrive/
            config.register_volume("flash_drive_001", f"{tmpdir}/volumes/music")

            # Both paths should exist since they're different
            paths = config.volumes["flash_drive_001"]["paths"]
            assert len(paths) == 2
            assert any("D" in p for p in paths)
            assert any("volumes" in p for p in paths)


@pytest.mark.unit
def test_register_volume_stores_canonical_path():
    """Should store normalized canonical form in config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()

            # Register with relative path
            original_path = "./music/library"
            config.register_volume("vol123", original_path)

            # Path should be stored as absolute canonical form
            stored_path = config.volumes["vol123"]["paths"][0]
            assert Path(stored_path).is_absolute()
            # Should not contain . or .. in the path
            assert ".." not in stored_path
            assert "/." not in stored_path


@pytest.mark.unit
def test_add_folder_stores_canonical_path():
    """Should store normalized canonical form in config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(Config, "_get_config_dir", return_value=Path(tmpdir)):
            config = Config()

            # Add with relative path
            original_path = "./music/library"
            config.add_folder(original_path)

            # Path should be stored as absolute canonical form
            stored_path = config.folders[0]
            assert Path(stored_path).is_absolute()
            # Should not contain . or .. in the path
            assert ".." not in stored_path
            assert "/." not in stored_path
