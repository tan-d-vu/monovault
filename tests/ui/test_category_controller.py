from unittest.mock import MagicMock, patch

import pytest

from src.models.track import Track
from src.ui.controllers.category_controller import CategoryController


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

    def test_write_failure_reverts_to_disk_state(self, qapp):
        categorizer = MagicMock()
        categorizer.apply_categories.return_value = None
        categorizer.get_suggestions.return_value = []

        track = make_track(categories=["rock", "jazz"])

        ctrl = make_ctrl(categorizer)
        ctrl.select_track(track)

        failures = []
        ctrl.write_failed.connect(lambda path, msg: failures.append((path, msg)))

        with patch(
            "src.ui.controllers.category_controller.read_comment",
            return_value=["rock"],
        ):
            ctrl._on_write_finished(track.file_path, False, "disk full")

        assert failures == [(track.file_path, "disk full")]
        categorizer.apply_categories.assert_called_with(track, ["rock"])

    def test_write_failure_for_other_track_is_ignored(self, qapp):
        categorizer = MagicMock()
        categorizer.apply_categories.return_value = None
        categorizer.get_suggestions.return_value = []

        track = make_track()

        ctrl = make_ctrl(categorizer)
        ctrl.select_track(track)

        # Reset apply_categories call history from select_track path.
        categorizer.apply_categories.reset_mock()

        with patch("src.ui.controllers.category_controller.read_comment") as mock_read:
            ctrl._on_write_finished("/tmp/other.mp3", False, "boom")

        mock_read.assert_not_called()
        categorizer.apply_categories.assert_not_called()

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


@pytest.mark.unit
class TestClearCategoriesBulk:
    def _make_track(self, track_id: int, categories=None) -> Track:
        return Track(
            id=track_id,
            file_path=f"/tmp/track{track_id}.mp3",
            title=f"Track {track_id}",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=list(categories) if categories else [],
            album_art=None,
            folder_path="/tmp",
        )

    def test_bulk_clear_skips_tracks_without_categories(self, qapp):
        categorizer = MagicMock()
        ctrl = make_ctrl(categorizer)

        tracks = [self._make_track(1, []), self._make_track(2, [])]
        result = ctrl.clear_categories_bulk(tracks)

        assert result == 0
        categorizer.apply_categories.assert_not_called()
        ctrl._schedule_write.assert_not_called()  # type: ignore[union-attr]

    def test_bulk_clear_clears_all_tracks_with_categories(self, qapp):
        categorizer = MagicMock()
        ctrl = make_ctrl(categorizer)

        track1 = self._make_track(1, ["rock"])
        track2 = self._make_track(2, ["jazz", "blues"])
        track3 = self._make_track(3, [])

        result = ctrl.clear_categories_bulk([track1, track2, track3])

        assert result == 2
        assert categorizer.apply_categories.call_count == 2
        ctrl._schedule_write.assert_any_call(track1.file_path, [])  # type: ignore[union-attr]
        ctrl._schedule_write.assert_any_call(track2.file_path, [])  # type: ignore[union-attr]

    def test_bulk_clear_emits_categories_changed_per_track(self, qapp):
        categorizer = MagicMock()
        ctrl = make_ctrl(categorizer)

        track1 = self._make_track(1, ["rock"])
        track2 = self._make_track(2, ["jazz"])

        emitted = []
        ctrl.categories_changed.connect(emitted.append)

        ctrl.clear_categories_bulk([track1, track2])

        assert len(emitted) == 2
        assert track1 in emitted
        assert track2 in emitted

    def test_bulk_clear_refreshes_suggestions_for_current_track(self, qapp):
        categorizer = MagicMock()
        categorizer.get_suggestions.return_value = []
        ctrl = make_ctrl(categorizer)

        track = self._make_track(1, ["rock"])
        ctrl.select_track(track)
        categorizer.get_suggestions.reset_mock()

        ctrl.clear_categories_bulk([track])

        categorizer.get_suggestions.assert_called_once_with(track)

    def test_bulk_clear_does_not_refresh_suggestions_when_current_track_not_in_selection(
        self, qapp
    ):
        categorizer = MagicMock()
        categorizer.get_suggestions.return_value = []
        ctrl = make_ctrl(categorizer)

        current = self._make_track(1, ["rock"])
        other = self._make_track(2, ["jazz"])
        ctrl.select_track(current)
        categorizer.get_suggestions.reset_mock()

        ctrl.clear_categories_bulk([other])

        categorizer.get_suggestions.assert_not_called()


@pytest.mark.unit
class TestReplaceEverywhere:
    def test_emits_signal_and_schedules_writes(self, qapp):
        categorizer = MagicMock()
        track1 = make_track(categories=["rock"])
        track2 = make_track(categories=["rock"])
        categorizer.replace_categories_everywhere.return_value = [track1, track2]
        ctrl = make_ctrl(categorizer)

        emitted = []
        ctrl.categories_changed.connect(emitted.append)

        result = ctrl.replace_everywhere({"rock"}, "metal")

        assert result == [track1, track2]
        assert emitted == [track1, track2]
        assert ctrl._schedule_write.call_count == 2

    def test_empty_modified_is_noop(self, qapp):
        categorizer = MagicMock()
        categorizer.replace_categories_everywhere.return_value = []
        ctrl = make_ctrl(categorizer)

        result = ctrl.replace_everywhere({"unknown"}, "x")

        assert result == []
        ctrl._schedule_write.assert_not_called()

    def test_refreshes_suggestions_when_current_track_modified(self, qapp):
        categorizer = MagicMock()
        categorizer.get_suggestions.return_value = []
        track = make_track(categories=["rock"])
        categorizer.replace_categories_everywhere.return_value = [track]
        ctrl = make_ctrl(categorizer)
        ctrl.select_track(track)
        categorizer.get_suggestions.reset_mock()

        ctrl.replace_everywhere({"rock"}, "metal")

        categorizer.get_suggestions.assert_called_once_with(track)

    def test_does_not_refresh_suggestions_when_current_track_not_modified(self, qapp):
        categorizer = MagicMock()
        categorizer.get_suggestions.return_value = []
        current = make_track(categories=["jazz"])
        other = make_track(categories=["rock"])
        categorizer.replace_categories_everywhere.return_value = [other]
        ctrl = make_ctrl(categorizer)
        ctrl.select_track(current)
        categorizer.get_suggestions.reset_mock()

        ctrl.replace_everywhere({"rock"}, "metal")

        categorizer.get_suggestions.assert_not_called()
