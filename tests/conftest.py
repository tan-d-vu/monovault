import pytest
from PyQt6.QtWidgets import QApplication

from src.models.track import Track


@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication instance for the entire test session."""
    app = QApplication.instance() or QApplication([])
    yield app


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
