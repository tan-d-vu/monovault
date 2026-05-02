from src.core.duplicates import DURATION_TOLERANCE_SECONDS, find_duplicates
from src.models.track import Track


def make_track(
    track_id: int,
    file_path: str,
    title: str = "Title",
    artist: str = "Artist",
    album: str = "Album",
    duration: float = 180.0,
) -> Track:
    return Track(
        id=track_id,
        file_path=file_path,
        title=title,
        artist=artist,
        album=album,
        duration=duration,
        categories=[],
        album_art=None,
        folder_path="/tmp",
    )


def _ids_in_groups(groups) -> list[set[int]]:
    return [{t.id for t in g.tracks} for g in groups]


def test_empty_input_returns_no_groups():
    assert find_duplicates([]) == []


def test_single_track_returns_no_groups():
    assert find_duplicates([make_track(1, "/a.mp3")]) == []


def test_no_duplicates_returns_no_groups():
    tracks = [
        make_track(1, "/a/song1.mp3", title="Alpha", artist="Anne"),
        make_track(2, "/a/song2.mp3", title="Beta", artist="Bob"),
        make_track(3, "/a/song3.mp3", title="Gamma", artist="Carl"),
    ]
    assert find_duplicates(tracks) == []


def test_rule_a_artist_and_title_match():
    # Track 3 shares the title but has a wildly different duration so rule C
    # doesn't pull it in — isolating rule A is the point of this test.
    tracks = [
        make_track(1, "/a/x.mp3", title="Bohemian Rhapsody", artist="Queen", duration=355.0),
        make_track(2, "/b/y.mp3", title="bohemian rhapsody", artist="QUEEN", duration=355.0),
        make_track(3, "/c/z.mp3", title="Bohemian Rhapsody", artist="Other", duration=120.0),
    ]
    groups = find_duplicates(tracks)
    assert _ids_in_groups(groups) == [{1, 2}]


def test_rule_b_filename_match_normalizes_case():
    tracks = [
        make_track(1, "/dir1/track.MP3", title="A", artist="X"),
        make_track(2, "/dir2/Track.mp3", title="B", artist="Y"),
        make_track(3, "/dir3/other.mp3", title="C", artist="Z"),
    ]
    groups = find_duplicates(tracks)
    assert _ids_in_groups(groups) == [{1, 2}]


def test_rule_c_title_and_duration_within_tolerance():
    tracks = [
        make_track(1, "/a.mp3", title="Same Song", artist="A1", duration=180.0),
        make_track(2, "/b.mp3", title="Same Song", artist="A2", duration=180.5),
        make_track(3, "/c.mp3", title="Same Song", artist="A3", duration=185.0),
    ]
    groups = find_duplicates(tracks)
    assert _ids_in_groups(groups) == [{1, 2}]


def test_rule_c_exact_tolerance_boundary_is_included():
    tracks = [
        make_track(1, "/a.mp3", title="Edge", artist="X", duration=100.0),
        make_track(2, "/b.mp3", title="Edge", artist="Y", duration=100.0 + DURATION_TOLERANCE_SECONDS),
    ]
    groups = find_duplicates(tracks)
    assert _ids_in_groups(groups) == [{1, 2}]


def test_rule_c_just_outside_tolerance_excluded():
    tracks = [
        make_track(1, "/a.mp3", title="Edge", artist="X", duration=100.0),
        make_track(
            2, "/b.mp3", title="Edge", artist="Y", duration=100.0 + DURATION_TOLERANCE_SECONDS + 0.01
        ),
    ]
    assert find_duplicates(tracks) == []


def test_rule_c_chains_via_consecutive_durations():
    tracks = [
        make_track(1, "/a.mp3", title="Chain", artist="X", duration=100.0),
        make_track(2, "/b.mp3", title="Chain", artist="Y", duration=100.5),
        make_track(3, "/c.mp3", title="Chain", artist="Z", duration=101.3),
    ]
    groups = find_duplicates(tracks)
    assert _ids_in_groups(groups) == [{1, 2, 3}]


def test_missing_metadata_falls_back_to_filename():
    tracks = [
        make_track(1, "/x/song.mp3", title="", artist="", duration=200.0),
        make_track(2, "/y/song.mp3", title="", artist="", duration=300.0),
    ]
    groups = find_duplicates(tracks)
    assert _ids_in_groups(groups) == [{1, 2}]


def test_rules_are_unioned_transitively():
    # 1 and 2 match by artist+title.
    # 2 and 3 match by filename.
    # 3 has nothing in common with 1 directly.
    # Expect a single merged group {1, 2, 3}.
    tracks = [
        make_track(1, "/dir1/aaa.mp3", title="Song", artist="Band"),
        make_track(2, "/dir2/shared.mp3", title="Song", artist="Band"),
        make_track(3, "/dir3/shared.mp3", title="Different", artist="Other"),
    ]
    groups = find_duplicates(tracks)
    assert _ids_in_groups(groups) == [{1, 2, 3}]


def test_groups_are_sorted_largest_first():
    tracks = [
        # Group of 3 by filename
        make_track(1, "/a/dup.mp3", title="X", artist="A"),
        make_track(2, "/b/dup.mp3", title="Y", artist="B"),
        make_track(3, "/c/dup.mp3", title="Z", artist="C"),
        # Group of 2 by artist+title
        make_track(4, "/d/p.mp3", title="Pair", artist="P"),
        make_track(5, "/e/q.mp3", title="Pair", artist="P"),
    ]
    groups = find_duplicates(tracks)
    assert [len(g.tracks) for g in groups] == [3, 2]
