"""Metadata-based duplicate detection.

Three rules are evaluated independently and merged via union-find, so any
two tracks that match by *any* rule end up in the same group:

    1. Same artist + same title (case-insensitive, trimmed)
    2. Same filename (case-insensitive, trimmed)
    3. Same title + duration within DURATION_TOLERANCE_SECONDS

Tracks with empty title/artist still participate in rule 2.
Singleton groups are not reported.
"""

from dataclasses import dataclass

from ..models.track import Track

DURATION_TOLERANCE_SECONDS = 1.0


@dataclass
class DuplicateGroup:
    tracks: list[Track]


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))
        self._rank = [0] * size

    def find(self, i: int) -> int:
        root = i
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[i] != root:
            self._parent[i], i = root, self._parent[i]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1


def _norm(value: str) -> str:
    return value.strip().lower()


def find_duplicates(tracks: list[Track]) -> list[DuplicateGroup]:
    """Return duplicate groups (size >= 2), largest first."""
    if len(tracks) < 2:
        return []

    uf = _UnionFind(len(tracks))

    _union_by_artist_title(uf, tracks)
    _union_by_filename(uf, tracks)
    _union_by_title_and_duration(uf, tracks)

    components: dict[int, list[int]] = {}
    for i in range(len(tracks)):
        components.setdefault(uf.find(i), []).append(i)

    groups = [
        DuplicateGroup(tracks=[tracks[i] for i in indices])
        for indices in components.values()
        if len(indices) > 1
    ]
    groups.sort(key=lambda g: len(g.tracks), reverse=True)
    return groups


def _union_by_artist_title(uf: _UnionFind, tracks: list[Track]) -> None:
    buckets: dict[tuple[str, str], list[int]] = {}
    for i, track in enumerate(tracks):
        if not track.artist or not track.title:
            continue
        key = (_norm(track.artist), _norm(track.title))
        buckets.setdefault(key, []).append(i)
    for indices in buckets.values():
        for j in indices[1:]:
            uf.union(indices[0], j)


def _union_by_filename(uf: _UnionFind, tracks: list[Track]) -> None:
    buckets: dict[str, list[int]] = {}
    for i, track in enumerate(tracks):
        key = _norm(track.filename)
        if not key:
            continue
        buckets.setdefault(key, []).append(i)
    for indices in buckets.values():
        for j in indices[1:]:
            uf.union(indices[0], j)


def _union_by_title_and_duration(uf: _UnionFind, tracks: list[Track]) -> None:
    buckets: dict[str, list[tuple[int, float]]] = {}
    for i, track in enumerate(tracks):
        if not track.title:
            continue
        buckets.setdefault(_norm(track.title), []).append((i, track.duration))
    for entries in buckets.values():
        if len(entries) < 2:
            continue
        entries.sort(key=lambda pair: pair[1])
        for k in range(1, len(entries)):
            if entries[k][1] - entries[k - 1][1] <= DURATION_TOLERANCE_SECONDS:
                uf.union(entries[k - 1][0], entries[k][0])
