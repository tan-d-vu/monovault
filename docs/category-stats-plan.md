# Category Stats — Implementation Plan

## Goal

Add a third tab "Categories" alongside Library and Duplicates. The tab shows per-category usage statistics (counts, orphans, untagged tracks, top co-occurring pairs). Clicking a category filters the Library tab to tracks that use it.

This plan is **read-only** — no editing of categories. Editing is covered by `category-management-plan.md` and depends on this plan being implemented first.

## User decisions baked into this plan

- UI lives in a single new "Categories" tab in `MainWindow._tabs`.
- Stats include: per-category count, orphan flag, untagged track count, and top co-occurring pairs.
- Clicking a category in the stats table filters the Library tab to tracks with that category and switches to the Library tab.
- Stats are recomputed on demand (Refresh button + when the Categories tab becomes active + after a library scan completes). Not live-updating on every edit.

## Verified codebase facts (read these before coding)

- `LibraryManager` is at `src/core/library.py` and implements `ITrackRepository` (`src/core/interfaces.py:46`). It has `get_all_tracks() -> list[Track]`, plus `tracks: dict[int, Track]` and `update_track(track)`.
- `Track` is a plain `@dataclass` with `categories: list[str]` (`src/models/track.py:13`). It is mutable. There is also `track.comments: str` and a `categories_str` property — the comments string is kept in sync with categories by `panels.update_categories` (`src/ui/panels.py:340`).
- `SearchController` constructor: `__init__(self, repository: ITrackRepository, bus, debounce_ms=0, parent=None)` (`src/ui/controllers/search_controller.py:15`). Internal attribute is `self._repo`. It has a `_timer: QTimer` for debounced text-search; we must stop it before publishing a non-text-search result, otherwise a queued search will overwrite the filter.
- The `results_changed = pyqtSignal(list)` signal is what `MainWindow._on_search_results` listens to (`src/ui/main_window.py:519`). Emitting it sets `self.all_tracks` and repopulates the track table — the same pathway already used by free-text search and folder filtering. There is no separate "filter" pathway.
- There is no separate filter pathway: free-text search, folder checkbox filtering, and our new category filter are all mutually exclusive — whichever runs last wins. Same as the existing UX.
- `_NumericItem` (a `QTableWidgetItem` subclass that sorts numerically) is defined in two places already: `src/ui/track_table.py:62` and `src/ui/duplicates_tab.py:42`. Each module defines its own. Define a third one inline in `category_stats_tab.py` to match precedent.
- `tests/conftest.py` provides session-scoped `qapp`, plus `sample_track`, `sample_track_no_categories`, `sample_tracks`. Use them.
- `tests/core/test_categorizer.py` and `tests/core/test_duplicates.py` show the test style: a top-level `make_track(...)` helper, `MagicMock` for collaborators, plain `assert` rather than fixtures heavy with state.

## Architecture

### New file: `src/core/category_stats.py`

Pure logic, no Qt. Mirrors the structure of `src/core/duplicates.py`.

```python
from collections import Counter
from dataclasses import dataclass
from itertools import combinations

from ..models.track import Track


@dataclass
class CategoryStats:
    counts: dict[str, int]                       # lowercase category -> track count
    untagged_count: int                          # tracks with empty categories list
    co_occurrences: list[tuple[str, str, int]]   # (cat_a, cat_b, count) sorted desc by count, then alpha
    total_tracks: int

    def unique_count(self) -> int:
        return len(self.counts)

    def orphans(self, threshold: int = 1) -> list[str]:
        """Categories used by <= threshold tracks, sorted alphabetically."""
        return sorted(c for c, n in self.counts.items() if n <= threshold)


def compute_stats(tracks: list[Track], top_pairs: int = 20) -> CategoryStats:
    """Build category statistics. All categories are compared/stored lowercase."""
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
```

Notes:
- Categories are lowercased and deduped per track before counting (so a track with `["Rock", "rock"]` counts once for `rock`).
- `combinations` over sorted-unique cats produces canonical (alpha-ordered) pair tuples.
- `top_pairs=20` is a hard cap to keep the UI table small.

### Modified file: `src/ui/controllers/search_controller.py`

Add one method. The constructor and other methods stay untouched.

```python
def filter_by_category(self, category: str | None) -> None:
    """Emit results_changed with tracks matching `category` (case-insensitive),
    or with all untagged tracks if `category is None`.

    Bypasses the search text box. Cancels any pending debounced search so it
    doesn't overwrite the filter results.
    """
    self._timer.stop()
    all_tracks = self._repo.get_all_tracks()
    if category is None:
        results = [t for t in all_tracks if not t.categories]
    else:
        target = category.lower()
        results = [t for t in all_tracks if any(c.lower() == target for c in t.categories)]
    self._pending_query = ""
    self.results_changed.emit(results)
```

`_pending_query = ""` is reset so that if the user later types into the search box, the debounce fire path picks up only the new text.

### New file: `src/ui/category_stats_tab.py`

`CategoryStatsTab(QWidget)`. Reads from `LibraryManager`. Mirrors the structure of `src/ui/duplicates_tab.py`.

