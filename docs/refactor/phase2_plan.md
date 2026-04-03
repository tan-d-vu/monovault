```markdown
# Phase 2: Decompose MainWindow

## Overview

Extract three controllers from the 750-line `MainWindow` god object: `PlaybackController`, `SearchController`, and `CategoryController`. Each controller encapsulates business logic and state, exposing signals for UI binding. `MainWindow` becomes a thin coordinator that builds the layout and wires controllers to widgets.

## Prerequisites

- Phase 1 complete (interfaces, metadata package, category sources, test infrastructure)

## Requirements

- `PlaybackController` — playback state machine, track navigation, seeking, volume
- `SearchController` — search debouncing, query execution, result set management
- `CategoryController` — category CRUD, suggestion refresh, track detail state
- `MainWindow` reduced to < 250 lines (currently 750)
- Each controller testable without a running QApplication (where possible)
- >= 80% coverage on controller modules

## Architecture Changes

| Change | File(s) | Description |
|---|---|---|
| New package | `src/ui/controllers/` | Controller package |
| PlaybackController | `src/ui/controllers/playback_controller.py` | Wraps `PlaybackEngine`, owns playback state |
| SearchController | `src/ui/controllers/search_controller.py` | Debounced search, result set |
| CategoryController | `src/ui/controllers/category_controller.py` | Category add/remove/suggest |
| MainWindow slim | `src/ui/main_window.py` | Reduced to layout + wiring |

---

## Implementation Steps

### Step 1: Create Controller Package

**Files to create:**
- `src/ui/controllers/__init__.py`
- `tests/ui/__init__.py` (if not exists)

**Dependencies**: None
**Risk**: Low

---

### Step 2: Extract PlaybackController

**File to create**: `src/ui/controllers/playback_controller.py`

**Action**: Move lines 500-616 of `main_window.py` (playback logic) into a controller:

```python
"""Playback controller — manages playback state, track navigation, seeking."""

from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal

from ...core.playback import PlaybackEngine
from ...models.track import Track


