```markdown
# Phase 3: Event Bus

## Overview

Introduce a lightweight in-process event bus that replaces direct signal wiring between controllers. Controllers publish domain events; other controllers and UI components subscribe. This decouples controllers from each other and makes adding new features a matter of adding new subscribers without modifying existing code.

## Prerequisites

- Phase 2 complete (controllers extracted, `MainWindow` is thin coordinator)

## Requirements

- `EventBus` class with typed event publishing and subscription
- Domain events as frozen dataclasses (immutable)
- Controllers publish events instead of holding references to other controllers
- `MainWindow` subscribes to events for UI updates instead of direct signal wiring
- New features can be added by subscribing to existing events
- Zero behavioral changes — pure architectural refactoring

## Architecture Changes

| Change | File(s) | Description |
|---|---|---|
| Event bus | `src/core/events.py` | `EventBus` class + domain event definitions |
| Controller updates | `src/ui/controllers/*.py` | Publish events instead of (or in addition to) Qt signals |
| MainWindow update | `src/ui/main_window.py` | Subscribe to events via bus |

---

## Domain Event Definitions

**File to create**: `src/core/events.py`

```python
"""Event bus and domain event definitions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..models.track import Track

logger = logging.getLogger(__name__)


# ─── Domain Events ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Event:
    """Base class for all domain events."""
    pass


@dataclass(frozen=True)
class TrackPlaybackStarted(Event):
    track: Track


@dataclass(frozen=True)
class PlaybackStateChanged(Event):
    is_playing: bool


@dataclass(frozen=True)
class PlaybackPositionChanged(Event):
    position_ms: int
    duration_ms: int
    slider_value: int        # 0-1000
    time_display: str        # "01:23 / 04:56"


@dataclass(frozen=True)
class PlaybackStopped(Event):
    pass


@dataclass(frozen=True)
class TrackSelected(Event):
    track: Track


@dataclass(frozen=True)
class SearchResultsChanged(Event):
    tracks: list[Track]
    query: str


@dataclass(frozen=True)
class CategoriesChanged(Event):
    track: Track


@dataclass(frozen=True)
class SuggestionsChanged(Event):
    suggestions: list[tuple[str, str]]   # (category, source_label)


@dataclass(frozen=True)
class LibraryRefreshed(Event):
    track_count: int


@dataclass(frozen=True)
class FolderAdded(Event):
    path: str


@dataclass(frozen=True)
class FolderRemoved(Event):
    path: str


# ─── Event Bus ───────────────────────────────────────────────────────────────

class EventBus:
    """Simple synchronous publish/subscribe event bus.

    Usage:
        bus = EventBus()
        bus.subscribe(TrackPlaybackStarted, handler_fn)
        bus.publish(TrackPlaybackStarted(track=my_track))
    """

    def __init__(self) -> None:
        self._subscribers: dict[type[Event], list[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: type[Event], handler: Callable[[Event], None]) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: type[Event], handler: Callable[[Event], None]) -> None:
        """Remove a handler. No-op if not registered."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass

    def publish(self, event: Event) -> None:
        """Dispatch event to all registered handlers synchronously."""
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Error in event handler %s for %s",
                    handler.__qualname__,
                    event_type.__name__,
                )

    def clear(self) -> None:
        """Remove all subscriptions. Useful for testing."""
        self._subscribers.clear()

    def has_subscribers(self, event_type: type[Event]) -> bool:
        """Check if an event type has any subscribers."""
        return bool(self._subscribers.get(event_type))
```

**Dependencies**: None
**Risk**: Low

---

## Implementation Steps

### Step 1: Create EventBus and Domain Events

**File to create**: `src/core/events.py` (as shown above)

**Test file to create**: `tests/core/test_events.py`

```python
import pytest
from src.core.events import (
    EventBus,
    TrackPlaybackStarted,
    PlaybackStateChanged,
    CategoriesChanged,
    Event,
)
from src.models.track import Track


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def track():
    return Track(
        id=1, file_path="/tmp/t.mp3", title="T", artist="A",
        album="B", duration=60.0, categories=[], album_art=None,
        folder_path="/tmp",
    )


@pytest.mark.unit
class TestEventBus:
    def test_publish_calls_subscriber(self, bus, track):
        received = []
        bus.subscribe(TrackPlaybackStarted, lambda e: received.append(e))
        bus.publish(TrackPlaybackStarted(track=track))
        assert len(received) == 1
        assert received[0].track is track

    def test_multiple_subscribers(self, bus, track):
        count = []
        bus.subscribe(TrackPlaybackStarted, lambda e: count.append(1))
        bus.subscribe(TrackPlaybackStarted, lambda e: count.append(2))
        bus.publish(TrackPlaybackStarted(track=track))
        assert len(count) == 2

    def test_wrong_event_type_not_called(self, bus, track):
        received = []
        bus.subscribe(PlaybackStateChanged, lambda e: received.append(e))
        bus.publish(TrackPlaybackStarted(track=track))
        assert len(received) == 0

    def test_unsubscribe(self, bus, track):
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe(TrackPlaybackStarted, handler)
        bus.unsubscribe(TrackPlaybackStarted, handler)
        bus.publish(TrackPlaybackStarted(track=track))
        assert len(received) == 0

    def test_handler_exception_does_not_break_others(self, bus, track):
        results = []

        def bad_handler(e):
            raise RuntimeError("oops")

        def good_handler(e):
            results.append(e)

        bus.subscribe(TrackPlaybackStarted, bad_handler)
        bus.subscribe(TrackPlaybackStarted, good_handler)
        bus.publish(TrackPlaybackStarted(track=track))
        assert len(results) == 1

    def test_clear(self, bus, track):
        bus.subscribe(TrackPlaybackStarted, lambda e: None)
        bus.clear()
        assert not bus.has_subscribers(TrackPlaybackStarted)

    def test_events_are_immutable(self, track):
        event = TrackPlaybackStarted(track=track)
        with pytest.raises(AttributeError):
            event.track = None  # type: ignore[misc]
```

**Dependencies**: None
**Risk**: Low
**Parallel track**: Track F (independent)

---

### Step 2: Migrate PlaybackController to EventBus

**File to modify**: `src/ui/controllers/playback_controller.py`

**Action**: Add `EventBus` parameter. Publish domain events alongside (or instead of) Qt signals. Keep Qt signals during transition for backward compatibility.

```python
def __init__(
    self,
    engine: PlaybackEngine,
    bus: Optional[EventBus] = None,
    parent: Optional[QObject] = None,
) -> None:
    super().__init__(parent)
    self._engine = engine
    self._bus = bus
    # ... existing init ...

def play_track(self, track: Track) -> None:
    self._current_track = track
    self._engine.load_track(track.file_path)
    self._engine.play()
    self.now_playing_changed.emit(f"{track.title} - {track.artist}")
    if self._bus:
        self._bus.publish(TrackPlaybackStarted(track=track))
```

Pattern: every method that emits a Qt signal also publishes the corresponding domain event if `_bus` is set. This enables gradual migration -- Qt signals still work, event bus is additive.

**Dependencies**: Step 1
**Risk**: Low -- additive change
**Parallel track**: Track G (sequential within G)

---

### Step 3: Migrate SearchController to EventBus

**File to modify**: `src/ui/controllers/search_controller.py`

**Action**: Publish `SearchResultsChanged` after search execution:

```python
def _execute_search(self) -> None:
    results = self.search_immediate(self._pending_query)
    if self._bus:
        self._bus.publish(SearchResultsChanged(tracks=results, query=self._pending_query))
```

**Dependencies**: Step 1
**Risk**: Low
**Parallel track**: Track G

---

### Step 4: Migrate CategoryController to EventBus

**File to modify**: `src/ui/controllers/category_controller.py`

**Action**: Publish `CategoriesChanged`, `SuggestionsChanged`, `TrackSelected`:

```python
def select_track(self, track: Track) -> None:
    self._current_track = track
    self.track_details_changed.emit(track)
    if self._bus:
        self._bus.publish(TrackSelected(track=track))
    self._refresh_suggestions()

def _refresh_suggestions(self) -> None:
    # ... existing logic ...
    if self._bus:
        self._bus.publish(SuggestionsChanged(suggestions=suggestions))
```

**Dependencies**: Step 1
**Risk**: Low
**Parallel track**: Track G

---

### Step 5: Update MainWindow to Use EventBus

**File to modify**: `src/ui/main_window.py`

**Action**: Create a shared `EventBus` instance and pass it to all controllers. Optionally, subscribe to domain events for cross-controller coordination instead of connecting controller signals directly.

```python
def __init__(self):
    super().__init__()
    from ..core.events import EventBus
    self._bus = EventBus()

    # ... create services ...

    self.playback_ctrl = PlaybackController(self.playback_engine, bus=self._bus, parent=self)
    self.search_ctrl = SearchController(self.library, bus=self._bus, parent=self)
    self.category_ctrl = CategoryController(categorizer, bus=self._bus, parent=self)

    self._setup_ui()
    self._connect_controllers()
    self._subscribe_events()
    self._load_library()

def _subscribe_events(self):
    """Subscribe to domain events for cross-cutting concerns."""
    from ..core.events import CategoriesChanged

    # Example: when categories change, refresh the track in the table
    self._bus.subscribe(CategoriesChanged, self._on_categories_event)

def _on_categories_event(self, event):
    self._refresh_track_in_table(event.track)
```

**Dependencies**: Steps 2-4
**Risk**: Medium -- must ensure no double-firing (both Qt signal and event bus updating same UI)
**Parallel track**: Sequential (after all controller migrations)

---

### Step 6: (Optional) Remove Qt Signal Redundancy

Once event bus is working and tested, Qt signals that are only used for inter-controller communication can be removed. Keep Qt signals that are directly connected to widgets (e.g., `slider_position_changed` -> `QSlider.setValue`).

**Rule**: If a signal connects controller-to-controller, replace with event bus. If it connects controller-to-widget, keep as Qt signal (widgets cannot subscribe to domain events).

**Dependencies**: Step 5 fully verified
**Risk**: Medium -- removing signals is a breaking change; do incrementally
**Parallel track**: Sequential

---

## Parallel Work Summary

```
Track F (event bus core):        Track G (controller migration):
─────────────────────           ────────────────────────────────
Step 1: EventBus + events        (waits for Track F)
Step 1: event bus tests          Step 2: PlaybackController
                                 Step 3: SearchController
                                 Step 4: CategoryController
                                 Step 5: MainWindow wiring
                                 Step 6: (optional) signal cleanup
```

## Acceptance Criteria

- [ ] `EventBus` class supports subscribe, unsubscribe, publish, clear
- [ ] All domain events are frozen dataclasses (immutable)
- [ ] Handler exceptions are logged but do not break other handlers
- [ ] All three controllers accept optional `EventBus` parameter
- [ ] Controllers publish domain events when `bus` is provided
- [ ] `MainWindow` creates shared `EventBus` and passes to controllers
- [ ] Application functions identically with event bus active
- [ ] `pytest --cov=src/core/events` shows >= 90%
- [ ] `ruff check src/` passes
- [ ] Adding a hypothetical new feature (e.g., "play count tracker") requires only a new subscriber file, no changes to existing controllers

## Risks & Mitigations

- **Risk**: Synchronous event dispatch causes UI lag for expensive handlers
  - Mitigation: Keep handlers lightweight; heavy work should use `QTimer.singleShot(0, ...)` to defer
- **Risk**: Double-firing: both Qt signal and event bus trigger the same UI update
  - Mitigation: During transition, use event bus for cross-controller only; keep Qt signals for widget binding
- **Risk**: Event ordering becomes unpredictable
  - Mitigation: Handlers are called in subscription order (FIFO); document this guarantee
- **Risk**: Memory leaks from forgotten subscriptions
  - Mitigation: `EventBus.clear()` in `MainWindow.closeEvent()`; consider weak references for long-lived subscribers

## Test Strategy

| Test file | What it covers | Type |
|---|---|---|
| `tests/core/test_events.py` | EventBus pub/sub, unsubscribe, exception isolation, immutability | Unit |
| `tests/ui/test_playback_controller.py` | (update) Verify domain events published alongside signals | Unit |
| `tests/ui/test_search_controller.py` | (update) Verify SearchResultsChanged published | Unit |
| `tests/ui/test_category_controller.py` | (update) Verify CategoriesChanged, SuggestionsChanged published | Unit |

## Example: Adding a Feature with Event Bus

To add a "recently played" sidebar:

```python
# src/ui/recently_played.py (NEW file)
from ..core.events import EventBus, TrackPlaybackStarted

class RecentlyPlayedTracker:
    def __init__(self, bus: EventBus, max_items: int = 20):
        self._recent: list[Track] = []
        self._max = max_items
        bus.subscribe(TrackPlaybackStarted, self._on_track_played)

    def _on_track_played(self, event: TrackPlaybackStarted) -> None:
        self._recent = [event.track] + [
            t for t in self._recent if t.id != event.track.id
        ][:self._max - 1]

    @property
    def recent_tracks(self) -> list[Track]:
        return list(self._recent)
```

No existing controller or MainWindow code needs to change. This is the primary value of the event bus architecture.
```

---

All four documents are complete. Here is a summary:

**Files to create:**
- `/home/tdv/projects/monovault/docs/refactor/overview.md` -- Cross-phase dependency map, parallel tracks, effort estimates, final file structure
- `/home/tdv/projects/monovault/docs/refactor/phase1_plan.md` -- Extract interfaces (IMetadataParser, ITrackRepository, ICategorySource), metadata package with format registry, proper logging, test infrastructure with 80%+ core coverage
- `/home/tdv/projects/monovault/docs/refactor/phase2_plan.md` -- Decompose MainWindow into PlaybackController, SearchController, CategoryController; slim MainWindow from 750 to ~250 lines
- `/home/tdv/projects/monovault/docs/refactor/phase3_plan.md` -- Lightweight synchronous EventBus with frozen dataclass domain events, gradual controller migration, enables feature addition without touching existing code

**Key findings from codebase analysis:**
- `metadata.py` has 6 silent `except Exception` blocks across `read_metadata`, `read_comment`, `read_comment_raw`, `write_comment`, `write_comments`, `get_album_art`
- `LibraryManager` already structurally satisfies `ITrackRepository` -- no method signature changes needed
- `Categorizer.__init__` takes untyped `library` parameter -- easy injection point for `ICategorySource` list
- No `pyproject.toml` test dependencies exist (pytest, pytest-cov must be added)
- No `tests/` directory exists at all
- Python 3.12 with `setuptools` build system
- Total estimated effort: 9-12 developer days across all three phases