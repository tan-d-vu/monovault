from collections import Counter
from dataclasses import dataclass
from itertools import combinations

from ..models.track import Track


@dataclass
class CategoryStats:
    counts: dict[str, int]
    untagged_count: int
    co_occurrences: list[tuple[str, str, int]]
    total_tracks: int

    def unique_count(self) -> int:
        return len(self.counts)

    def orphans(self, threshold: int = 1) -> list[str]:
        """Categories used by <= threshold tracks, sorted alphabetically."""
        return sorted(c for c, n in self.counts.items() if n <= threshold)


def compute_stats(tracks: list[Track], top_pairs: int = 20) -> CategoryStats:
    counts: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()
    untagged = 0

    for track in tracks:
        cats = sorted({c.lower() for c in track.categories})
        if not cats:
            untagged += 1
            continue
        for c in cats:
            counts[c] += 1
        for a, b in combinations(cats, 2):
            pair_counts[(a, b)] += 1

    pairs = sorted(
        ((a, b, n) for (a, b), n in pair_counts.items()),
        key=lambda x: (-x[2], x[0], x[1]),
    )[:top_pairs]

    return CategoryStats(
        counts=dict(counts),
        untagged_count=untagged,
        co_occurrences=pairs,
        total_tracks=len(tracks),
    )
