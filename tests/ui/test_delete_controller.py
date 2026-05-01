"""Tests for src/ui/controllers/delete_controller.py.

Strategy: real LibraryManager + real TrashManager (cheap; both touch only
tmp_path or in-memory dicts), but the PlaybackEngine and Scanner are mocked.
This way we can assert the file actually moved on disk while still
controlling the side-effects on Qt's media subsystem (which is unhelpfully
real).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.library import LibraryManager
from src.core.library_store import LibraryStore
from src.core.trash import TrashManager
from src.models.track import Track
from src.ui.controllers.delete_controller import DeleteController


def make_track(
    track_id: int,
    file_path: str,
    folder_path: str,
    *,
    date_added: str = "2024-06-12",
) -> Track:
    return Track(
        id=track_id,
        file_path=file_path,
        title="Song",
        artist="Artist",
        album="Album",
        duration=180.0,
        categories=["rock"],
        album_art=None,
        folder_path=folder_path,
        comments="rock",
        date_added=date_added,
    )


@pytest.fixture
def folders_with_tracks(tmp_path: Path):
    """Two watched folders, each with one real audio file in it."""
    folder_a = tmp_path / "library_a"
    folder_b = tmp_path / "library_b"
    folder_a.mkdir()
    folder_b.mkdir()

    file_a = folder_a / "Artist" / "Album" / "01.mp3"
    file_b = folder_b / "Track.mp3"
    file_a.parent.mkdir(parents=True)
    file_a.write_bytes(b"AAA")
    file_b.write_bytes(b"BBB")

    return folder_a, folder_b, file_a, file_b


@pytest.fixture
def controller(folders_with_tracks):
    folder_a, folder_b, _file_a, _file_b = folders_with_tracks
    library = LibraryManager()
    library.config = MagicMock()
    library.folders = [str(folder_a), str(folder_b)]
    library.config.get_folders.return_value = list(library.folders)

    playback = MagicMock()
    playback.current_track.return_value = None
    scanner = MagicMock()

    return DeleteController(library, playback, scanner), library, playback, scanner


@pytest.mark.unit
class TestDeleteTracks:
    def test_moves_file_to_trash_and_removes_from_library(
        self, qapp, controller, folders_with_tracks
    ):
        ctrl, library, _playback, _scanner = controller
        folder_a, _folder_b, file_a, _file_b = folders_with_tracks
        track = make_track(1, str(file_a), str(folder_a))
        library.add_track(track)

        results: list[int] = []
        ctrl.delete_completed.connect(lambda count: results.append(count))

        ctrl.delete_tracks([track])

        assert results == [1]
        assert not file_a.exists()
        assert library.get_track_by_id(track.id) is None
        # Trash manifest received the entry
        manager = TrashManager(folder_a)
        assert len(manager.list_entries()) == 1

    def test_groups_by_folder(self, qapp, controller, folders_with_tracks):
        ctrl, library, _playback, _scanner = controller
        folder_a, folder_b, file_a, file_b = folders_with_tracks
        track_a = make_track(1, str(file_a), str(folder_a))
        track_b = make_track(2, str(file_b), str(folder_b))
        library.add_track(track_a)
        library.add_track(track_b)

        ctrl.delete_tracks([track_a, track_b])

        assert len(TrashManager(folder_a).list_entries()) == 1
        assert len(TrashManager(folder_b).list_entries()) == 1

    def test_stops_playback_when_current_track_is_deleted(
        self, qapp, controller, folders_with_tracks
    ):
        ctrl, library, playback, _scanner = controller
        folder_a, _folder_b, file_a, _file_b = folders_with_tracks
        track = make_track(1, str(file_a), str(folder_a))
        library.add_track(track)
        playback.current_track.return_value = str(file_a)

        ctrl.delete_tracks([track])

        playback.stop.assert_called_once()
        playback.player.setSource.assert_called_once()

    def test_skips_playback_release_when_current_track_unaffected(
        self, qapp, controller, folders_with_tracks
    ):
        ctrl, library, playback, _scanner = controller
        folder_a, _folder_b, file_a, _file_b = folders_with_tracks
        track = make_track(1, str(file_a), str(folder_a))
        library.add_track(track)
        playback.current_track.return_value = "/something/else.mp3"

        ctrl.delete_tracks([track])

        playback.stop.assert_not_called()
        playback.player.setSource.assert_not_called()

    def test_partial_failure_emits_count_and_first_error(
        self, qapp, controller, folders_with_tracks
    ):
        ctrl, library, _playback, _scanner = controller
        folder_a, _folder_b, file_a, _file_b = folders_with_tracks
        good = make_track(1, str(file_a), str(folder_a))
        bad = make_track(2, str(folder_a / "ghost.mp3"), str(folder_a))
        library.add_track(good)
        library.add_track(bad)

        completed: list[int] = []
        failed: list[tuple[str, int]] = []
        ctrl.delete_completed.connect(lambda count: completed.append(count))
        ctrl.delete_failed.connect(lambda msg, count: failed.append((msg, count)))

        ctrl.delete_tracks([good, bad])

        assert completed == []
        assert len(failed) == 1
        assert failed[0][1] == 1
        assert library.get_track_by_id(good.id) is None
        assert library.get_track_by_id(bad.id) is not None

    def test_empty_input_emits_zero_count(self, qapp, controller):
        ctrl, _library, _playback, _scanner = controller
        results: list[int] = []
        ctrl.delete_completed.connect(lambda count: results.append(count))

        ctrl.delete_tracks([])

        assert results == [1] if False else results == [0]


@pytest.mark.unit
class TestRestore:
    def test_restore_re_adds_with_original_date_added(
        self, qapp, controller, folders_with_tracks
    ):
        ctrl, library, _playback, scanner = controller
        folder_a, _folder_b, file_a, _file_b = folders_with_tracks
        track = make_track(1, str(file_a), str(folder_a), date_added="2020-01-15")
        library.add_track(track)

        ctrl.delete_tracks([track])
        entries = ctrl.list_all_trash()
        assert len(entries) == 1

        rebuilt = make_track(0, str(file_a), str(folder_a), date_added="")
        scanner.process_file.return_value = rebuilt

        restored: list[list[Track]] = []
        ctrl.restore_completed.connect(lambda tracks: restored.append(tracks))

        ctrl.restore(entries)

        assert len(restored) == 1
        assert len(restored[0]) == 1
        assert restored[0][0].date_added == "2020-01-15"
        assert file_a.exists()
        # LibraryStore should have the original date persisted
        store = LibraryStore(folder_a)
        assert store.get(str(file_a)) == "2020-01-15"

    def test_list_all_trash_aggregates_across_folders(
        self, qapp, controller, folders_with_tracks
    ):
        ctrl, library, _playback, _scanner = controller
        folder_a, folder_b, file_a, file_b = folders_with_tracks
        track_a = make_track(1, str(file_a), str(folder_a))
        track_b = make_track(2, str(file_b), str(folder_b))
        library.add_track(track_a)
        library.add_track(track_b)

        ctrl.delete_tracks([track_a, track_b])
        all_trash = ctrl.list_all_trash()

        folders_seen = {fp for fp, _entry in all_trash}
        assert folders_seen == {str(folder_a), str(folder_b)}


@pytest.mark.unit
class TestPurge:
    def test_purge_removes_file_and_manifest(
        self, qapp, controller, folders_with_tracks
    ):
        ctrl, library, _playback, _scanner = controller
        folder_a, _folder_b, file_a, _file_b = folders_with_tracks
        track = make_track(1, str(file_a), str(folder_a))
        library.add_track(track)

        ctrl.delete_tracks([track])
        entries = ctrl.list_all_trash()

        ctrl.purge(entries)

        assert ctrl.list_all_trash() == []
        trash_dir = folder_a / ".monovault" / "trash"
        leftovers = [p for p in trash_dir.iterdir() if p.suffix == ".mp3"]
        assert leftovers == []

    def test_empty_trash_clears_all_folders(
        self, qapp, controller, folders_with_tracks
    ):
        ctrl, library, _playback, _scanner = controller
        folder_a, folder_b, file_a, file_b = folders_with_tracks
        library.add_track(make_track(1, str(file_a), str(folder_a)))
        library.add_track(make_track(2, str(file_b), str(folder_b)))

        ctrl.delete_tracks(library.get_all_tracks())
        ctrl.empty_trash()

        assert ctrl.list_all_trash() == []
