import logging

logger = logging.getLogger(__name__)

_MIN_BPM = 40.0
_MAX_BPM = 250.0
_MIN_BEATS = 4
_MAX_DURATION_S = 60


def analyze_bpm(file_path: str) -> float | None:
    """Analyze a file and return its BPM, or None if detection fails.

    Returns None when:
    - librosa is not installed
    - fewer than _MIN_BEATS beats detected
    - detected BPM is outside [_MIN_BPM, _MAX_BPM]
    """
    try:
        import librosa
        import numpy as np
    except ImportError:
        logger.warning("librosa not installed; BPM detection unavailable")
        return None

    try:
        y, sr = librosa.load(file_path, duration=_MAX_DURATION_S, sr=None, mono=True)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        beat_count = len(beats)

        if beat_count < _MIN_BEATS:
            return None

        bpm = float(np.atleast_1d(tempo)[0])
        if bpm < _MIN_BPM or bpm > _MAX_BPM:
            return None

        return round(bpm, 1)
    except Exception as e:
        logger.warning("BPM analysis failed for %s: %s", file_path, e)
        return None
