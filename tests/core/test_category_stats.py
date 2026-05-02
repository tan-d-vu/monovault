from src.core.category_stats import compute_stats
from src.models.track import Track


def make_track(id=1, categories=None):
    return Track(
        id=id,
        file_path=f"/tmp/track{id}.mp3",
        title="Test Track",
        artist="Artist",
        album="Album",
        duration=180.0,
        categories=list(categories) if categories else [],
        album_art=None,
        folder_path="/tmp",
    )


class TestComputeStats:
    def test_empty_list(self):
        stats = compute_stats([])
        assert stats.counts == {}
        assert stats.untagged_count == 0
        assert stats.co_occurrences == []
        assert stats.total_tracks == 0

    def test_all_untagged(self):
        tracks = [make_track(id=i) for i in range(3)]
        stats = compute_stats(tracks)
        assert stats.counts == {}
        assert stats.untagged_count == 3

    def test_single_category_single_track(self):
        stats = compute_stats([make_track(categories=["rock"])])
        assert stats.counts == {"rock": 1}
        assert stats.co_occurrences == []

    def test_mixed_case_deduped_per_track(self):
        stats = compute_stats([make_track(categories=["Rock", "rock"])])
        assert stats.counts == {"rock": 1}

    def test_pair_counted_correctly(self):
        t1 = make_track(id=1, categories=["rock", "jazz"])
        t2 = make_track(id=2, categories=["rock", "jazz"])
        stats = compute_stats([t1, t2])
        assert ("jazz", "rock", 2) in stats.co_occurrences

    def test_top_pairs_cap(self):
        tracks = []
        for i in range(10):
            tracks.append(make_track(id=i, categories=[f"cat{i}", f"cat{i+1}"]))
        stats = compute_stats(tracks, top_pairs=2)
        assert len(stats.co_occurrences) <= 2

    def test_orphans_threshold_1(self):
        t1 = make_track(id=1, categories=["rock"])
        t2 = make_track(id=2, categories=["rock"])
        t3 = make_track(id=3, categories=["jazz"])
        stats = compute_stats([t1, t2, t3])
        assert stats.orphans(threshold=1) == ["jazz"]

    def test_orphans_threshold_3(self):
        tracks = [make_track(id=i, categories=["rock"]) for i in range(4)]
        tracks += [make_track(id=10, categories=["jazz"])]
        tracks += [make_track(id=11, categories=["jazz"])]
        tracks += [make_track(id=12, categories=["blues"])]
        stats = compute_stats(tracks)
        # rock:4, jazz:2, blues:1
        assert "blues" in stats.orphans(threshold=3)
        assert "jazz" in stats.orphans(threshold=3)
        assert "rock" not in stats.orphans(threshold=3)
