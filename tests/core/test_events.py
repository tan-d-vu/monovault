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
        id=1,
        file_path="/tmp/t.mp3",
        title="T",
        artist="A",
        album="B",
        duration=60.0,
        categories=[],
        album_art=None,
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
            event.track = None
