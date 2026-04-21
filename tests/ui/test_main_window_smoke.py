"""Smoke tests for MainWindow.

MainWindow wires a lot together: library, scanner, playback, controllers,
and the three-panel UI. These tests don't assert pixel-perfect behavior —
they prove the window comes up, its expected child widgets exist, folder
state round-trips through the tree, and teardown is clean.

Every test uses `tmp_monovault_home` so no test ever touches the real
~/.monovault config. Tests run under QT_QPA_PLATFORM=offscreen (set in
conftest.py) so no display server is required.
"""

from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
class TestConstruction:
    def test_main_window_constructs_without_exception(self, main_window_fixture):
        assert main_window_fixture is not None
        assert main_window_fixture.windowTitle() == "MonoVault"

    def test_main_window_uses_tmp_config(self, main_window_fixture, tmp_monovault_home):
        # Config dir should point at the tmp home, not the real one
        assert main_window_fixture.library.config.config_dir.parent == tmp_monovault_home

    def test_main_window_starts_with_empty_library(self, main_window_fixture):
        assert main_window_fixture.library.get_all_tracks() == []

    def test_main_window_starts_with_no_folders(self, main_window_fixture):
        assert main_window_fixture.library.get_folders() == []


@pytest.mark.unit
class TestChildWidgets:
    def test_folder_tree_exists(self, main_window_fixture):
        assert main_window_fixture.folder_tree_widget is not None

    def test_track_table_exists(self, main_window_fixture):
        assert main_window_fixture.track_table_widget is not None

    def test_details_panel_exists(self, main_window_fixture):
        assert main_window_fixture.details_panel is not None

    def test_playback_bar_exists(self, main_window_fixture):
        assert main_window_fixture.playback_bar is not None

    def test_add_folder_button_exists(self, main_window_fixture):
        assert main_window_fixture.add_folder_btn is not None

    def test_refresh_button_exists(self, main_window_fixture):
        assert main_window_fixture.refresh_btn is not None

    def test_search_input_exists(self, main_window_fixture):
        assert main_window_fixture.search_input is not None


@pytest.mark.unit
class TestLibraryIntegration:
    def test_adding_folder_populates_folder_tree(self, main_window_fixture, tmp_path):
        music_folder = tmp_path / "music"
        music_folder.mkdir()

        main_window_fixture.library.add_folder(str(music_folder))
        # Re-run the same wiring used by MainWindow._load_library
        from src.ui.panels import populate_folder_tree

        populate_folder_tree(
            main_window_fixture.folder_tree_widget,
            main_window_fixture.library.get_folders(),
        )

        tree = main_window_fixture.folder_tree_widget
        assert tree.topLevelItemCount() == 1
        assert (
            tree.topLevelItem(0).data(0, 0x0100)  # UserRole
            == str(music_folder.resolve())
        )

    def test_adding_folder_with_tracks_round_trips(self, main_window_fixture, tmp_path):
        music_folder = tmp_path / "music"
        music_folder.mkdir()
        main_window_fixture.library.add_folder(str(music_folder))

        # No real tracks yet — we just care that the library state flows
        # into the window's in-memory list without error.
        main_window_fixture._load_tracks()

        assert main_window_fixture.all_tracks == []


@pytest.mark.unit
class TestAddFolderDialog:
    def test_cancelled_dialog_is_noop(self, main_window_fixture, monkeypatch):
        # QFileDialog returns "" when the user cancels — no folder added.
        monkeypatch.setattr(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            MagicMock(return_value=""),
        )
        main_window_fixture._add_folder()
        assert main_window_fixture.library.get_folders() == []

    def test_successful_dialog_adds_folder(self, main_window_fixture, monkeypatch, tmp_path):
        music_folder = tmp_path / "music"
        music_folder.mkdir()

        monkeypatch.setattr(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            MagicMock(return_value=str(music_folder)),
        )

        main_window_fixture._add_folder()

        assert str(music_folder.resolve()) in main_window_fixture.library.get_folders()


@pytest.mark.unit
class TestTeardown:
    def test_close_does_not_raise(self, qapp, tmp_monovault_home):
        from src.ui.main_window import MainWindow

        window = MainWindow()
        window.close()  # would raise if closeEvent crashed

    def test_close_stops_playback(self, qapp, tmp_monovault_home):
        from src.ui.main_window import MainWindow

        window = MainWindow()
        window.playback_ctrl.stop = MagicMock()
        window.close()
        window.playback_ctrl.stop.assert_called_once()
