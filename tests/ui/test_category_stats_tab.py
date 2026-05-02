"""Tests for CategoryStatsTab widget."""

import pytest

from src.core.library import LibraryManager
from src.models.track import Track
from src.ui.category_stats_tab import UNTAGGED_SENTINEL, CategoryStatsTab


def make_track(id=1, categories=None, artist="Artist"):
    return Track(
        id=id,
        file_path=f"/tmp/track{id}.mp3",
        title=f"Track {id}",
        artist=artist,
        album="Album",
        duration=180.0,
        categories=list(categories) if categories else [],
        album_art=None,
        folder_path="/tmp",
    )


def make_library(*tracks):
    library = LibraryManager()
    for t in tracks:
        library.add_track(t)
    return library


@pytest.mark.unit
class TestCategoryStatsTab:
    def test_after_refresh_row_count_equals_unique_categories(self, qapp):
        library = make_library(
            make_track(id=1, categories=["rock", "jazz"]),
            make_track(id=2, categories=["rock"]),
        )
        tab = CategoryStatsTab(library)
        tab.refresh()

        assert tab._category_table.rowCount() == 2

    def test_search_filter_hides_non_matching_rows(self, qapp):
        library = make_library(
            make_track(id=1, categories=["rock"]),
            make_track(id=2, categories=["jazz"]),
        )
        tab = CategoryStatsTab(library)
        tab.refresh()

        tab._search_input.setText("rock")

        # jazz row should be hidden, rock row visible
        visible = [
            row
            for row in range(tab._category_table.rowCount())
            if not tab._category_table.isRowHidden(row)
        ]
        assert len(visible) == 1
        item = tab._category_table.item(visible[0], 0)
        assert item is not None
        assert item.text() == "rock"

    def test_double_click_emits_category_filter_requested(self, qapp):
        library = make_library(make_track(id=1, categories=["rock"]))
        tab = CategoryStatsTab(library)
        tab.refresh()

        emitted = []
        tab.category_filter_requested.connect(emitted.append)

        name_item = tab._category_table.item(0, 0)
        assert name_item is not None
        tab._on_category_activated(name_item)

        assert emitted == ["rock"]

    def test_untagged_button_emits_sentinel(self, qapp):
        library = make_library(make_track(id=1))  # no categories
        tab = CategoryStatsTab(library)
        tab.refresh()

        emitted = []
        tab.category_filter_requested.connect(emitted.append)
        tab._untagged_btn.click()

        assert emitted == [UNTAGGED_SENTINEL]

    def test_invalidate_then_show_if_dirty_triggers_recompute(self, qapp):
        library = make_library(make_track(id=1, categories=["rock"]))
        tab = CategoryStatsTab(library)
        tab.refresh()

        # Add a new track category directly to library
        t2 = make_track(id=2, categories=["jazz"])
        library.add_track(t2)

        tab.invalidate()
        assert tab._dirty is True

        tab.show_if_dirty()

        assert tab._dirty is False
        assert tab._stats is not None
        assert "jazz" in tab._stats.counts

    def test_refresh_shows_correct_summary(self, qapp):
        library = make_library(
            make_track(id=1, categories=["rock"]),
            make_track(id=2),  # untagged
        )
        tab = CategoryStatsTab(library)
        tab.refresh()

        summary = tab._summary_label.text()
        assert "1 unique" in summary
        assert "1 untagged" in summary

    def test_orphan_flagged_in_table(self, qapp):
        library = make_library(make_track(id=1, categories=["rare"]))
        tab = CategoryStatsTab(library)
        tab.refresh()

        # "rare" has count=1, orphan_threshold=1 → flag "⚠"
        flag_item = tab._category_table.item(0, 2)
        assert flag_item is not None
        assert flag_item.text() == "⚠"
