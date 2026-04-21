"""Tests for Categorizer with pluggable sources."""

from unittest.mock import MagicMock

from src.core.categorizer import Categorizer
from src.models.track import Track


def make_track(id=1, categories=None):
    return Track(
        id=id,
        file_path="/tmp/track.mp3",
        title="Test Track",
        artist="Artist",
        album="Album",
        duration=180.0,
        categories=list(categories) if categories else [],
        album_art=None,
        folder_path="/tmp",
    )


class TestCategorizerGetSuggestions:
    def test_delegates_to_sources_and_deduplicates(self):
        library = MagicMock()
        source1 = MagicMock()
        source1.get_suggestions.return_value = [
            ("rock", "same artist"),
            ("jazz", "same artist"),
        ]
        source2 = MagicMock()
        source2.get_suggestions.return_value = [
            ("rock", "similar category"),
            ("blues", "similar category"),
        ]
        categorizer = Categorizer(library, sources=[source1, source2])
        track = make_track()
        result = categorizer.get_suggestions(track, max_suggestions=5)
        cats = [cat for cat, _ in result]
        # rock from source1 should appear only once
        assert cats.count("rock") == 1
        assert "jazz" in cats
        assert "blues" in cats

    def test_no_sources_returns_empty(self):
        library = MagicMock()
        categorizer = Categorizer(library, sources=[])
        result = categorizer.get_suggestions(make_track())
        assert result == []

    def test_respects_max_suggestions(self):
        library = MagicMock()
        source = MagicMock()
        source.get_suggestions.return_value = [
            ("a", "x"),
            ("b", "x"),
            ("c", "x"),
            ("d", "x"),
            ("e", "x"),
            ("f", "x"),
        ]
        categorizer = Categorizer(library, sources=[source])
        result = categorizer.get_suggestions(make_track(), max_suggestions=3)
        assert len(result) == 3

    def test_none_track_returns_empty(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        result = categorizer.get_suggestions(None)  # type: ignore[arg-type]
        assert result == []


class TestCategorizerParseAddCategory:
    def test_returns_normalized_category(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["rock"])
        result = categorizer.parse_add_category(track, "  Jazz  ")
        assert result == "jazz"

    def test_returns_none_for_empty(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track()
        assert categorizer.parse_add_category(track, "  ") is None

    def test_returns_none_for_duplicate(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["rock"])
        assert categorizer.parse_add_category(track, "Rock") is None

    def test_case_insensitive_duplicate_check(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["ROCK"])
        assert categorizer.parse_add_category(track, "rock") is None


class TestCategorizerParseRemoveCategory:
    def test_returns_lowercased_match(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["Rock", "jazz"])
        result = categorizer.parse_remove_category(track, "Rock")
        assert result == "rock"

    def test_case_insensitive_match(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["Rock"])
        result = categorizer.parse_remove_category(track, "ROCK")
        assert result == "rock"

    def test_returns_none_when_not_found(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["rock"])
        assert categorizer.parse_remove_category(track, "jazz") is None


class TestCategorizerApplyCategories:
    def test_overwrites_categories_and_updates_library(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["rock"])
        categorizer.apply_categories(track, ["jazz", "pop"])
        assert track.categories == ["jazz", "pop"]
        library.update_track.assert_called_once_with(track)

    def test_clears_all_categories(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["rock", "jazz"])
        categorizer.apply_categories(track, [])
        assert track.categories == []
        library.update_track.assert_called_once_with(track)
