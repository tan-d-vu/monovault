"""Event bus and domain event definitions."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

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
    slider_value: int
    time_display: str


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
    suggestions: list[tuple[str, str]]


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
    """Simple synchronous publish/subscribe event bus."""

    def __init__(self) -> None:
        self._subscribers: dict[type[Event], list[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: type[Event], handler: Callable[[Event], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: type[Event], handler: Callable[[Event], None]) -> None:
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass

    def publish(self, event: Event) -> None:
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
        self._subscribers.clear()

    def has_subscribers(self, event_type: type[Event]) -> bool:
        return bool(self._subscribers.get(event_type))
