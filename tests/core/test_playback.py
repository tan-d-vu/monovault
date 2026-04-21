"""Tests for src/core/playback.py.

PlaybackEngine wraps QMediaPlayer + QAudioOutput. The wrapper itself is
thin, so most tests assert that method calls delegate to the underlying
Qt objects correctly and that signals fire on state transitions.

Strategy: we patch QMediaPlayer / QAudioOutput at the module boundary so
construction produces MagicMocks instead of real media objects — but we
substitute a class that *still exposes the real PlaybackState enum* so
`is_playing()` and friends can compare against it. That keeps the suite
headless, deterministic, and free of real-Qt audio driver dependencies.
"""

from unittest.mock import MagicMock

import pytest
from PyQt6.QtMultimedia import QMediaPlayer


class _FakeMediaPlayerFactory(MagicMock):
    """Callable Mock whose class attrs proxy the real QMediaPlayer.

    MagicMock() gives us the instance side (setSource, play, etc. become
    recorded-call spies). Declaring PlaybackState/Error as class attrs
    means code referencing QMediaPlayer.PlaybackState still sees the real
    IntEnum, so equality checks in is_playing/is_paused behave correctly.
    """

    PlaybackState = QMediaPlayer.PlaybackState
    Error = QMediaPlayer.Error


@pytest.fixture
def mocked_engine(qapp, monkeypatch):
    """Yield a PlaybackEngine whose Qt collaborators are MagicMocks.

    The engine's own pyqtSignals stay real so pytest-qt's qtbot can observe
    them. Only the outbound QMediaPlayer/QAudioOutput objects are mocked.
    """
    from src.core import playback as playback_module

    # Swap in the fake classes — code doing `QMediaPlayer()` now yields a
    # MagicMock instance; code doing `QMediaPlayer.PlaybackState.X` still
    # sees the real enum thanks to the class-level proxy.
    monkeypatch.setattr(playback_module, "QMediaPlayer", _FakeMediaPlayerFactory)
    monkeypatch.setattr(playback_module, "QAudioOutput", MagicMock)

    engine = playback_module.PlaybackEngine()
    # Default volume readback: the constructor set 0.7; mirror that
    engine.audio.volume.return_value = 0.7
    yield engine
    engine.deleteLater()


@pytest.mark.unit
class TestInitialState:
    def test_initial_current_track_is_none(self, mocked_engine):
        assert mocked_engine.current_track() is None

    def test_initial_position_is_zero(self, mocked_engine):
        assert mocked_engine._current_position == 0

    def test_initial_duration_is_zero(self, mocked_engine):
        assert mocked_engine._duration == 0

    def test_audio_output_wired_to_player(self, mocked_engine):
        mocked_engine.player.setAudioOutput.assert_called_once_with(mocked_engine.audio)

    def test_default_volume_is_seventy_percent(self, mocked_engine):
        mocked_engine.audio.setVolume.assert_called_once_with(0.7)


@pytest.mark.unit
class TestLoadTrack:
    def test_load_sets_source_on_player(self, mocked_engine):
        mocked_engine.load_track("/music/song.mp3")

        mocked_engine.player.setSource.assert_called_once()
        args, _ = mocked_engine.player.setSource.call_args
        # QUrl.fromLocalFile(...) returns a QUrl — assert it points at our file
        assert args[0].toLocalFile() == "/music/song.mp3"

    def test_load_records_current_track(self, mocked_engine):
        mocked_engine.load_track("/music/song.mp3")
        assert mocked_engine.current_track() == "/music/song.mp3"

    def test_load_emits_track_changed(self, qtbot, mocked_engine):
        with qtbot.waitSignal(mocked_engine.track_changed, timeout=500) as blocker:
            mocked_engine.load_track("/music/song.mp3")
        assert blocker.args == ["/music/song.mp3"]


