import pytest
from unittest.mock import MagicMock

from src.ui.controllers.playback_controller import PlaybackController
from src.models.track import Track


@pytest.mark.unit
class TestPlaybackController:
    def test_play_track_emits_signal(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()
        engine.load_track = MagicMock()
        engine.play = MagicMock()

        ctrl = PlaybackController(engine)

        track = Track(
            id=1,
            file_path="/tmp/test.mp3",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path="/tmp",
        )
        ctrl.play_track(track)

        engine.load_track.assert_called_once_with("/tmp/test.mp3")
        engine.play.assert_called_once()

    def test_toggle_playback_when_playing_pauses(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()
        engine.is_playing.return_value = True
        engine.pause = MagicMock()

        ctrl = PlaybackController(engine)
        ctrl.toggle_playback()

        engine.pause.assert_called_once()

    def test_toggle_playback_when_paused_plays_with_track(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()
        engine.is_playing.return_value = False

        ctrl = PlaybackController(engine)
        ctrl._current_track = MagicMock()
        ctrl.toggle_playback()

        engine.play.assert_called_once()

    def test_toggle_playback_no_track_no_op(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()
        engine.is_playing.return_value = False

        ctrl = PlaybackController(engine)
        ctrl._current_track = None

        ctrl.toggle_playback()

        engine.play.assert_not_called()

    def test_seek_with_valid_duration(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()
        engine.get_duration.return_value = 1000

        ctrl = PlaybackController(engine)
        ctrl.seek(500)

        engine.seek.assert_called_once_with(500)

    def test_seek_with_zero_duration(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()
        engine.get_duration.return_value = 0

        ctrl = PlaybackController(engine)
        ctrl.seek(500)

        engine.seek.assert_not_called()

    def test_set_volume(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()

        ctrl = PlaybackController(engine)
        ctrl.set_volume(80)

        engine.set_volume.assert_called_once_with(80)

    def test_next_track_at_end_does_nothing(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()

        track = Track(
            id=1,
            file_path="/tmp/test1.mp3",
            title="Song 1",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path="/tmp",
        )
        tracks = [track]

        ctrl = PlaybackController(engine)
        ctrl._track_list = tracks
        ctrl._current_track = track
        ctrl.play_track = MagicMock()

        ctrl.next_track()

        ctrl.play_track.assert_not_called()

    def test_prev_track_at_start_does_nothing(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()

        track = Track(
            id=1,
            file_path="/tmp/test1.mp3",
            title="Song 1",
            artist="Artist",
            album="Album",
            duration=180.0,
            categories=[],
            album_art=None,
            folder_path="/tmp",
        )
        tracks = [track]

        ctrl = PlaybackController(engine)
        ctrl._track_list = tracks
        ctrl._current_track = track
        ctrl.play_track = MagicMock()

        ctrl.prev_track()

        ctrl.play_track.assert_not_called()

    def test_format_time(self):
        assert PlaybackController._format_time(63000, 240000) == "01:03 / 04:00"
        assert PlaybackController._format_time(0, 0) == "00:00 / 00:00"
        assert PlaybackController._format_time(0, 60000) == "00:00 / 01:00"

    def test_stop_clears_current_track(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()
        engine.stop = MagicMock()

        ctrl = PlaybackController(engine)
        ctrl._current_track = MagicMock()

        ctrl.stop()

        engine.stop.assert_called_once()
        assert ctrl._current_track is None

    def test_current_track_property(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()

        ctrl = PlaybackController(engine)

        track = MagicMock()
        ctrl._current_track = track

        assert ctrl.current_track == track

    def test_set_track_list(self, qapp):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()

        ctrl = PlaybackController(engine)

        tracks = [MagicMock(), MagicMock()]
        ctrl.set_track_list(tracks)

        assert len(ctrl._track_list) == 2
