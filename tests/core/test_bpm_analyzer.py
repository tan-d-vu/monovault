from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.core.bpm_analyzer import analyze_bpm


@pytest.mark.unit
def test_returns_none_when_librosa_unavailable():
    with patch.dict("sys.modules", {"librosa": None}):
        result = analyze_bpm("/some/file.mp3")
    assert result is None


@pytest.mark.unit
def test_returns_none_for_fewer_than_4_beats():
    mock_librosa = MagicMock()
    mock_librosa.load.return_value = (np.zeros(1000), 44100)
    mock_librosa.beat.beat_track.return_value = (np.array([120.0]), np.array([1, 2]))  # 2 beats

    with patch.dict("sys.modules", {"librosa": mock_librosa, "librosa.beat": mock_librosa.beat}):
        result = analyze_bpm("/some/file.flac")
    assert result is None


@pytest.mark.unit
def test_returns_none_for_bpm_below_min():
    mock_librosa = MagicMock()
    mock_librosa.load.return_value = (np.zeros(44100), 44100)
    mock_librosa.beat.beat_track.return_value = (np.array([30.0]), np.arange(10))

    with patch.dict("sys.modules", {"librosa": mock_librosa, "librosa.beat": mock_librosa.beat}):
        result = analyze_bpm("/some/file.mp3")
    assert result is None


@pytest.mark.unit
def test_returns_rounded_bpm_for_valid_detection():
    mock_librosa = MagicMock()
    mock_librosa.load.return_value = (np.zeros(44100), 44100)
    mock_librosa.beat.beat_track.return_value = (np.array([128.456]), np.arange(20))

    with patch.dict("sys.modules", {"librosa": mock_librosa, "librosa.beat": mock_librosa.beat}):
        result = analyze_bpm("/some/file.flac")
    assert result == 128.5  # round(128.456, 1)
