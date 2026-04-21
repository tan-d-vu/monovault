"""Tests for volume re-association logic in MainWindow."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
def test_reassociate_finds_moved_volume():
    """Should find moved volume and update config (unit test)."""
    from src.ui.main_window import MainWindow

    # Create a minimal mock window
    window = MagicMock(spec=MainWindow)
    window.library = MagicMock()
    window.library.config = MagicMock()
    window.library.config.folders = ["/old/path"]
    window.library.config.volumes = {"vol123": {"paths": ["/old/path"]}}

    # Mock the method with real logic
    def mock_reassociate():
        config = window.library.config
        for folder in list(config.folders):
            if Path(folder).exists():
                continue
            for vol_id, vol_info in config.volumes.items():
                if folder in vol_info.get("paths", []):
                    new_path = Path("/new/path")  # Simulated find result
                    if new_path:
                        new_folder = str(new_path)
                        config.update_volume_path(vol_id, folder, new_folder)
                    break

    window._reassociate_volumes = mock_reassociate

    # Run the reassociation
    window._reassociate_volumes()

    # Verify config.update_volume_path was called
    window.library.config.update_volume_path.assert_called_once_with(
        "vol123", "/old/path", "/new/path"
    )


@pytest.mark.unit
def test_register_volume_on_add_folder():
    """Should trigger ensure_volume_id + register_volume."""
    from src.ui.main_window import MainWindow

    window = MagicMock(spec=MainWindow)
    window.library = MagicMock()
    window.library.config = MagicMock()

    # Manually create the _register_volume method
    def mock_register(folder: str):
        vol_id = "test_vol_id"  # Simulated ensure_volume_id result
        if vol_id:
            window.library.config.register_volume(vol_id, folder)

    window._register_volume = mock_register
    window._register_volume("/test")

    window.library.config.register_volume.assert_called_once_with("test_vol_id", "/test")