class PlaybackController(QObject):
    """Decoupled playback logic. Emits signals for UI to bind."""

    # Signals for UI binding
    now_playing_changed = pyqtSignal(str)       # "Title - Artist" or "No track playing"
    play_state_changed = pyqtSignal(bool)       # True = playing, False = paused/stopped
    position_updated = pyqtSignal(int, int)     # (position_ms, duration_ms)
    time_display_changed = pyqtSignal(str)      # "01:23 / 04:56"
    slider_position_changed = pyqtSignal(int)   # 0-1000 range for slider

    def __init__(self, engine: PlaybackEngine, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._current_track: Optional[Track] = None
        self._track_list: list[Track] = []
        self._is_seeking = False

        # Wire engine signals
        self._engine.position_changed.connect(self._on_position_changed)
        self._engine.duration_changed.connect(self._on_duration_changed)
        self._engine.playback_state_changed.connect(self._on_playback_state_changed)

    @property
    def current_track(self) -> Optional[Track]:
        return self._current_track

    def set_track_list(self, tracks: list[Track]) -> None:
        self._track_list = list(tracks)

    def play_track(self, track: Track) -> None:
        self._current_track = track
        self._engine.load_track(track.file_path)
        self._engine.play()
        self.now_playing_changed.emit(f"{track.title} - {track.artist}")

    def toggle_playback(self) -> None:
        if self._engine.is_playing():
            self._engine.pause()
            self.play_state_changed.emit(False)
        elif self._current_track:
            self._engine.play()
            self.play_state_changed.emit(True)

    def seek(self, slider_position: int) -> None:
        """Seek to position. slider_position is 0-1000."""
        if self._is_seeking:
            return
        self._is_seeking = True
        try:
            duration = self._engine.get_duration()
            if duration > 0:
                seek_pos = int(slider_position / 1000 * duration)
                self._engine.seek(seek_pos)
        finally:
            self._is_seeking = False

    def set_volume(self, value: int) -> None:
        self._engine.set_volume(value)

    def next_track(self) -> None:
        if not self._track_list or not self._current_track:
            return
        idx = self._find_current_index()
        if idx is not None and idx < len(self._track_list) - 1:
            self.play_track(self._track_list[idx + 1])

    def prev_track(self) -> None:
        if not self._track_list or not self._current_track:
            return
        idx = self._find_current_index()
        if idx is not None and idx > 0:
            self.play_track(self._track_list[idx - 1])

    def stop(self) -> None:
        self._engine.stop()
        self._current_track = None

    def _find_current_index(self) -> Optional[int]:
        if not self._current_track:
            return None
        for i, t in enumerate(self._track_list):
            if t.file_path == self._current_track.file_path:
                return i
        return None

    def _on_position_changed(self, position: int) -> None:
        if self._is_seeking:
            return
        self._is_seeking = True
        try:
            duration = self._engine.get_duration()
            if duration > 0:
                self.slider_position_changed.emit(int(position / duration * 1000))
            self.time_display_changed.emit(self._format_time(position, duration))
        finally:
            self._is_seeking = False

    def _on_duration_changed(self, duration: int) -> None:
        self.slider_position_changed.emit(0)
        self.time_display_changed.emit(self._format_time(0, duration))

    def _on_playback_state_changed(self, state: int) -> None:
        from PyQt6.QtMultimedia import QMediaPlayer
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_state_changed.emit(is_playing)

    @staticmethod
    def _format_time(position_ms: int, duration_ms: int) -> str:
        pos_s = position_ms // 1000
        dur_s = duration_ms // 1000
        return f"{pos_s // 60:02d}:{pos_s % 60:02d} / {dur_s // 60:02d}:{dur_s % 60:02d}"
```

**Dependencies**: None within Phase 2
**Risk**: Medium -- playback is user-facing; must test seeking edge cases
**Parallel track**: Track D

---

### Step 3: Extract SearchController

**File to create**: `src/ui/controllers/search_controller.py`

```python
"""Search controller — debounced search with result set management."""

from typing import Optional
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ...core.interfaces import ITrackRepository
from ...models.track import Track


class SearchController(QObject):
    """Manages search state. Emits results_changed when track list updates."""

    results_changed = pyqtSignal(list)  # list[Track]

    def __init__(
        self,
        repository: ITrackRepository,
        debounce_ms: int = 1500,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repository
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._execute_search)
        self._debounce_ms = debounce_ms
        self._pending_query: str = ""

    def on_text_changed(self, text: str) -> None:
        """Called when search input text changes. Starts debounce timer."""
        self._pending_query = text.strip()
        self._timer.start(self._debounce_ms)

    def search_immediate(self, query: str) -> list[Track]:
        """Execute search immediately without debounce. Returns results."""
        self._timer.stop()
        q = query.strip()
        if q:
            results = self._repo.search(q)
        else:
            results = self._repo.get_all_tracks()
        self.results_changed.emit(results)
        return results

    def get_all_tracks(self) -> list[Track]:
        """Return all tracks (clear search)."""
        results = self._repo.get_all_tracks()
        self.results_changed.emit(results)
        return results

    def _execute_search(self) -> None:
        self.search_immediate(self._pending_query)
```

**Dependencies**: Phase 1 `ITrackRepository`
**Risk**: Low
**Parallel track**: Track E

---

### Step 4: Extract CategoryController

**File to create**: `src/ui/controllers/category_controller.py`

```python
"""Category controller — manages category CRUD and suggestions for the selected track."""

from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal

from ...core.categorizer import Categorizer
from ...models.track import Track


class CategoryController(QObject):
    """Category management for the currently selected track."""

    categories_changed = pyqtSignal(Track)               # Emitted after add/remove
    suggestions_changed = pyqtSignal(list)                # list[tuple[str, str]]
    track_details_changed = pyqtSignal(Track)             # Emitted when selected track changes

    def __init__(
        self,
        categorizer: Categorizer,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._categorizer = categorizer
        self._current_track: Optional[Track] = None

    @property
    def current_track(self) -> Optional[Track]:
        return self._current_track

    def select_track(self, track: Track) -> None:
        """Set the currently viewed track. Emits detail and suggestion signals."""
        self._current_track = track
        self.track_details_changed.emit(track)
        self._refresh_suggestions()

    def add_category(self, category: str) -> bool:
        """Add a category to the current track. Returns True on success."""
        if not self._current_track:
            return False
        success = self._categorizer.add_category(self._current_track, category)
        if success:
            self.categories_changed.emit(self._current_track)
            self._refresh_suggestions()
        return success

    def remove_category(self, category: str) -> bool:
        """Remove a category from the current track. Returns True on success."""
        if not self._current_track:
            return False
        success = self._categorizer.remove_category(self._current_track, category)
        if success:
            self.categories_changed.emit(self._current_track)
            self._refresh_suggestions()
        return success

    def accept_suggestion(self, category: str) -> bool:
        """Accept a suggested category (same as add)."""
        return self.add_category(category)

    def _refresh_suggestions(self) -> None:
        if not self._current_track:
            self.suggestions_changed.emit([])
            return
        suggestions = self._categorizer.get_suggestions(self._current_track)
        self.suggestions_changed.emit(suggestions)
```

**Dependencies**: Phase 1 `Categorizer` refactor
**Risk**: Medium -- must preserve exact UI update behavior
**Parallel track**: Track E (alongside SearchController)

---

### Step 5: Slim Down MainWindow

**File to modify**: `src/ui/main_window.py`

**Action**: Replace inline logic with controller delegation. The `__init__` becomes:

```python
def __init__(self):
    super().__init__()
    # Core services
    self.library = LibraryManager()
    self.library_store = LibraryStore()
    self.scanner = Scanner(library_store=self.library_store)
    self.playback_engine = PlaybackEngine()

    # Category sources (from Phase 1)
    from ..core.category_sources import ArtistCategorySource, SimilarCategoryCategorySource
    categorizer = Categorizer(
        self.library,
        sources=[
            ArtistCategorySource(self.library),
            SimilarCategoryCategorySource(self.library),
        ],
    )

    # Controllers
    self.playback_ctrl = PlaybackController(self.playback_engine, parent=self)
    self.search_ctrl = SearchController(self.library, parent=self)
    self.category_ctrl = CategoryController(categorizer, parent=self)

    self._setup_ui()
    self._connect_controllers()
    self._load_library()
```

**Methods to remove from MainWindow** (moved to controllers):
- `_toggle_playback` -> `self.playback_ctrl.toggle_playback()`
- `_on_seek` -> `self.playback_ctrl.seek()`
- `_on_volume_changed` -> `self.playback_ctrl.set_volume()`
- `_on_position_changed` -> handled by `PlaybackController` signals
- `_on_duration_changed` -> handled by `PlaybackController` signals
- `_on_playback_state_changed` -> handled by `PlaybackController` signals
- `_prev_track` / `_next_track` -> `self.playback_ctrl.prev_track()` / `next_track()`
- `_do_search` -> `self.search_ctrl` handles via `results_changed` signal
- `_on_search_changed` -> `self.search_ctrl.on_text_changed()`
- `_add_category` -> `self.category_ctrl.add_category()`
- `_remove_category` -> `self.category_ctrl.remove_category()`
- `_on_suggestion_clicked` -> `self.category_ctrl.accept_suggestion()`
- `_update_categories` -> bound to `category_ctrl.categories_changed` signal
- `_update_suggestions` -> bound to `category_ctrl.suggestions_changed` signal

**Methods that remain in MainWindow:**
- `_setup_ui` — layout creation (but can be further split into private methods)
- `_create_folder_panel`, `_create_track_table`, `_create_details_panel`, `_create_playback_bar`
- `_connect_controllers` — NEW method wiring controller signals to UI updates
- `_load_library`, `_load_tracks`, `_populate_track_table` — library management
- `_add_folder`, `_remove_folder`, `_refresh_library` — folder management
- `_show_track_details` — simplified, delegates to `category_ctrl.select_track()`
- `_refresh_track_in_table` — table update helper
- `closeEvent`, `eventFilter`

**New wiring method:**
```python
def _connect_controllers(self):
    # Playback
    self.playback_ctrl.now_playing_changed.connect(self.now_playing_label.setText)
    self.playback_ctrl.play_state_changed.connect(self._update_play_icon)
    self.playback_ctrl.time_display_changed.connect(self.time_label.setText)
    self.playback_ctrl.slider_position_changed.connect(self.position_slider.setValue)

    self.play_btn.clicked.connect(self.playback_ctrl.toggle_playback)
    self.position_slider.sliderMoved.connect(self.playback_ctrl.seek)
    self.volume_slider.sliderMoved.connect(self.playback_ctrl.set_volume)

    # Search
    self.search_input.textChanged.connect(self.search_ctrl.on_text_changed)
    self.search_ctrl.results_changed.connect(self._on_search_results)

    # Categories
    self.category_input.returnPressed.connect(self._on_add_category_input)
    self.category_ctrl.categories_changed.connect(self._on_categories_changed)
    self.category_ctrl.suggestions_changed.connect(self._on_suggestions_changed)
    self.category_ctrl.track_details_changed.connect(self._on_track_details_changed)
```

**Dependencies**: Steps 2-4 (all controllers exist)
**Risk**: High -- this is the largest change; must be done carefully with manual testing
**Parallel track**: Sequential (after all controllers)

---

### Step 6: Write Controller Tests

**Files to create:**
- `tests/ui/test_playback_controller.py`
- `tests/ui/test_search_controller.py`
- `tests/ui/test_category_controller.py`

Controllers use Qt signals, so tests need `QApplication`. Use `pytest-qt` or a minimal fixture:

```python
# tests/conftest.py (add to existing)
import pytest
from PyQt6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication instance for the entire test session."""
    app = QApplication.instance() or QApplication([])
    yield app
```

```python
# tests/ui/test_playback_controller.py
import pytest
from unittest.mock import MagicMock, patch
from src.ui.controllers.playback_controller import PlaybackController
from src.models.track import Track


@pytest.mark.unit
class TestPlaybackController:
    def test_play_track_emits_signal(self, qapp, sample_track):
        engine = MagicMock()
        engine.position_changed = MagicMock()
        engine.duration_changed = MagicMock()
        engine.playback_state_changed = MagicMock()
        # Need to mock signal connections
        ctrl = PlaybackController.__new__(PlaybackController)
        # ... test signal emission

    def test_toggle_pause(self, qapp):
        engine = MagicMock()
        engine.is_playing.return_value = True
        # ...

    def test_next_track(self, qapp, sample_tracks):
        # Verify next track is played when available
        pass

    def test_next_track_at_end_does_nothing(self, qapp, sample_track):
        # Verify no action when at end of list
        pass

    def test_format_time(self):
        assert PlaybackController._format_time(63000, 240000) == "01:03 / 04:00"
        assert PlaybackController._format_time(0, 0) == "00:00 / 00:00"
```

```python
# tests/ui/test_search_controller.py
import pytest
from unittest.mock import MagicMock
from src.ui.controllers.search_controller import SearchController


@pytest.mark.unit
class TestSearchController:
    def test_search_immediate_with_query(self, qapp):
        repo = MagicMock()
        repo.search.return_value = ["track1"]
        ctrl = SearchController(repo, debounce_ms=0)

        results = ctrl.search_immediate("test")
        repo.search.assert_called_once_with("test")

    def test_search_immediate_empty_returns_all(self, qapp):
        repo = MagicMock()
        repo.get_all_tracks.return_value = ["all"]
        ctrl = SearchController(repo, debounce_ms=0)

        results = ctrl.search_immediate("")
        repo.get_all_tracks.assert_called_once()

    def test_search_strips_whitespace(self, qapp):
        repo = MagicMock()
        repo.get_all_tracks.return_value = []
        ctrl = SearchController(repo, debounce_ms=0)

        ctrl.search_immediate("   ")
        repo.get_all_tracks.assert_called_once()
```

```python
# tests/ui/test_category_controller.py
import pytest
from unittest.mock import MagicMock
from src.ui.controllers.category_controller import CategoryController


@pytest.mark.unit
class TestCategoryController:
    def test_add_category_success(self, qapp, sample_track):
        categorizer = MagicMock()
        categorizer.add_category.return_value = True
        categorizer.get_suggestions.return_value = []

        ctrl = CategoryController(categorizer)
        ctrl.select_track(sample_track)
        assert ctrl.add_category("jazz") is True
        categorizer.add_category.assert_called_once_with(sample_track, "jazz")

    def test_add_category_no_track(self, qapp):
        categorizer = MagicMock()
        ctrl = CategoryController(categorizer)
        assert ctrl.add_category("jazz") is False

    def test_remove_category(self, qapp, sample_track):
        categorizer = MagicMock()
        categorizer.remove_category.return_value = True
        categorizer.get_suggestions.return_value = []

        ctrl = CategoryController(categorizer)
        ctrl.select_track(sample_track)
        assert ctrl.remove_category("rock") is True
```

**Dependencies**: Steps 2-4
**Risk**: Medium -- Qt signal testing can be tricky
**Parallel track**: Track D and E (one per controller)

---

## Parallel Work Summary

```
Sequential Setup:
  Step 1: Create controller package

Track D (playback):               Track E (search + category):
──────────────────                ────────────────────────────
Step 2: PlaybackController         Step 3: SearchController
Step 6a: playback tests            Step 4: CategoryController
                                   Step 6b+c: search + category tests

Sequential Finish:
  Step 5: Slim MainWindow (depends on D + E)
  Manual regression testing
```

## Acceptance Criteria

- [ ] `MainWindow.__init__` creates controllers, not inline logic
- [ ] `main_window.py` is < 300 lines (target ~250)
- [ ] `PlaybackController` handles all playback state transitions
- [ ] `SearchController` handles debounced search with `results_changed` signal
- [ ] `CategoryController` handles category CRUD with proper signals
- [ ] No direct `PlaybackEngine` calls from `MainWindow` (all via controller)
- [ ] No direct `Categorizer` calls from `MainWindow` (all via controller)
- [ ] `python -m src.ui.main_window` launches and functions identically
- [ ] `pytest --cov=src/ui/controllers` shows >= 80%
- [ ] `ruff check src/` passes

## Risks & Mitigations

- **Risk**: Signal disconnection causes silent UI failures
  - Mitigation: Integration test that verifies signal chain from controller to dummy slot
- **Risk**: Playback seeking race condition during extraction
  - Mitigation: Keep `_is_seeking` guard pattern intact in controller
- **Risk**: `QTimer` in `SearchController` behaves differently in tests
  - Mitigation: Use `search_immediate()` in tests, test debounce separately with `pytest-qt`'s `qtbot.waitSignal`

## Test Strategy

| Test file | What it covers | Type |
|---|---|---|
| `tests/ui/test_playback_controller.py` | Play, pause, seek, next/prev, time formatting | Unit |
| `tests/ui/test_search_controller.py` | Immediate search, empty query, whitespace | Unit |
| `tests/ui/test_category_controller.py` | Add/remove category, no-track guard, suggestion refresh | Unit |
```

---