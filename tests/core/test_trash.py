"""Tests for src/core/trash.py — TrashManager contract.

Trash is a single-folder concept (one TrashManager per watched folder), so
fixtures here build a tmp folder, drop a fake audio file inside it, and
exercise move/restore/purge round-trips. The audio bytes never matter — the
manager is a pure file mover and JSON store. We use plain `.mp3` extensions
on text files so we don't pay a mutagen tax we don't need.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.trash import TrashEntry, TrashManager
from src.models.track import Track


def _track_for(file_path: Path, folder: Path) -> Track:
    return Track(
        id=42,
        file_path=str(file_path),
        title="Song",
        artist="Artist",
        album="Album",
        duration=123.4,
        categories=["rock", "90s"],
        album_art=None,
        folder_path=str(folder),
        comments="rock 90s",
        date_added="2024-06-12",
    )


@pytest.fixture
def folder_with_track(tmp_path: Path) -> tuple[Path, Path, Track]:
    folder = tmp_path / "library"
    folder.mkdir()
    audio = folder / "Artist" / "Album" / "01 - Song.mp3"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"AUDIO_BYTES")
    track = _track_for(audio, folder)
    return folder, audio, track


@pytest.mark.unit
def test_move_to_trash_relocates_file(folder_with_track):
    folder, audio, track = folder_with_track
    manager = TrashManager(folder)

    trash_id = manager.move_to_trash(track)

    assert not audio.exists()
    trash_dir = folder / ".monovault" / "trash"
    moved_files = [p for p in trash_dir.iterdir() if p.suffix == ".mp3"]
    assert len(moved_files) == 1
    assert moved_files[0].read_bytes() == b"AUDIO_BYTES"
    assert moved_files[0].stem == trash_id


@pytest.mark.unit
def test_move_to_trash_records_manifest_with_relative_path(folder_with_track):
    folder, _audio, track = folder_with_track
    manager = TrashManager(folder)

    trash_id = manager.move_to_trash(track)

    manifest = json.loads((folder / ".monovault" / "trash" / "manifest.json").read_text())
    assert trash_id in manifest
    entry = manifest[trash_id]
    assert entry["original_relpath"] == "Artist/Album/01 - Song.mp3"
    assert entry["title"] == "Song"
    assert entry["artist"] == "Artist"
    assert entry["categories"] == ["rock", "90s"]
    assert entry["date_added"] == "2024-06-12"


@pytest.mark.unit
def test_move_to_trash_rejects_file_outside_folder(tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    other = tmp_path / "elsewhere.mp3"
    other.write_bytes(b"X")
    manager = TrashManager(folder)

    track = _track_for(other, folder)
    with pytest.raises(ValueError):
        manager.move_to_trash(track)


@pytest.mark.unit
def test_move_to_trash_missing_source_raises(tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    ghost = folder / "ghost.mp3"
    manager = TrashManager(folder)

    with pytest.raises(FileNotFoundError):
        manager.move_to_trash(_track_for(ghost, folder))


@pytest.mark.unit
def test_restore_returns_file_to_original_path(folder_with_track):
    folder, audio, track = folder_with_track
    manager = TrashManager(folder)
    trash_id = manager.move_to_trash(track)

    restored = manager.restore(trash_id)

    assert restored == audio
    assert audio.exists()
    assert audio.read_bytes() == b"AUDIO_BYTES"
    assert manager.get(trash_id) is None
    manifest = json.loads((folder / ".monovault" / "trash" / "manifest.json").read_text())
    assert trash_id not in manifest


@pytest.mark.unit
def test_restore_collision_appends_suffix(folder_with_track):
    folder, audio, track = folder_with_track
    manager = TrashManager(folder)
    trash_id = manager.move_to_trash(track)

    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"DIFFERENT")

    restored = manager.restore(trash_id)

    assert restored != audio
    assert restored.name == "01 - Song (restored).mp3"
    assert restored.read_bytes() == b"AUDIO_BYTES"
    assert audio.read_bytes() == b"DIFFERENT"


@pytest.mark.unit
def test_restore_collision_escalates_numeric_suffix(folder_with_track):
    folder, audio, track = folder_with_track
    manager = TrashManager(folder)
    trash_id = manager.move_to_trash(track)

    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"A")
    (audio.parent / "01 - Song (restored).mp3").write_bytes(b"B")

    restored = manager.restore(trash_id)

    assert restored.name == "01 - Song (restored 2).mp3"


@pytest.mark.unit
def test_restore_unknown_id_raises(tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    manager = TrashManager(folder)

    with pytest.raises(KeyError):
        manager.restore("nope")


@pytest.mark.unit
def test_purge_removes_file_and_manifest_entry(folder_with_track):
    folder, _audio, track = folder_with_track
    manager = TrashManager(folder)
    trash_id = manager.move_to_trash(track)

    manager.purge(trash_id)

    trash_dir = folder / ".monovault" / "trash"
    moved_files = [p for p in trash_dir.iterdir() if p.suffix == ".mp3"]
    assert moved_files == []
    assert manager.get(trash_id) is None


@pytest.mark.unit
def test_purge_unknown_id_is_noop(tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    manager = TrashManager(folder)

    manager.purge("nonexistent")  # should not raise


@pytest.mark.unit
def test_list_entries_returns_typed_records(folder_with_track):
    folder, _audio, track = folder_with_track
    manager = TrashManager(folder)
    trash_id = manager.move_to_trash(track)

    entries = manager.list_entries()

    assert len(entries) == 1
    entry = entries[0]
    assert isinstance(entry, TrashEntry)
    assert entry.trash_id == trash_id
    assert entry.title == "Song"
    assert entry.categories == ["rock", "90s"]


@pytest.mark.unit
def test_manifest_survives_corrupt_load(tmp_path):
    folder = tmp_path / "library"
    (folder / ".monovault" / "trash").mkdir(parents=True)
    (folder / ".monovault" / "trash" / "manifest.json").write_text("not json")

    manager = TrashManager(folder)

    assert manager.list_entries() == []


@pytest.mark.unit
def test_manifest_persists_across_instances(folder_with_track):
    folder, _audio, track = folder_with_track
    manager = TrashManager(folder)
    trash_id = manager.move_to_trash(track)

    fresh_manager = TrashManager(folder)
    entry = fresh_manager.get(trash_id)
    assert entry is not None
    assert entry.title == "Song"


@pytest.mark.unit
def test_manifest_write_is_atomic(folder_with_track, monkeypatch):
    """If the tmp write succeeds but os.replace raises, the original manifest must remain readable."""
    folder, _audio, track = folder_with_track
    manager = TrashManager(folder)
    first_id = manager.move_to_trash(track)

    second_audio = folder / "Artist" / "Album" / "02 - Other.mp3"
    second_audio.write_bytes(b"OTHER")
    second_track = _track_for(second_audio, folder)

    import os as _os

    def boom(_src, _dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(_os, "replace", boom)

    with pytest.raises(OSError):
        manager.move_to_trash(second_track)

    fresh = TrashManager(folder)
    ids = [e.trash_id for e in fresh.list_entries()]
    assert ids == [first_id]
