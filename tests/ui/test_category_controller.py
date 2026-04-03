import pytest
from unittest.mock import MagicMock

from src.ui.controllers.category_controller import CategoryController
from src.models.track import Track


@pytest.mark.unit
class TestCategoryController:
    def test_add_category_success(self, qapp):
        categorizer = MagicMock()
        categorizer.add_category.return_value = True
        categorizer.get_suggestions.return_value = []

        track = Track(
            id=1,
            file_path="/tmp/test.mp3",
            title="Test",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path="/tmp",
        )

        ctrl = CategoryController(categorizer)
        ctrl.select_track(track)
        result = ctrl.add_category("jazz")

        assert result is True
        categorizer.add_category.assert_called_once_with(track, "jazz")

    def test_add_category_no_track(self, qapp):
        categorizer = MagicMock()
        categorizer.add_category.return_value = True

        ctrl = CategoryController(categorizer)
        result = ctrl.add_category("jazz")

        assert result is False

    def test_add_category_failure(self, qapp):
        categorizer = MagicMock()
        categorizer.add_category.return_value = False

        track = Track(
            id=1,
            file_path="/tmp/test.mp3",
            title="Test",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path="/tmp",
        )

        ctrl = CategoryController(categorizer)
        ctrl.select_track(track)
        result = ctrl.add_category("invalid")

        assert result is False

    def test_remove_category_success(self, qapp):
        categorizer = MagicMock()
        categorizer.remove_category.return_value = True
        categorizer.get_suggestions.return_value = []

        track = Track(
            id=1,
            file_path="/tmp/test.mp3",
            title="Test",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=["rock"],
            album_art=None,
            folder_path="/tmp",
        )

        ctrl = CategoryController(categorizer)
        ctrl.select_track(track)
        result = ctrl.remove_category("rock")

        assert result is True
        categorizer.remove_category.assert_called_once_with(track, "rock")

    def test_remove_category_no_track(self, qapp):
        categorizer = MagicMock()
        categorizer.remove_category.return_value = True

        ctrl = CategoryController(categorizer)
        result = ctrl.remove_category("rock")

        assert result is False

    def test_accept_suggestion_calls_add_category(self, qapp):
        categorizer = MagicMock()
        categorizer.add_category.return_value = True

        track = Track(
            id=1,
            file_path="/tmp/test.mp3",
            title="Test",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path="/tmp",
        )

        ctrl = CategoryController(categorizer)
        ctrl.select_track(track)
        result = ctrl.accept_suggestion("jazz")

        assert result is True
        categorizer.add_category.assert_called_once_with(track, "jazz")

    def test_select_track_emits_signals(self, qapp):
        categorizer = MagicMock()
        categorizer.get_suggestions.return_value = [("jazz", "Artist")]

        track = Track(
            id=1,
            file_path="/tmp/test.mp3",
            title="Test",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path="/tmp",
        )

        ctrl = CategoryController(categorizer)

        track_details = []
        suggestions = []

        ctrl.track_details_changed.connect(lambda t: track_details.append(t))
        ctrl.suggestions_changed.connect(lambda s: suggestions.extend(s))

        ctrl.select_track(track)

        assert len(track_details) == 1
        assert track_details[0] == track
        assert len(suggestions) == 1
        assert suggestions[0] == ("jazz", "Artist")

    def test_select_track_with_no_suggestions(self, qapp):
        categorizer = MagicMock()
        categorizer.get_suggestions.return_value = []

        track = Track(
            id=1,
            file_path="/tmp/test.mp3",
            title="Test",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path="/tmp",
        )

        ctrl = CategoryController(categorizer)

        suggestions = []
        ctrl.suggestions_changed.connect(lambda s: suggestions.extend(s))

        ctrl.select_track(track)

        assert suggestions == []

    def test_current_track_property(self, qapp):
        categorizer = MagicMock()

        ctrl = CategoryController(categorizer)

        track = Track(
            id=1,
            file_path="/tmp/test.mp3",
            title="Test",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path="/tmp",
        )

        ctrl._current_track = track

        assert ctrl.current_track == track
