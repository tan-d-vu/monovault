"""Playback controller — manages playback state, track navigation, seeking."""

from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal

from ...core.events import EventBus
from ...core.playback import PlaybackEngine
from ...models.track import Track


class PlaybackController(QObject):
    """Decoupled playback logic. Emits signals for UI to bind."""

    now_playing_changed = pyqtSignal(str)
    play_state_changed = pyqtSignal(bool)
    position_updated = pyqtSignal(int, int)
    time_display_changed = pyqtSignal(str)
    slider_position_changed = pyqtSignal(int)

    def __init__(
        self,
        engine: PlaybackEngine,
        bus: Optional[EventBus] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._bus = bus
        self._current_track: Optional[Track] = None
        self._track_list: list[Track] = []
        self._is_seeking = False

        self._engine.position_changed.connect(self._on_position_changed)
        self._engine.duration_changed.connect(self._on_duration_changed)
        self._engine.playback_state_changed.connect(self._on_playback_state_changed)

    @property
    def current_track(self) -> Optional[Track]:
        return self._current_track

    @property
    def engine(self) -> PlaybackEngine:
        return self._engine

    def set_track_list(self, tracks: list[Track]) -> None:
        self._track_list = list(tracks)

    def set_current_track(self, track: Track) -> None:
        self._current_track = track
        self._engine.load_track(track.file_path)

    def play_track(self, track: Track) -> None:
        self._current_track = track
        self._engine.load_track(track.file_path)
        self._engine.play()
        self.play_state_changed.emit(True)
        self.now_playing_changed.emit("{} - {}".format(track.title, track.artist))

        if self._bus:
            from ...core.events import TrackPlaybackStarted

            self._bus.publish(TrackPlaybackStarted(track=track))

    def toggle_playback(self) -> None:
        if self._engine.is_playing():
            self._engine.pause()
            self.play_state_changed.emit(False)
            if self._bus:
                from ...core.events import PlaybackStateChanged

                self._bus.publish(PlaybackStateChanged(is_playing=False))
        elif self._current_track:
            self._engine.play()
            self.play_state_changed.emit(True)
            if self._bus:
                from ...core.events import PlaybackStateChanged

                self._bus.publish(PlaybackStateChanged(is_playing=True))

    def seek(self, slider_position: int) -> None:
        if self._is_seeking:
            return
        self._is_seeking = True
        try:
            duration = self._engine.get_duration()
            if duration > 0:
                seek_pos = int(slider_position / 1000 * duration)
                self._engine.seek(seek_pos)
        finally:
            self._is_seeking = False

    def set_volume(self, value: int) -> None:
        self._engine.set_volume(value)

    def next_track(self) -> None:
        if not self._track_list or not self._current_track:
            return
        idx = self._find_current_index()
        if idx is not None and idx < len(self._track_list) - 1:
            self.play_track(self._track_list[idx + 1])

    def prev_track(self) -> None:
        if not self._track_list or not self._current_track:
            return
        idx = self._find_current_index()
        if idx is not None and idx > 0:
            self.play_track(self._track_list[idx - 1])

    def stop(self) -> None:
        self._engine.stop()
        self._current_track = None
        if self._bus:
            from ...core.events import PlaybackStopped

            self._bus.publish(PlaybackStopped())

    def _find_current_index(self) -> Optional[int]:
        if not self._current_track:
            return None
        for i, t in enumerate(self._track_list):
            if t.file_path == self._current_track.file_path:
                return i
        return None

    def _on_position_changed(self, position: int) -> None:
        if self._is_seeking:
            return
        self._is_seeking = True
        try:
            duration = self._engine.get_duration()
            if duration > 0:
                self.slider_position_changed.emit(int(position / duration * 1000))
            self.time_display_changed.emit(self._format_time(position, duration))
        finally:
            self._is_seeking = False

    def _on_duration_changed(self, duration: int) -> None:
        self.slider_position_changed.emit(0)
        self.time_display_changed.emit(self._format_time(0, duration))

    def _on_playback_state_changed(self, state) -> None:
        from PyQt6.QtMultimedia import QMediaPlayer

        actual_state = self._engine.player.playbackState()
        is_playing = actual_state == QMediaPlayer.PlaybackState.PlayingState
        self.play_state_changed.emit(is_playing)

    @staticmethod
    def _format_time(position_ms: int, duration_ms: int) -> str:
        pos_s = position_ms // 1000
        dur_s = duration_ms // 1000
        return (
            f"{pos_s // 60:02d}:{pos_s % 60:02d} / {dur_s // 60:02d}:{dur_s % 60:02d}"
        )
