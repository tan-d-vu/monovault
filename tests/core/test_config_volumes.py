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
