
import pytest

from src.core.bpm_store import _MISSING, BpmStore


@pytest.mark.unit
def test_get_returns_missing_for_unknown_file(tmp_path):
    store = BpmStore(tmp_path)
    assert store.get("/some/file.mp3") is _MISSING


@pytest.mark.unit
def test_set_and_get_returns_bpm(tmp_path):
    store = BpmStore(tmp_path)
    track_path = str(tmp_path / "track.flac")
    store.set(track_path, 128.0)
    assert store.get(track_path) == 128.0


@pytest.mark.unit
def test_set_none_marks_analyzed_no_result(tmp_path):
    store = BpmStore(tmp_path)
    track_path = str(tmp_path / "silence.flac")
    store.set(track_path, None)
    assert store.get(track_path) is None


@pytest.mark.unit
def test_save_and_reload_round_trips(tmp_path):
    store = BpmStore(tmp_path)
    track_path = str(tmp_path / "song.mp3")
    store.set(track_path, 140.5)
    store.save()

    store2 = BpmStore(tmp_path)
    assert store2.get(track_path) == 140.5


@pytest.mark.unit
def test_remove_deletes_entry(tmp_path):
    store = BpmStore(tmp_path)
    track_path = str(tmp_path / "track.mp3")
    store.set(track_path, 120.0)
    store.remove(track_path)
    assert store.get(track_path) is _MISSING


@pytest.mark.unit
def test_load_handles_corrupt_json(tmp_path):
    monovault = tmp_path / ".monovault"
    monovault.mkdir()
    (monovault / "bpm_cache.json").write_text("not json")
    store = BpmStore(tmp_path)
    assert store.get(str(tmp_path / "x.mp3")) is _MISSING
