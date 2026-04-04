import pytest
from unittest.mock import MagicMock, patch

from src.ui.controllers.category_controller import CategoryController
from src.models.track import Track


def make_track(categories=None):
    return Track(
        id=1,
        file_path="/tmp/test.mp3",
        title="Test",
        artist="Artist",
        album="Album",
        duration=180.0,
        categories=list(categories) if categories else [],
        album_art=None,
        folder_path="/tmp",
    )


def make_ctrl(categorizer, **kwargs):
    """Create a CategoryController with _schedule_write mocked out for unit tests."""
    ctrl = CategoryController(categorizer, **kwargs)
    ctrl._schedule_write = MagicMock()
    return ctrl


@pytest.mark.unit
class TestCategoryController:
    def test_add_category_success(self, qapp):
        categorizer = MagicMock()
        categorizer.parse_add_category.return_value = "jazz"
        categorizer.apply_categories.return_value = None
        categorizer.get_suggestions.return_value = []

        track = make_track()

        ctrl = make_ctrl(categorizer)
        ctrl.select_track(track)
        result = ctrl.add_category("jazz")

        assert result is True
        categorizer.parse_add_category.assert_called_once_with(track, "jazz")
        categorizer.apply_categories.assert_called_once()
        args = categorizer.apply_categories.call_args[0]
        assert "jazz" in args[1]
        ctrl._schedule_write.assert_called_once_with(track.file_path, args[1])  # type: ignore[union-attr]

    def test_add_category_no_track(self, qapp):
        categorizer = MagicMock()

        ctrl = make_ctrl(categorizer)
        result = ctrl.add_category("jazz")

        assert result is False

    def test_add_category_failure(self, qapp):
        categorizer = MagicMock()
        categorizer.parse_add_category.return_value = None

        track = make_track()

        ctrl = make_ctrl(categorizer)
        ctrl.select_track(track)
        result = ctrl.add_category("invalid")

        assert result is False

    def test_remove_category_success(self, qapp):
        categorizer = MagicMock()
        categorizer.parse_remove_category.return_value = "rock"
        categorizer.apply_categories.return_value = None
        categorizer.get_suggestions.return_value = []

        track = make_track(categories=["rock"])

        ctrl = make_ctrl(categorizer)
        ctrl.select_track(track)
        result = ctrl.remove_category("rock")

        assert result is True
        categorizer.parse_remove_category.assert_called_once_with(track, "rock")
        categorizer.apply_categories.assert_called_once()
        args = categorizer.apply_categories.call_args[0]
        assert "rock" not in args[1]

    def test_remove_category_no_track(self, qapp):
        categorizer = MagicMock()

        ctrl = make_ctrl(categorizer)
        result = ctrl.remove_category("rock")

        assert result is False

    def test_accept_suggestion_calls_add_category(self, qapp):
        categorizer = MagicMock()
        categorizer.parse_add_category.return_value = "jazz"
        categorizer.apply_categories.return_value = None

        track = make_track()

        ctrl = make_ctrl(categorizer)
        ctrl.select_track(track)
        result = ctrl.accept_suggestion("jazz")

        assert result is True
        categorizer.parse_add_category.assert_called_once_with(track, "jazz")

    def test_select_track_emits_signals(self, qapp):
        categorizer = MagicMock()
        categorizer.get_suggestions.return_value = [("jazz", "Artist")]

        track = make_track()

        ctrl = make_ctrl(categorizer)

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

        track = make_track()

        ctrl = make_ctrl(categorizer)

        suggestions = []
        ctrl.suggestions_changed.connect(lambda s: suggestions.extend(s))

        ctrl.select_track(track)

        assert suggestions == []

    def test_current_track_property(self, qapp):
        categorizer = MagicMock()

        ctrl = make_ctrl(categorizer)

        track = make_track()
        ctrl._current_track = track

        assert ctrl.current_track == track

    def test_clear_categories(self, qapp):
        categorizer = MagicMock()
        categorizer.apply_categories.return_value = None
        categorizer.get_suggestions.return_value = []

        track = make_track(categories=["rock", "jazz"])

        ctrl = make_ctrl(categorizer)
        ctrl.select_track(track)
        result = ctrl.clear_categories()

        assert result is True
        categorizer.apply_categories.assert_called_once_with(track, [])
        ctrl._schedule_write.assert_called_once_with(track.file_path, [])  # type: ignore[union-attr]

    def test_clear_categories_no_track(self, qapp):
        categorizer = MagicMock()

        ctrl = make_ctrl(categorizer)
        result = ctrl.clear_categories()

        assert result is False

    def test_write_failed_signal_emitted_on_error(self, qapp):
        categorizer = MagicMock()

        ctrl = make_ctrl(categorizer)

        failures = []
        ctrl.write_failed.connect(lambda path, msg: failures.append((path, msg)))

        # Simulate write failure by calling the handler directly
        ctrl._on_write_finished("/tmp/test.mp3", False, "Permission denied")

        assert len(failures) == 1
        assert failures[0] == ("/tmp/test.mp3", "Permission denied")

    def test_write_failed_signal_not_emitted_on_success(self, qapp):
        categorizer = MagicMock()

        ctrl = make_ctrl(categorizer)

        failures = []
        ctrl.write_failed.connect(lambda path, msg: failures.append((path, msg)))

        ctrl._on_write_finished("/tmp/test.mp3", True, "")

        assert failures == []

    def test_shutdown_drains_pool(self, qapp):
        categorizer = MagicMock()

        ctrl = CategoryController(categorizer)
        # shutdown() should not raise even with an idle pool
        ctrl.shutdown()