```python
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..core.category_stats import CategoryStats, compute_stats
from ..core.library import LibraryManager

UNTAGGED_SENTINEL = "__UNTAGGED__"


class _NumericItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            return int(self.text()) < int(other.text())
        except ValueError:
            return super().__lt__(other)


class CategoryStatsTab(QWidget):
    category_filter_requested = pyqtSignal(str)  # category name OR UNTAGGED_SENTINEL

    def __init__(self, library: LibraryManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._library = library
        self._stats: CategoryStats | None = None
        self._orphan_threshold = 1
        self._dirty = True   # True means recompute on next show
        self._build_ui()
```

#### Layout

```
┌─ Categories tab ─────────────────────────────────────────┐
│ [search...]  [Refresh]   142 unique · 18 orphans · 23 untagged │
├──────────────────────────┬───────────────────────────────┤
│  Categories table        │  Co-occurring pairs table     │
│  Category │ Count │ Flag │  Pair         │ Count         │
│  rock     │  142  │      │  rock + 90s   │  47           │
│  jazz     │   89  │      │  jazz + chill │  21           │
│  chill    │    1  │  ⚠   │  ...                          │
│  ...                     │                               │
├──────────────────────────┴───────────────────────────────┤
│  [Show untagged tracks (23)]                             │
└──────────────────────────────────────────────────────────┘
```

#### Widget tree (build inside `_build_ui`)

```
self (QVBoxLayout)
├─ top_bar (QHBoxLayout)
│   ├─ self._search_input (QLineEdit, placeholder "Filter categories...")
│   ├─ self._refresh_btn (QPushButton "Refresh")
│   └─ self._summary_label (QLabel, stretch=1)
├─ self._splitter (QSplitter Horizontal, stretch=1)
│   ├─ self._category_table (QTableWidget, 3 cols: Category, Count, Flag)
│   └─ self._pairs_table (QTableWidget, 2 cols: Pair, Count)
└─ bottom_bar (QHBoxLayout)
    └─ self._untagged_btn (QPushButton "Show untagged tracks (N)")
```

Both tables: same configuration as `src/ui/duplicates_tab.py:_build_ui`:
- `setSelectionBehavior(SelectionBehavior.SelectRows)`
- `setSelectionMode(SelectionMode.SingleSelection)` for v1 (the management plan flips it to `ExtendedSelection`)
- `setEditTriggers(EditTrigger.NoEditTriggers)`
- `setAlternatingRowColors(True)`
- Hide vertical header
- `header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)`, `header.setStretchLastSection(True)`

Splitter: `setSizes([400, 300])`, `setStretchFactor(0, 1)`, `setStretchFactor(1, 0)`, `setHandleWidth(1)`.

#### Behavior

```python
def invalidate(self) -> None:
    """Mark stats stale. Called by MainWindow after library scans/edits."""
    self._dirty = True

def refresh(self) -> None:
    """Recompute stats and repopulate tables. Cheap; safe to call repeatedly."""
    self._stats = compute_stats(self._library.get_all_tracks())
    self._dirty = False
    self._populate_summary()
    self._populate_categories_table()
    self._populate_pairs_table()
    self._update_untagged_button()
    self._apply_search_filter(self._search_input.text())

def show_if_dirty(self) -> None:
    """Called by MainWindow when this tab becomes active."""
    if self._dirty:
        self.refresh()
```

`_populate_summary`:
```python
self._summary_label.setText(
    f"{self._stats.unique_count()} unique · "
    f"{len(self._stats.orphans(self._orphan_threshold))} orphans · "
    f"{self._stats.untagged_count} untagged"
)
```

`_populate_categories_table`:
- Sort categories by count desc, then alpha.
- For each: `name_item = QTableWidgetItem(name)`, `count_item = _NumericItem(str(count))`, `flag_item = QTableWidgetItem("⚠" if count <= self._orphan_threshold else "")`.
- Store the category string in `name_item.setData(Qt.ItemDataRole.UserRole, name)`.

`_populate_pairs_table`:
- For each `(a, b, n)` in `self._stats.co_occurrences`: `QTableWidgetItem(f"{a} + {b}")` and `_NumericItem(str(n))`.

`_apply_search_filter(query: str)`:
- For each row in the categories table, `setRowHidden(row, query.lower() not in name.lower())`. Pairs table is unaffected.

Wire up:
- `self._search_input.textChanged.connect(self._apply_search_filter)`
- `self._refresh_btn.clicked.connect(self.refresh)`
- `self._category_table.itemDoubleClicked.connect(self._on_category_activated)`
- `self._untagged_btn.clicked.connect(lambda: self.category_filter_requested.emit(UNTAGGED_SENTINEL))`

```python
def _on_category_activated(self, item: QTableWidgetItem) -> None:
    row = item.row()
    name_item = self._category_table.item(row, 0)
    if name_item is None:
        return
    category = name_item.data(Qt.ItemDataRole.UserRole)
    if category:
        self.category_filter_requested.emit(category)
```

### Modified file: `src/ui/main_window.py`

Concrete edits:

1. **Import** at top:
   ```python
   from .category_stats_tab import CategoryStatsTab, UNTAGGED_SENTINEL
   ```

