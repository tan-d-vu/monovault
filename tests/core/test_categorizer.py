"""Tests for Categorizer with pluggable sources."""

from unittest.mock import MagicMock, patch
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
        result = categorizer.get_suggestions(None)
        assert result == []


class TestCategorizerAddCategory:
    def test_add_category_success(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["rock"])
        with patch(
            "src.core.categorizer.write_comment", return_value=True
        ) as mock_write:
            result = categorizer.add_category(track, "jazz")
        assert result is True
        assert "jazz" in track.categories
        library.update_track.assert_called_once_with(track)
        mock_write.assert_called_once_with("/tmp/track.mp3", ["rock", "jazz"])

    def test_add_duplicate_category_returns_false(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["rock"])
        with patch("src.core.categorizer.write_comment", return_value=True):
            result = categorizer.add_category(track, "Rock")
        assert result is False
        library.update_track.assert_not_called()

    def test_add_empty_category_returns_false(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track()
        result = categorizer.add_category(track, "  ")
        assert result is False

    def test_add_category_write_failure_rolls_back(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["rock"])
        with patch("src.core.categorizer.write_comment", return_value=False):
            result = categorizer.add_category(track, "jazz")
        assert result is False
        assert "jazz" not in track.categories
        library.update_track.assert_not_called()


class TestCategorizerRemoveCategory:
    def test_remove_category_success(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["rock", "jazz"])
        with patch(
            "src.core.categorizer.write_comment", return_value=True
        ) as mock_write:
            result = categorizer.remove_category(track, "rock")
        assert result is True
        assert "rock" not in track.categories
        assert "jazz" in track.categories
        library.update_track.assert_called_once_with(track)
        mock_write.assert_called_once_with("/tmp/track.mp3", ["jazz"])

    def test_remove_missing_category_returns_false(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["rock"])
        with patch("src.core.categorizer.write_comment", return_value=True):
            result = categorizer.remove_category(track, "jazz")
        assert result is False
        library.update_track.assert_not_called()

    def test_remove_category_write_failure_rolls_back(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track(categories=["rock", "jazz"])
        with patch("src.core.categorizer.write_comment", return_value=False):
            result = categorizer.remove_category(track, "rock")
        assert result is False
        assert "rock" in track.categories
        library.update_track.assert_not_called()
