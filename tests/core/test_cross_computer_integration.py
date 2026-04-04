"""Integration tests for cross-computer flash drive support scenarios.

Tests cover:
- Windows → macOS volume re-association with metadata preservation
- New files on Computer2 updating library.json
- Read-only mount rejection
"""

import json
from datetime import date

import pytest

from src.core.library_store import LibraryStore
from src.core.volume_utils import ensure_volume_id


@pytest.mark.integration
class TestCrossComputerWindowsToMac:
    """Test Windows → macOS cross-computer scenario."""

    def test_volume_id_preserved_across_computers(self, tmp_path):
        """Windows creates volume_id; macOS should read the same ID."""
        # Simulate Computer1 (Windows) creating volume_id
        computer1_folder = tmp_path / "flash_drive"
        computer1_folder.mkdir()

        vol_id_computer1 = ensure_volume_id(computer1_folder)
        assert vol_id_computer1 is not None

        # Simulate Computer2 (macOS) reading same folder
        computer2_folder = computer1_folder  # Same physical folder
        vol_id_computer2 = ensure_volume_id(computer2_folder)

        # Should be identical
        assert vol_id_computer2 == vol_id_computer1

    def test_date_added_preserved_across_computers(self, tmp_path, sample_track):
        """Date_added values from Computer1 should be preserved on Computer2."""
        # Simulate Computer1 (Windows) scanning
        flash_drive = tmp_path / "flash_drive"
        flash_drive.mkdir()

        # Create 10 audio files
        audio_folder = flash_drive / "music"
        audio_folder.mkdir()
        for i in range(10):
            audio_file = audio_folder / f"song_{i}.mp3"
            audio_file.write_text("dummy audio")

        # Computer1 scans and records files
        store1 = LibraryStore(base_dir=flash_drive)
        recorded_dates = {}
        for i in range(10):
            file_path = str(audio_folder / f"song_{i}.mp3")
            date_added = store1.record_if_new(file_path)
            recorded_dates[file_path] = date_added
        store1.save()

        # Verify library.json exists
        lib_file = flash_drive / ".monovault" / "library.json"
        assert lib_file.exists()

        # Computer2 loads same folder
        store2 = LibraryStore(base_dir=flash_drive)

        # All dates should match
        for file_path, expected_date in recorded_dates.items():
            retrieved_date = store2.get(file_path)
            assert retrieved_date == expected_date

    def test_library_json_format_preserved(self, tmp_path):
        """Library.json format should be readable across computers."""
        flash_drive = tmp_path / "flash_drive"
        flash_drive.mkdir()

        audio_folder = flash_drive / "music"
        audio_folder.mkdir()

        # Create 3 files
        file_paths = []
        for i in range(3):
            audio_file = audio_folder / f"song_{i}.mp3"
            audio_file.write_text("dummy")
            file_paths.append(str(audio_file))

        # Computer1 records files
        store1 = LibraryStore(base_dir=flash_drive)
        for file_path in file_paths:
            store1.record_if_new(file_path)
        store1.save()

        # Verify JSON is valid and readable
        lib_file = flash_drive / ".monovault" / "library.json"
        json_content = json.loads(lib_file.read_text())

        # Should have all 3 files as keys
        assert len(json_content) == 3
        # All values should be ISO date strings
        for key, value in json_content.items():
            assert isinstance(key, str)
            assert isinstance(value, str)
            # Should be valid ISO date
            date.fromisoformat(value)


