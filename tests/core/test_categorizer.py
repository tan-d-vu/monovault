"""Tests for Categorizer with pluggable sources."""

from unittest.mock import MagicMock

import pytest

from src.core.categorizer import Categorizer
from src.core.library import LibraryManager
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

    def test_rejects_internal_whitespace(self):
        library = MagicMock()
        categorizer = Categorizer(library)
        track = make_track()
        assert categorizer.parse_add_category(track, "classical music") is None
        assert categorizer.parse_add_category(track, "a\tb") is None


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


@pytest.mark.unit
class TestReplaceCategoriesEverywhere:
    def _make_library(self, *tracks):
        library = LibraryManager()
        for t in tracks:
            library.add_track(t)
        return library

    def test_rename_basic(self):
        t1 = make_track(id=1, categories=["rock", "90s"])
        t2 = make_track(id=2, categories=["jazz"])
        library = self._make_library(t1, t2)
        cat = Categorizer(library)

        modified = cat.replace_categories_everywhere({"rock"}, "metal")

        assert {t.id for t in modified} == {1}
        assert library.get_track_by_id(1).categories == ["metal", "90s"]
        assert library.get_track_by_id(1).comments == "metal 90s"
        assert library.get_track_by_id(2).categories == ["jazz"]

    def test_rename_case_insensitive_source_match(self):
        t1 = make_track(id=1, categories=["Rock"])
        library = self._make_library(t1)
        cat = Categorizer(library)

        modified = cat.replace_categories_everywhere({"ROCK"}, "metal")

        assert len(modified) == 1
        assert library.get_track_by_id(1).categories == ["metal"]

    def test_rename_dedup_when_target_already_present(self):
        t1 = make_track(id=1, categories=["rock", "metal"])
        library = self._make_library(t1)
        cat = Categorizer(library)

        modified = cat.replace_categories_everywhere({"rock"}, "metal")

        assert len(modified) == 1
        assert library.get_track_by_id(1).categories == ["metal"]

    def test_rename_comments_updated(self):
        t1 = make_track(id=1, categories=["rock"])
        library = self._make_library(t1)
        cat = Categorizer(library)

        cat.replace_categories_everywhere({"rock"}, "metal")

        assert library.get_track_by_id(1).comments == "metal"

    def test_merge_multiple_sources(self):
        t1 = make_track(id=1, categories=["rock", "punk"])
        t2 = make_track(id=2, categories=["punk"])
        library = self._make_library(t1, t2)
        cat = Categorizer(library)

        modified = cat.replace_categories_everywhere({"rock", "punk"}, "metal")

        assert {t.id for t in modified} == {1, 2}
        assert library.get_track_by_id(1).categories == ["metal"]
        assert library.get_track_by_id(2).categories == ["metal"]

    def test_merge_target_in_sources_ignored(self):
        t1 = make_track(id=1, categories=["rock", "metal"])
        library = self._make_library(t1)
        cat = Categorizer(library)

        # metal is in both sources and target — should only replace rock
        modified = cat.replace_categories_everywhere({"rock", "metal"}, "metal")

        assert len(modified) == 1
        assert library.get_track_by_id(1).categories == ["metal"]

    def test_delete_removes_from_all_tracks(self):
        t1 = make_track(id=1, categories=["rock", "90s"])
        t2 = make_track(id=2, categories=["rock"])
        library = self._make_library(t1, t2)
        cat = Categorizer(library)

        modified = cat.replace_categories_everywhere({"rock"}, None)

        assert {t.id for t in modified} == {1, 2}
        assert library.get_track_by_id(1).categories == ["90s"]
        assert library.get_track_by_id(2).categories == []

    def test_delete_case_insensitive(self):
        t1 = make_track(id=1, categories=["Rock"])
        library = self._make_library(t1)
        cat = Categorizer(library)

        cat.replace_categories_everywhere({"rock"}, None)

        assert library.get_track_by_id(1).categories == []

    def test_delete_no_matching_tracks_returns_empty(self):
        t1 = make_track(id=1, categories=["jazz"])
        library = self._make_library(t1)
        cat = Categorizer(library)

        result = cat.replace_categories_everywhere({"rock"}, None)

        assert result == []
        assert library.get_track_by_id(1).categories == ["jazz"]

    def test_empty_target_raises_value_error(self):
        library = self._make_library()
        cat = Categorizer(library)

        with pytest.raises(ValueError):
            cat.replace_categories_everywhere({"rock"}, "")

    def test_whitespace_target_raises_value_error(self):
        library = self._make_library()
        cat = Categorizer(library)

        with pytest.raises(ValueError):
            cat.replace_categories_everywhere({"rock"}, "hello world")

    def test_none_target_is_valid(self):
        library = self._make_library()
        cat = Categorizer(library)
        # Should not raise
        result = cat.replace_categories_everywhere({"rock"}, None)
        assert result == []

    def test_no_matching_tracks_returns_empty_list(self):
        t1 = make_track(id=1, categories=["jazz"])
        library = self._make_library(t1)
        cat = Categorizer(library)

        result = cat.replace_categories_everywhere({"rock"}, "metal")

        assert result == []
        assert library.get_track_by_id(1).categories == ["jazz"]