@pytest.mark.unit
class TestPlaybackTransitions:
    def test_play_calls_player_play(self, mocked_engine):
        mocked_engine.play()
        mocked_engine.player.play.assert_called_once()

    def test_pause_calls_player_pause(self, mocked_engine):
        mocked_engine.pause()
        mocked_engine.player.pause.assert_called_once()

    def test_stop_calls_player_stop_and_clears_track(self, mocked_engine):
        mocked_engine.load_track("/music/song.mp3")
        assert mocked_engine.current_track() == "/music/song.mp3"

        mocked_engine.stop()

        mocked_engine.player.stop.assert_called_once()
        assert mocked_engine.current_track() is None

    def test_seek_forwards_to_player(self, mocked_engine):
        mocked_engine.seek(12345)
        mocked_engine.player.setPosition.assert_called_once_with(12345)


@pytest.mark.unit
class TestSignals:
    def test_position_changed_signal_re_emitted(self, qtbot, mocked_engine):
        with qtbot.waitSignal(mocked_engine.position_changed, timeout=500) as blocker:
            mocked_engine._on_position_changed(9000)
        assert blocker.args == [9000]
        assert mocked_engine._current_position == 9000

    def test_duration_changed_signal_re_emitted(self, qtbot, mocked_engine):
        with qtbot.waitSignal(mocked_engine.duration_changed, timeout=500) as blocker:
            mocked_engine._on_duration_changed(240000)
        assert blocker.args == [240000]
        assert mocked_engine._duration == 240000

    def test_state_changed_signal_re_emitted(self, qtbot, mocked_engine):
        # playback_state_changed is pyqtSignal(int); PyQt6 marshals the
        # PlaybackState enum into *some* integer on emission. We don't care
        # what that integer is — only that the signal fires exactly once
        # per state transition.
        with qtbot.waitSignal(mocked_engine.playback_state_changed, timeout=500) as blocker:
            mocked_engine._on_state_changed(QMediaPlayer.PlaybackState.PlayingState)
        assert len(blocker.args) == 1
        assert isinstance(blocker.args[0], int)


@pytest.mark.unit
class TestVolume:
    def test_set_volume_normalizes_from_percent(self, mocked_engine):
        mocked_engine.set_volume(50)
        mocked_engine.audio.setVolume.assert_called_with(0.5)

    def test_set_volume_accepts_zero(self, mocked_engine):
        mocked_engine.set_volume(0)
        mocked_engine.audio.setVolume.assert_called_with(0.0)

    def test_set_volume_accepts_max(self, mocked_engine):
        mocked_engine.set_volume(100)
        mocked_engine.audio.setVolume.assert_called_with(1.0)

    def test_get_volume_denormalizes_to_percent(self, mocked_engine):
        mocked_engine.audio.volume.return_value = 0.35
        assert mocked_engine.get_volume() == 35


@pytest.mark.unit
class TestStateQueries:
    def test_is_playing_true_when_player_is_playing(self, mocked_engine):
        mocked_engine.player.playbackState.return_value = QMediaPlayer.PlaybackState.PlayingState
        assert mocked_engine.is_playing() is True

    def test_is_playing_false_when_paused(self, mocked_engine):
        mocked_engine.player.playbackState.return_value = QMediaPlayer.PlaybackState.PausedState
        assert mocked_engine.is_playing() is False

    def test_is_paused_true_when_paused(self, mocked_engine):
        mocked_engine.player.playbackState.return_value = QMediaPlayer.PlaybackState.PausedState
        assert mocked_engine.is_paused() is True

    def test_is_paused_false_when_playing(self, mocked_engine):
        mocked_engine.player.playbackState.return_value = QMediaPlayer.PlaybackState.PlayingState
        assert mocked_engine.is_paused() is False

    def test_get_position_delegates_to_player(self, mocked_engine):
        mocked_engine.player.position.return_value = 42000
        assert mocked_engine.get_position() == 42000

    def test_get_duration_delegates_to_player(self, mocked_engine):
        mocked_engine.player.duration.return_value = 180000
        assert mocked_engine.get_duration() == 180000


@pytest.mark.unit
class TestErrorHandling:
    def test_error_handler_does_not_raise(self, mocked_engine):
        # _on_error is a print-only handler; it should tolerate any input
        mocked_engine._on_error(QMediaPlayer.Error.ResourceError, "Resource unavailable")
