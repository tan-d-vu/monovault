import os
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from src.models.track import Track

# Run Qt in offscreen mode globally — avoids flaky behavior on headless hosts
# and makes CI parity trivial. Setting it at import time means every test
# process sees it before any Qt platform init.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication instance for the entire test session.

    pytest-qt ships its own qapp fixture, but we keep a compatibility shim
    so older tests that expect our simpler contract keep working. Both
    fixtures return the same singleton, so there's no duplication.
    """
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def tmp_monovault_home(monkeypatch, tmp_path):
    """Redirect the app's config dir to a per-test tmp_path.

    Config._get_config_dir() resolves to Path.home()/'.monovault' on POSIX
    and %APPDATA%/'.monovault' on Windows. Patching both Path.home and
    APPDATA covers both branches, so the same fixture works everywhere.

    Returns the redirected home path so tests can inspect written config.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.setenv("APPDATA", str(fake_home))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    return fake_home


@pytest.fixture
def main_window_fixture(qapp, tmp_monovault_home):
    """Build a MainWindow against a tmp config and guarantee cleanup.

    Imported lazily so the conftest doesn't drag PyQt Multimedia into every
    test module that only needs Track fixtures.
    """
    from src.ui.main_window import MainWindow

    window = MainWindow()
    yield window
    window.close()
    window.deleteLater()


@pytest.fixture
def sample_track() -> Track:
    return Track(
        id=1,
        file_path="/tmp/test.mp3",
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration=180.0,
        categories=["rock", "instrumental"],
        album_art=None,
        folder_path="/tmp",
        comments="rock instrumental",
        date_added="2025-01-01",
    )


@pytest.fixture
def sample_track_no_categories() -> Track:
    return Track(
        id=2,
        file_path="/tmp/test2.flac",
        title="Another Song",
        artist="Test Artist",
        album="Test Album",
        duration=240.0,
        categories=[],
        album_art=None,
        folder_path="/tmp",
        comments="",
        date_added="2025-01-02",
    )


@pytest.fixture
def sample_tracks(sample_track, sample_track_no_categories) -> list[Track]:
    return [sample_track, sample_track_no_categories]
