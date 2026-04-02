from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput


class PlaybackEngine(QObject):
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    playback_state_changed = pyqtSignal(int)
    track_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)

        self._current_track: Optional[str] = None
        self._current_position: int = 0
        self._duration: int = 0

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

    def load_track(self, file_path: str):
        self._current_track = file_path
        from PyQt6.QtCore import QUrl

        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.track_changed.emit(file_path)

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()
        self._current_track = None

    def seek(self, position: int):
        self.player.setPosition(position)

    def set_volume(self, volume: int):
        self.audio.setVolume(volume / 100.0)

    def get_volume(self) -> int:
        return int(self.audio.volume() * 100)

    def get_position(self) -> int:
        return self.player.position()

    def get_duration(self) -> int:
        return self.player.duration()

    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def is_paused(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState

    def current_track(self) -> Optional[str]:
        return self._current_track

    def _on_position_changed(self, position: int):
        self._current_position = position
        self.position_changed.emit(position)

    def _on_duration_changed(self, duration: int):
        self._duration = duration
        self.duration_changed.emit(duration)

    def _on_state_changed(self, state: int):
        self.playback_state_changed.emit(state)
