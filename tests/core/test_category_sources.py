"""Tests for pluggable category suggestion sources."""
import pytest
from unittest.mock import MagicMock
from src.core.category_sources import ArtistCategorySource, SimilarCategoryCategorySource
from src.models.track import Track


def make_track(id, artist="Artist", categories=None, file_path="/tmp/t.mp3"):
    return Track(
        id=id,
        file_path=file_path,
        title=f"Track {id}",
        artist=artist,
        album="Album",
        duration=180.0,
        categories=categories or [],
        album_art=None,
        folder_path="/tmp",
    )


class TestArtistCategorySource:
    def test_suggests_from_same_artist(self):
        repo = MagicMock()
        other = make_track(2, categories=["rock", "live"])
        repo.get_tracks_by_artist.return_value = [make_track(1), other]
        source = ArtistCategorySource(repo)
        track = make_track(1)
        result = source.get_suggestions(track, set(), max_results=5)
        assert ("rock", "same artist") in result
        assert ("live", "same artist") in result

    def test_excludes_self(self):
        repo = MagicMock()
        self_track = make_track(1, categories=["jazz"])
        repo.get_tracks_by_artist.return_value = [self_track]
        source = ArtistCategorySource(repo)
        result = source.get_suggestions(self_track, set(), max_results=5)
        assert result == []

    def test_empty_artist_returns_empty(self):
        repo = MagicMock()
        source = ArtistCategorySource(repo)
        track = make_track(1, artist="")
        result = source.get_suggestions(track, set(), max_results=5)
        assert result == []
        repo.get_tracks_by_artist.assert_not_called()

    def test_label_is_same_artist(self):
        repo = MagicMock()
        other = make_track(2, categories=["blues"])
        repo.get_tracks_by_artist.return_value = [make_track(1), other]
        source = ArtistCategorySource(repo)
        result = source.get_suggestions(make_track(1), set(), max_results=5)
        assert all(label == "same artist" for _, label in result)

    def test_respects_max_results(self):
        repo = MagicMock()
        other = make_track(2, categories=["a", "b", "c", "d", "e", "f"])
        repo.get_tracks_by_artist.return_value = [make_track(1), other]
        source = ArtistCategorySource(repo)
        result = source.get_suggestions(make_track(1), set(), max_results=3)
        assert len(result) == 3

    def test_deduplicates_across_tracks(self):
        repo = MagicMock()
        t2 = make_track(2, categories=["rock"])
        t3 = make_track(3, categories=["rock"])
        repo.get_tracks_by_artist.return_value = [make_track(1), t2, t3]
        source = ArtistCategorySource(repo)
        result = source.get_suggestions(make_track(1), set(), max_results=5)
        cats = [cat for cat, _ in result]
        assert cats.count("rock") == 1

    def test_excludes_existing_categories(self):
        repo = MagicMock()
        other = make_track(2, categories=["rock", "jazz"])
        repo.get_tracks_by_artist.return_value = [make_track(1), other]
        source = ArtistCategorySource(repo)
        result = source.get_suggestions(make_track(1), {"rock"}, max_results=5)
        cats = [cat for cat, _ in result]
        assert "rock" not in cats
        assert "jazz" in cats


class TestSimilarCategoryCategorySource:
    def test_suggests_from_similar_tracks(self):
        repo = MagicMock()
        other = make_track(2, categories=["blues", "acoustic"])
        repo.get_tracks_with_categories.return_value = [other]
        source = SimilarCategoryCategorySource(repo)
        track = make_track(1, categories=["rock"])
        result = source.get_suggestions(track, {"rock"}, max_results=5)
        assert ("blues", "similar category") in result
        assert ("acoustic", "similar category") in result

    def test_excludes_self(self):
        repo = MagicMock()
        track = make_track(1, categories=["rock"])
        repo.get_tracks_with_categories.return_value = [track]
        source = SimilarCategoryCategorySource(repo)
        result = source.get_suggestions(track, {"rock"}, max_results=5)
        assert result == []

    def test_empty_categories_returns_empty(self):
        repo = MagicMock()
        source = SimilarCategoryCategorySource(repo)
        track = make_track(1, categories=[])
        result = source.get_suggestions(track, set(), max_results=5)
        assert result == []
        repo.get_tracks_with_categories.assert_not_called()

    def test_label_is_similar_category(self):
        repo = MagicMock()
        other = make_track(2, categories=["jazz"])
        repo.get_tracks_with_categories.return_value = [other]
        source = SimilarCategoryCategorySource(repo)
        track = make_track(1, categories=["blues"])
        result = source.get_suggestions(track, {"blues"}, max_results=5)
        assert all(label == "similar category" for _, label in result)

    def test_respects_max_results(self):
        repo = MagicMock()
        other = make_track(2, categories=["a", "b", "c", "d", "e", "f"])
        repo.get_tracks_with_categories.return_value = [other]
        source = SimilarCategoryCategorySource(repo)
        track = make_track(1, categories=["rock"])
        result = source.get_suggestions(track, {"rock"}, max_results=2)
        assert len(result) == 2