2. **In `_setup_ui`**, after the existing `self.duplicates_tab = DuplicatesTab(...)` line and **before** the tabs are added:
   ```python
   self.category_stats_tab = CategoryStatsTab(self.library)
   self.category_stats_tab.category_filter_requested.connect(
       self._on_category_filter_requested
   )
   ```

3. **In `_setup_ui`**, in the `self._tabs.addTab(...)` block, append:
   ```python
   self._tabs.addTab(self.category_stats_tab, "Categories")
   ```
   And, after the tabs are constructed, connect:
   ```python
   self._tabs.currentChanged.connect(self._on_tab_changed)
   ```

4. **Add new methods** to `MainWindow`:
   ```python
   def _on_tab_changed(self, index: int) -> None:
       widget = self._tabs.widget(index)
       if widget is self.category_stats_tab:
           self.category_stats_tab.show_if_dirty()

   def _on_category_filter_requested(self, category: str) -> None:
       cat = None if category == UNTAGGED_SENTINEL else category
       self.search_ctrl.filter_by_category(cat)
       self._tabs.setCurrentIndex(0)  # Library tab
       # Clear the search input so it doesn't disagree with the filter.
       self.search_input.blockSignals(True)
       self.search_input.clear()
       self.search_input.blockSignals(False)
       label = "untagged tracks" if cat is None else f'category "{cat}"'
       self.statusBar().showMessage(f"Filtered to {label}", 5000)
   ```

5. **In `_on_scan_all_done`** (`src/ui/main_window.py:396`), add at the end:
   ```python
   self.category_stats_tab.invalidate()
   ```

6. **In `_refresh_library`** (`src/ui/main_window.py:321`), after `self.library.clear()`, add:
   ```python
   self.category_stats_tab.invalidate()
   ```

7. **In `_on_categories_changed`** (`src/ui/main_window.py:672`), add at the end:
   ```python
   self.category_stats_tab.invalidate()
   ```

No changes to `library.py`, `track.py`, `categorizer.py`, or any other controller.

## Tests

### `tests/core/test_category_stats.py` (new file)

Style note: top-level `make_track` helper as in `tests/core/test_categorizer.py`.

Cases:
- Empty list → `counts == {}`, `untagged_count == 0`, `co_occurrences == []`, `total_tracks == 0`.
- All tracks with no categories → `counts == {}`, `untagged_count == n`.
- One category on one track → `counts == {"rock": 1}`, no pairs, no orphans-above-threshold-zero.
- Mixed-case in same track (`["Rock", "rock"]`) → counted once for `rock`.
- Two tracks both with `["rock", "jazz"]` → pair `("jazz", "rock", 2)` (alpha order in tuple).
- `top_pairs=2` cap respected when more pairs exist.
- `orphans(threshold=1)` returns categories with count == 1, sorted alphabetically.
- `orphans(threshold=3)` includes categories with counts 1, 2, and 3.

### `tests/ui/test_category_stats_tab.py` (new file)

Use the `qapp` fixture from `tests/conftest.py`. Use a real `LibraryManager` populated via `add_track`, or mock — match `tests/ui/test_search_controller.py` style:
- After `refresh()`, the categories table row count equals number of unique categories.
- Search input filtering hides non-matching rows (`isRowHidden(row)` is True).
- Double-clicking a name cell emits `category_filter_requested` with the right category string.
- Clicking the "Show untagged tracks" button emits with `UNTAGGED_SENTINEL`.
- `invalidate()` followed by `show_if_dirty()` triggers a recompute.

## Step-by-step for handoff

1. Create `src/core/category_stats.py` with the dataclass and `compute_stats` exactly as written above.
2. Create `tests/core/test_category_stats.py` with the cases above. Run `pytest tests/core/test_category_stats.py`. Confirm green before continuing.
3. Add `filter_by_category` to `src/ui/controllers/search_controller.py` per spec. Don't touch the constructor or other methods.
4. Create `src/ui/category_stats_tab.py`. Build the widget tree as described. Implement `refresh`, `invalidate`, `show_if_dirty`, `_apply_search_filter`, `_on_category_activated`.
5. Edit `src/ui/main_window.py` per the seven numbered edits. Run the app: `python -m src.ui.main_window`. Verify the Categories tab appears and counts are populated when first opened.
6. Manual smoke test:
   - Categories tab opens with correct counts.
   - Search box filters the categories list.
   - Double-clicking a category jumps to the Library tab and filters.
   - Clicking "Show untagged tracks" jumps to the Library tab and shows tracks without categories.
   - Adding a category to a track in the Library tab — return to Categories tab — counts update.
   - Clicking a folder checkbox after filtering wipes the filter (existing behavior — same UX as free-text search).
7. Run `ruff check src/` and `ruff format src/`. Run full `pytest`.

## Out of scope (covered later or never)

- Editing categories from this tab → see `category-management-plan.md`.
- Live updates without leaving the tab.
- Persisting the orphan threshold or search filter.
- Configurable `top_pairs` limit in the UI.
- Per-category track preview pane inside the tab.
- Charts/graphs.