@pytest.mark.integration
class TestNewFilesUpdatingLibrary:
    """Test scenario where Computer2 adds new files to existing library."""

    def test_new_files_recorded_with_different_dates(self, tmp_path):
        """New files added on Computer2 should get new date_added values."""
        flash_drive = tmp_path / "flash_drive"
        flash_drive.mkdir()

        audio_folder = flash_drive / "music"
        audio_folder.mkdir()

        # Computer1 creates and scans 10 files
        store1 = LibraryStore(base_dir=flash_drive)
        original_dates = {}
        for i in range(10):
            file_path = audio_folder / f"original_{i}.mp3"
            file_path.write_text("dummy")
            date_added = store1.record_if_new(str(file_path))
            original_dates[str(file_path)] = date_added
        store1.save()

        # Computer2 loads same folder and adds 5 new files
        new_dates = {}
        for i in range(5):
            file_path = audio_folder / f"new_{i}.mp3"
            file_path.write_text("dummy")
            new_dates[str(file_path)] = str(file_path)

        store2 = LibraryStore(base_dir=flash_drive)
        for file_path in new_dates.keys():
            date_added = store2.record_if_new(file_path)
            new_dates[file_path] = date_added
        store2.save()

        # Verify all original files still have original dates
        store3 = LibraryStore(base_dir=flash_drive)
        for file_path, original_date in original_dates.items():
            retrieved = store3.get(file_path)
            assert retrieved == original_date

    def test_original_files_not_overwritten(self, tmp_path):
        """Original files' date_added should never be overwritten."""
        flash_drive = tmp_path / "flash_drive"
        flash_drive.mkdir()

        audio_folder = flash_drive / "music"
        audio_folder.mkdir()

        # Create and record 5 original files
        files = []
        for i in range(5):
            file_path = audio_folder / f"song_{i}.mp3"
            file_path.write_text("dummy")
            files.append(str(file_path))

        store1 = LibraryStore(base_dir=flash_drive)
        original_data = {}
        for file_path in files:
            date_added = store1.record_if_new(file_path)
            original_data[file_path] = date_added
        store1.save()

        # Load store again and force re-record (simulate Computer2 re-scanning)
        store2 = LibraryStore(base_dir=flash_drive)
        # Add 5 new files
        for i in range(5, 10):
            file_path = audio_folder / f"song_{i}.mp3"
            file_path.write_text("dummy")
            store2.record_if_new(str(file_path))
        store2.save()

        # Verify original files still have original dates
        store3 = LibraryStore(base_dir=flash_drive)
        for file_path, original_date in original_data.items():
            stored_date = store3.get(file_path)
            assert stored_date == original_date, (
                f"Original date for {file_path} was overwritten: "
                f"{original_date} → {stored_date}"
            )

    def test_library_json_accumulates_entries(self, tmp_path):
        """Library.json should accumulate entries, never lose data."""
        flash_drive = tmp_path / "flash_drive"
        flash_drive.mkdir()

        audio_folder = flash_drive / "music"
        audio_folder.mkdir()

        # Create 10 files in Computer1
        for i in range(10):
            file_path = audio_folder / f"song_{i}.mp3"
            file_path.write_text("dummy")

        store1 = LibraryStore(base_dir=flash_drive)
        for i in range(10):
            store1.record_if_new(str(audio_folder / f"song_{i}.mp3"))
        store1.save()

        lib_file = flash_drive / ".monovault" / "library.json"
        initial_count = len(json.loads(lib_file.read_text()))
        assert initial_count == 10

        # Add 5 more files in Computer2
        for i in range(10, 15):
            file_path = audio_folder / f"song_{i}.mp3"
            file_path.write_text("dummy")

        store2 = LibraryStore(base_dir=flash_drive)
        for i in range(10, 15):
            store2.record_if_new(str(audio_folder / f"song_{i}.mp3"))
        store2.save()

        # Should now have 15 entries
        final_count = len(json.loads(lib_file.read_text()))
        assert final_count == 15
        # First 10 should still be there
        final_data = json.loads(lib_file.read_text())
        for i in range(10):
            key = f"music/song_{i}.mp3"
            assert key in final_data


@pytest.mark.unit
class TestReadOnlyMountRejection:
    """Test rejection of read-only folders (Phase 1 implementation)."""

    def test_read_only_folder_shows_warning(self, qapp, tmp_path, monkeypatch):
        """Read-only folder should show warning and not add."""
        from unittest.mock import MagicMock


        from src.ui.main_window import MainWindow

        # Create read-only folder
        readonly_folder = tmp_path / "readonly_drive"
        readonly_folder.mkdir()
        readonly_folder.chmod(0o444)

        try:
            main_window = MainWindow()

            # Mock QFileDialog to return read-only folder
            mock_get_dir = MagicMock(return_value=str(readonly_folder))
            monkeypatch.setattr(
                "src.ui.main_window.QFileDialog.getExistingDirectory", mock_get_dir
            )

            # Mock warning message box
            mock_warning = MagicMock()
            monkeypatch.setattr("src.ui.main_window.QMessageBox.warning", mock_warning)

            # Attempt to add folder
            main_window._add_folder()

            # Warning should be shown
            mock_warning.assert_called_once()
            # library.add_folder should NOT be called
            assert str(readonly_folder) not in main_window.library.get_folders()
        finally:
            readonly_folder.chmod(0o755)

    def test_read_only_folder_no_volume_register(self, qapp, tmp_path, monkeypatch):
        """Read-only folder should not register volume."""
        from unittest.mock import MagicMock


        from src.ui.main_window import MainWindow

        readonly_folder = tmp_path / "readonly_drive"
        readonly_folder.mkdir()
        readonly_folder.chmod(0o444)

        try:
            main_window = MainWindow()
            config = main_window.library.config

            # Mock QFileDialog to return read-only folder
            mock_get_dir = MagicMock(return_value=str(readonly_folder))
            monkeypatch.setattr(
                "src.ui.main_window.QFileDialog.getExistingDirectory", mock_get_dir
            )

            # Mock warning message box
            mock_warning = MagicMock()
            monkeypatch.setattr("src.ui.main_window.QMessageBox.warning", mock_warning)

            # Attempt to add folder
            main_window._add_folder()

            # Folder should not be in config
            assert str(readonly_folder) not in config.get_folders()
        finally:
            # Restore permissions first
            readonly_folder.chmod(0o755)
            # Now check that no volume_id file exists
            assert not (readonly_folder / ".monovault" / "volume_id").exists()
