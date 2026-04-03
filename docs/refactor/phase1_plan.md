```markdown
# Phase 1: Extract Interfaces & Fix Testability

## Overview

Extract Protocol-based interfaces from the core modules, replace the monolithic `metadata.py` with a format-registry pattern, add proper error logging, and establish test infrastructure. Zero UI changes -- the application must behave identically after this phase.

## Requirements

- Python `Protocol` classes for metadata parsing, track repository, and category suggestions
- Format-specific parser classes (`Mp3Parser`, `FlacParser`) behind a registry
- Replace all 6 silent `except Exception: return ...` blocks with logged errors
- pytest infrastructure with >= 80% coverage on core modules
- No changes to any UI file

## Architecture Changes

| Change | File(s) | Description |
|---|---|---|
| New interfaces | `src/core/interfaces.py` | `IMetadataParser`, `ITrackRepository`, `ICategorySource` Protocols |
| Metadata package | `src/core/metadata/` | Replace `src/core/metadata.py` with package |
| Format registry | `src/core/metadata/registry.py` | Maps file extensions to parser implementations |
| Category sources | `src/core/category_sources.py` | Pluggable suggestion strategy implementations |
| Library refactor | `src/core/library.py` | Conform to `ITrackRepository` protocol |
| Test infrastructure | `tests/`, `pyproject.toml` | pytest setup, fixtures, initial test suite |

---

## Implementation Steps

### Step 1: Test Infrastructure Setup

**Files to create:**
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/core/__init__.py`
- `tests/ui/__init__.py`

**Files to modify:**
- `pyproject.toml` — add pytest + pytest-cov to dev dependencies

**Action**: Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = [
    "pyinstaller>=6.0.0",
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.1.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
]
```

**Action**: Create `tests/conftest.py`:
```python
import pytest
from src.models.track import Track


@pytest.fixture
def sample_track() -> Track:
    return Track(
        id=1,
        file_path="/tmp/test.mp3",
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration=180.0,
        categories=["rock", "instrumental"],
        album_art=None,
        folder_path="/tmp",
        comments="rock instrumental",
        date_added="2025-01-01",
    )


@pytest.fixture
def sample_track_no_categories() -> Track:
    return Track(
        id=2,
        file_path="/tmp/test2.flac",
        title="Another Song",
        artist="Test Artist",
        album="Test Album",
        duration=240.0,
        categories=[],
        album_art=None,
        folder_path="/tmp",
        comments="",
        date_added="2025-01-02",
    )


@pytest.fixture
def sample_tracks(sample_track, sample_track_no_categories) -> list[Track]:
    return [sample_track, sample_track_no_categories]
```

**Dependencies**: None
**Risk**: Low
**Parallel track**: Independent

---

### Step 2: Define Protocol Interfaces

**File to create**: `src/core/interfaces.py`

**Action**: Define three Protocol classes:

```python
from typing import Protocol, Optional
from ..models.track import Track


class IMetadataParser(Protocol):
    """Reads and writes metadata for a specific audio format."""

    def can_handle(self, file_path: str) -> bool:
        """Return True if this parser supports the given file."""
        ...

    def read_metadata(self, file_path: str) -> dict:
        """Read title, artist, album, duration, album_art from file.
        Returns empty dict on failure."""
        ...

    def read_comment(self, file_path: str) -> list[str]:
        """Read categories from the COMMENT tag as a list of strings."""
        ...

    def read_comment_raw(self, file_path: str) -> str:
        """Read the raw COMMENT tag string."""
        ...

    def write_comment(self, file_path: str, categories: list[str]) -> bool:
        """Write categories to the COMMENT tag. Returns True on success."""
        ...

    def write_comments(self, file_path: str, comments: str) -> bool:
        """Write raw comment string. Returns True on success."""
        ...

    def get_album_art(self, file_path: str) -> Optional[bytes]:
        """Extract album art bytes, or None."""
        ...


class ITrackRepository(Protocol):
    """Stores and queries Track objects."""

    def add_track(self, track: Track) -> int:
        """Add or update a track. Returns the track ID."""
        ...

    def update_track(self, track: Track) -> None:
        """Update an existing track in the store."""
        ...

    def get_all_tracks(self) -> list[Track]:
        """Return all tracks."""
        ...

    def get_track_by_id(self, track_id: int) -> Optional[Track]:
        """Return a track by ID, or None."""
        ...

    def get_track_by_path(self, file_path: str) -> Optional[Track]:
        """Return a track by file path, or None."""
        ...

    def search(self, query: str) -> list[Track]:
        """Full-text search across title, artist, album, categories."""
        ...

    def get_tracks_by_artist(self, artist: str) -> list[Track]:
        """Return all tracks by a given artist (case-insensitive)."""
        ...

    def get_tracks_with_categories(self, categories: list[str]) -> list[Track]:
        """Return tracks that have any of the given categories."""
        ...


class ICategorySource(Protocol):
    """Provides category suggestions for a track."""

    def get_suggestions(
        self, track: Track, existing_categories: set[str], max_results: int = 5
    ) -> list[tuple[str, str]]:
        """Return list of (category, source_label) tuples.
        Must exclude categories already in existing_categories."""
        ...
```

**Dependencies**: None
**Risk**: Low
**Parallel track**: Independent (can be done alongside Step 1)

---

### Step 3: Create Metadata Package with Format-Specific Parsers

**Files to create:**
- `src/core/metadata/__init__.py`
- `src/core/metadata/base.py`
- `src/core/metadata/mp3_parser.py`
- `src/core/metadata/flac_parser.py`
- `src/core/metadata/registry.py`

**File to delete (after migration):**
- `src/core/metadata.py` (replaced by package)

#### 3a. `src/core/metadata/base.py`

```python
"""Base class with shared validation and logging for metadata parsers."""

import logging
from pathlib import Path
from typing import Optional

import mutagen

logger = logging.getLogger(__name__)


class BaseParser:
    """Shared utilities for format-specific parsers."""

    supported_extensions: set[str] = set()

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.supported_extensions

    def _load_audio(self, file_path: str) -> Optional[mutagen.FileType]:
        """Load audio file with proper error handling. Returns None on failure."""
        path = Path(file_path)
        if not path.exists():
            logger.warning("File not found: %s", file_path)
            return None
        try:
            audio = mutagen.File(file_path)
            if audio is None:
                logger.warning("Mutagen returned None for: %s", file_path)
            return audio
        except mutagen.MutagenError as e:
            logger.error("Failed to load audio file %s: %s", file_path, e)
            return None

    def _safe_tag_get(self, tags: dict, key: str, default: str = "") -> str:
        """Safely extract a string from tags."""
        value = tags.get(key)
        if value is None:
            return default
        if isinstance(value, list) and value:
            return str(value[0])
        return str(value)
```

#### 3b. `src/core/metadata/mp3_parser.py`

```python
"""MP3 metadata parser using mutagen ID3 tags."""

import logging
from typing import Optional

import mutagen.id3
from mutagen.mp3 import MP3

from .base import BaseParser

logger = logging.getLogger(__name__)


class Mp3Parser(BaseParser):
    supported_extensions = {".mp3"}

    def read_metadata(self, file_path: str) -> dict:
        audio = self._load_audio(file_path)
        if audio is None:
            return {}

        metadata = {
            "title": "",
            "artist": "",
            "album": "",
            "duration": getattr(audio.info, "length", 0.0) if audio.info else 0.0,
            "album_art": None,
        }

        if not hasattr(audio, "tags") or audio.tags is None:
            return metadata

        metadata["title"] = self._safe_tag_get(audio.tags, "title")
        metadata["artist"] = self._safe_tag_get(audio.tags, "artist")
        metadata["album"] = self._safe_tag_get(audio.tags, "album")

        if hasattr(audio.tags, "getall"):
            for pic in audio.tags.getall("APIC"):
                metadata["album_art"] = pic.data
                break

        return metadata

    def read_comment(self, file_path: str) -> list[str]:
        audio = self._load_audio(file_path)
        if audio is None or not hasattr(audio, "tags") or audio.tags is None:
            return []

        try:
            if hasattr(audio.tags, "getall"):
                comm_all = list(audio.tags.getall("COMM"))
                if comm_all:
                    text = comm_all[0].text
                    if isinstance(text, list) and text:
                        text = text[0]
                    if text:
                        return text.split()
            return []
        except (AttributeError, IndexError, TypeError) as e:
            logger.error("Failed to read comment from %s: %s", file_path, e)
            return []

    def read_comment_raw(self, file_path: str) -> str:
        audio = self._load_audio(file_path)
        if audio is None or not hasattr(audio, "tags") or audio.tags is None:
            return ""

        try:
            if hasattr(audio.tags, "getall"):
                comm_all = list(audio.tags.getall("COMM"))
                if comm_all:
                    text = comm_all[0].text
                    if isinstance(text, list) and text:
                        text = text[0]
                    if text:
                        return text
            return ""
        except (AttributeError, IndexError, TypeError) as e:
            logger.error("Failed to read raw comment from %s: %s", file_path, e)
            return ""

    def write_comment(self, file_path: str, categories: list[str]) -> bool:
        audio = self._load_audio(file_path)
        if audio is None:
            return False

        try:
            if audio.tags is None:
                audio.add_tags()
            comment_text = " ".join(categories)
            audio.tags.setall(
                "COMM",
                [mutagen.id3.COMM(encoding=3, lang="eng", text=comment_text)],
            )
            audio.save()
            return True
        except mutagen.MutagenError as e:
            logger.error("Failed to write comment to %s: %s", file_path, e)
            return False

    def write_comments(self, file_path: str, comments: str) -> bool:
        audio = self._load_audio(file_path)
        if audio is None:
            return False

        try:
            if audio.tags is None:
                audio.add_tags()
            audio.tags.setall(
                "COMM",
                [mutagen.id3.COMM(encoding=3, lang="eng", text=comments)],
            )
            audio.save()
            return True
        except mutagen.MutagenError as e:
            logger.error("Failed to write comments to %s: %s", file_path, e)
            return False

    def get_album_art(self, file_path: str) -> Optional[bytes]:
        audio = self._load_audio(file_path)
        if audio is None or not hasattr(audio, "tags") or audio.tags is None:
            return None

        try:
            if hasattr(audio.tags, "getall"):
                for pic in audio.tags.getall("APIC"):
                    return pic.data
            return None
        except (AttributeError, IndexError) as e:
            logger.error("Failed to read album art from %s: %s", file_path, e)
            return None
```

#### 3c. `src/core/metadata/flac_parser.py`

```python
"""FLAC metadata parser using mutagen Vorbis comments."""

import logging
from typing import Optional

from mutagen.flac import FLAC

from .base import BaseParser

logger = logging.getLogger(__name__)


class FlacParser(BaseParser):
    supported_extensions = {".flac"}

    def read_metadata(self, file_path: str) -> dict:
        audio = self._load_audio(file_path)
        if audio is None:
            return {}

        metadata = {
            "title": "",
            "artist": "",
            "album": "",
            "duration": getattr(audio.info, "length", 0.0) if audio.info else 0.0,
            "album_art": None,
        }

        if isinstance(audio, FLAC) and hasattr(audio, "pictures") and audio.pictures:
            metadata["album_art"] = audio.pictures[0].data

        if hasattr(audio, "tags") and audio.tags:
            metadata["title"] = self._safe_tag_get(audio.tags, "title")
            metadata["artist"] = self._safe_tag_get(audio.tags, "artist")
            metadata["album"] = self._safe_tag_get(audio.tags, "album")

        return metadata

    def read_comment(self, file_path: str) -> list[str]:
        audio = self._load_audio(file_path)
        if audio is None or not hasattr(audio, "tags") or audio.tags is None:
            return []

        try:
            comment = audio.tags.get("COMMENT")
            if comment:
                text = comment[0] if isinstance(comment, list) else comment
                if isinstance(text, list) and text:
                    text = text[0]
                if text:
                    return text.split()
            return []
        except (AttributeError, IndexError, TypeError) as e:
            logger.error("Failed to read comment from %s: %s", file_path, e)
            return []

    def read_comment_raw(self, file_path: str) -> str:
        audio = self._load_audio(file_path)
        if audio is None or not hasattr(audio, "tags") or audio.tags is None:
            return ""

        try:
            comment = audio.tags.get("COMMENT")
            if comment:
                text = comment[0] if isinstance(comment, list) else comment
                if isinstance(text, list) and text:
                    text = text[0]
                if text:
                    return text
            return ""
        except (AttributeError, IndexError, TypeError) as e:
            logger.error("Failed to read raw comment from %s: %s", file_path, e)
            return ""

    def write_comment(self, file_path: str, categories: list[str]) -> bool:
        audio = self._load_audio(file_path)
        if audio is None:
            return False

        try:
            if not isinstance(audio, FLAC):
                logger.error("Expected FLAC file but got %s: %s", type(audio), file_path)
                return False
            comment_text = " ".join(categories)
            audio.tags["COMMENT"] = [comment_text]
            audio.save()
            return True
        except Exception as e:
            logger.error("Failed to write comment to %s: %s", file_path, e)
            return False

    def write_comments(self, file_path: str, comments: str) -> bool:
        audio = self._load_audio(file_path)
        if audio is None:
            return False

        try:
            if not isinstance(audio, FLAC):
                logger.error("Expected FLAC file but got %s: %s", type(audio), file_path)
                return False
            audio.tags["COMMENT"] = [comments]
            audio.save()
            return True
        except Exception as e:
            logger.error("Failed to write comments to %s: %s", file_path, e)
            return False

    def get_album_art(self, file_path: str) -> Optional[bytes]:
        audio = self._load_audio(file_path)
        if audio is None:
            return None

        try:
            if isinstance(audio, FLAC) and hasattr(audio, "pictures") and audio.pictures:
                return audio.pictures[0].data
            if hasattr(audio, "tags") and audio.tags and hasattr(audio.tags, "getall"):
                for pic in audio.tags.getall("APIC"):
                    return pic.data
            return None
        except (AttributeError, IndexError) as e:
            logger.error("Failed to read album art from %s: %s", file_path, e)
            return None
```

#### 3d. `src/core/metadata/registry.py`

```python
"""Format registry that dispatches to the correct parser by file extension."""

import logging
from pathlib import Path
from typing import Optional

from .base import BaseParser
from .mp3_parser import Mp3Parser
from .flac_parser import FlacParser

logger = logging.getLogger(__name__)


class MetadataRegistry:
    """Maps file extensions to parser instances. Singleton-like usage expected."""

    def __init__(self) -> None:
        self._parsers: list[BaseParser] = []

    def register(self, parser: BaseParser) -> None:
        self._parsers.append(parser)

    def get_parser(self, file_path: str) -> Optional[BaseParser]:
        for parser in self._parsers:
            if parser.can_handle(file_path):
                return parser
        return None

    def supported_extensions(self) -> set[str]:
        result: set[str] = set()
        for parser in self._parsers:
            result |= parser.supported_extensions
        return result

    def is_supported(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.supported_extensions()


def create_default_registry() -> MetadataRegistry:
    """Create a registry with MP3 and FLAC parsers."""
    registry = MetadataRegistry()
    registry.register(Mp3Parser())
    registry.register(FlacParser())
    return registry
```

#### 3e. `src/core/metadata/__init__.py`

Backward-compatible re-exports so existing imports continue to work:

```python
"""Metadata package — backward-compatible API.

Existing code imports:
    from src.core.metadata import read_metadata, write_comment, ...

These module-level functions delegate to the default registry.
"""

from typing import Optional
from .registry import create_default_registry

_registry = create_default_registry()

SUPPORTED_EXTENSIONS = _registry.supported_extensions()


def is_supported(path: str) -> bool:
    return _registry.is_supported(path)


def read_metadata(file_path: str) -> dict:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return {}
    return parser.read_metadata(file_path)


def read_comment(file_path: str) -> list[str]:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return []
    return parser.read_comment(file_path)


def read_comment_raw(file_path: str) -> str:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return ""
    return parser.read_comment_raw(file_path)


def write_comment(file_path: str, categories: list[str]) -> bool:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return False
    return parser.write_comment(file_path, categories)


def write_comments(file_path: str, comments: str) -> bool:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return False
    return parser.write_comments(file_path, comments)


def get_album_art(file_path: str) -> Optional[bytes]:
    parser = _registry.get_parser(file_path)
    if parser is None:
        return None
    return parser.get_album_art(file_path)
```

**Dependencies**: Step 2 (interfaces defined)
**Risk**: Medium -- this is the largest change; backward-compat `__init__.py` mitigates breakage
**Parallel track**: Track A (independent of B and C)

---

### Step 4: Refactor LibraryManager to Conform to ITrackRepository

**File to modify**: `src/core/library.py`

**Action**: No signature changes needed. `LibraryManager` already satisfies `ITrackRepository` structurally (duck typing). Changes:

1. Add `update_track` return type annotation (`-> None`)
2. Add module docstring referencing the protocol
3. Add type annotations where missing

The key change is that downstream code (Phase 2 controllers) will type-hint against `ITrackRepository` rather than `LibraryManager` directly. In Phase 1, we only need to verify structural compatibility.

**Action**: Create `tests/core/test_library.py`:
```python
import pytest
from src.core.library import LibraryManager
from src.core.interfaces import ITrackRepository
from src.models.track import Track


@pytest.mark.unit
class TestLibraryManager:
    def test_conforms_to_protocol(self):
        """LibraryManager structurally satisfies ITrackRepository."""
        manager = LibraryManager()
        # Structural check — if this doesn't error, protocol is satisfied
        repo: ITrackRepository = manager  # type: ignore[assignment]

    def test_add_track(self, sample_track):
        manager = LibraryManager()
        track_id = manager.add_track(sample_track)
        assert track_id > 0
        assert manager.get_track_by_id(track_id) is not None

    def test_add_duplicate_track_updates(self, sample_track):
        manager = LibraryManager()
        id1 = manager.add_track(sample_track)
        id2 = manager.add_track(sample_track)
        assert id1 == id2
        assert len(manager.get_all_tracks()) == 1

    def test_search_by_title(self, sample_track):
        manager = LibraryManager()
        manager.add_track(sample_track)
        results = manager.search("Test Song")
        assert len(results) == 1

    def test_search_by_category(self, sample_track):
        manager = LibraryManager()
        manager.add_track(sample_track)
        results = manager.search("rock")
        assert len(results) == 1

    def test_search_no_results(self, sample_track):
        manager = LibraryManager()
        manager.add_track(sample_track)
        results = manager.search("nonexistent")
        assert len(results) == 0

    def test_get_tracks_by_artist(self, sample_tracks):
        manager = LibraryManager()
        for t in sample_tracks:
            manager.add_track(t)
        results = manager.get_tracks_by_artist("Test Artist")
        assert len(results) == 2

    def test_get_tracks_with_categories(self, sample_track):
        manager = LibraryManager()
        manager.add_track(sample_track)
        results = manager.get_tracks_with_categories(["rock"])
        assert len(results) == 1

    def test_remove_folder(self, sample_track):
        manager = LibraryManager()
        manager.add_track(sample_track)
        assert len(manager.get_all_tracks()) == 1
        manager.remove_folder("/tmp")
        # Track persists because folder was not in config
        # This test verifies the removal path works

    def test_clear(self, sample_track):
        manager = LibraryManager()
        manager.add_track(sample_track)
        manager.clear()
        assert len(manager.get_all_tracks()) == 0
```

**Dependencies**: Step 2 (interfaces)
**Risk**: Low -- no behavioral changes
**Parallel track**: Track B

---

### Step 5: Create Pluggable Category Sources

**File to create**: `src/core/category_sources.py`

**Action**: Extract suggestion logic from `Categorizer` into separate `ICategorySource` implementations:

```python
"""Pluggable category suggestion sources."""

from ..models.track import Track
from .interfaces import ITrackRepository


class ArtistCategorySource:
    """Suggests categories from other tracks by the same artist."""

    def __init__(self, repository: ITrackRepository) -> None:
        self._repo = repository

    def get_suggestions(
        self, track: Track, existing_categories: set[str], max_results: int = 5
    ) -> list[tuple[str, str]]:
        if not track.artist:
            return []

        suggestions: list[tuple[str, str]] = []
        same_artist = self._repo.get_tracks_by_artist(track.artist)

        for t in same_artist:
            if t.id == track.id:
                continue
            for cat in t.categories:
                if cat.lower() not in existing_categories and len(suggestions) < max_results:
                    if not any(s[0] == cat.lower() for s in suggestions):
                        suggestions.append((cat.lower(), "same artist"))

        return suggestions[:max_results]


class SimilarCategoryCategorySource:
    """Suggests categories from tracks sharing any category with the current track."""

    def __init__(self, repository: ITrackRepository) -> None:
        self._repo = repository

    def get_suggestions(
        self, track: Track, existing_categories: set[str], max_results: int = 5
    ) -> list[tuple[str, str]]:
        if not track.categories:
            return []

        suggestions: list[tuple[str, str]] = []
        similar = self._repo.get_tracks_with_categories(track.categories)

        for t in similar:
            if t.id == track.id:
                continue
            for cat in t.categories:
                if cat.lower() not in existing_categories and len(suggestions) < max_results:
                    if not any(s[0] == cat.lower() for s in suggestions):
                        suggestions.append((cat.lower(), "similar category"))

        return suggestions[:max_results]
```

**File to modify**: `src/core/categorizer.py`

**Action**: Refactor `Categorizer` to accept a list of `ICategorySource` instances and delegate suggestion gathering:

```python
"""Category management — add/remove categories, delegate suggestions to sources."""

import logging
from typing import Optional

from ..models.track import Track
from .interfaces import ITrackRepository, ICategorySource
from .metadata import write_comment

logger = logging.getLogger(__name__)


class Categorizer:
    def __init__(
        self,
        library: ITrackRepository,
        sources: Optional[list[ICategorySource]] = None,
    ) -> None:
        self._library = library
        self._sources = sources or []

    def get_suggestions(
        self, track: Track, max_suggestions: int = 5
    ) -> list[tuple[str, str]]:
        if not track:
            return []

        existing = {c.lower() for c in track.categories}
        all_suggestions: list[tuple[str, str]] = []
        seen: set[str] = set()

        for source in self._sources:
            for cat, label in source.get_suggestions(track, existing, max_suggestions):
                if cat not in seen:
                    seen.add(cat)
                    all_suggestions.append((cat, label))
                if len(all_suggestions) >= max_suggestions:
                    return all_suggestions

        return all_suggestions

    def add_category(self, track: Track, category: str) -> bool:
        category = category.strip().lower()
        if not category or category in [c.lower() for c in track.categories]:
            return False

        new_categories = track.categories + [category]
        success = write_comment(track.file_path, new_categories)

        if success:
            track.categories = new_categories
            self._library.update_track(track)
        else:
            logger.error("Failed to write category '%s' to %s", category, track.file_path)

        return success

    def remove_category(self, track: Track, category: str) -> bool:
        category_lower = category.lower()
        if category_lower not in [c.lower() for c in track.categories]:
            return False

        new_categories = [c for c in track.categories if c.lower() != category_lower]
        success = write_comment(track.file_path, new_categories)

        if success:
            track.categories = new_categories
            self._library.update_track(track)
        else:
            logger.error(
                "Failed to remove category '%s' from %s", category, track.file_path
            )

        return success

    def clear_categories(self, track: Track) -> bool:
        success = write_comment(track.file_path, [])

        if success:
            track.categories = []
            self._library.update_track(track)
        else:
            logger.error("Failed to clear categories for %s", track.file_path)

        return success
```

**File to modify**: `src/ui/main_window.py` (line 52)

Change the `Categorizer` initialization to inject sources:

```python
# Before (line 52):
self.categorizer = Categorizer(self.library)

# After:
from ..core.category_sources import ArtistCategorySource, SimilarCategoryCategorySource
self.categorizer = Categorizer(
    self.library,
    sources=[
        ArtistCategorySource(self.library),
        SimilarCategoryCategorySource(self.library),
    ],
)
```

**Dependencies**: Steps 2 and 4 (interfaces + repository)
**Risk**: Medium -- behavioral change in suggestion algorithm must be regression-tested
**Parallel track**: Track C (depends on Track B completing)

---

### Step 6: Write Metadata Tests

**Files to create:**
- `tests/core/test_metadata_mp3.py`
- `tests/core/test_metadata_flac.py`
- `tests/core/test_metadata_registry.py`

**Action**: Test parsers using temporary audio files created with mutagen:

```python
# tests/core/test_metadata_registry.py
import pytest
from src.core.metadata.registry import MetadataRegistry, create_default_registry


@pytest.mark.unit
class TestMetadataRegistry:
    def test_default_registry_supports_mp3(self):
        reg = create_default_registry()
        assert reg.is_supported("song.mp3")

    def test_default_registry_supports_flac(self):
        reg = create_default_registry()
        assert reg.is_supported("song.flac")

    def test_unsupported_extension(self):
        reg = create_default_registry()
        assert not reg.is_supported("song.wav")

    def test_get_parser_mp3(self):
        reg = create_default_registry()
        parser = reg.get_parser("song.mp3")
        assert parser is not None

    def test_get_parser_none_for_unknown(self):
        reg = create_default_registry()
        assert reg.get_parser("song.aac") is None

    def test_empty_registry(self):
        reg = MetadataRegistry()
        assert not reg.is_supported("song.mp3")
        assert reg.get_parser("song.mp3") is None
        assert reg.supported_extensions() == set()
```

```python
# tests/core/test_metadata_mp3.py
import pytest
import tempfile
import shutil
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, COMM

from src.core.metadata.mp3_parser import Mp3Parser


@pytest.fixture
def mp3_file(tmp_path):
    """Create a minimal valid MP3 file for testing."""
    # Create a minimal MP3 frame (silence)
    mp3_path = tmp_path / "test.mp3"
    # Minimal MP3: MPEG1 Layer3 frame header + padding
    # Frame sync: 0xFF 0xFB, 128kbps, 44100Hz, stereo
    frame = b'\xff\xfb\x90\x00' + b'\x00' * 413
    mp3_path.write_bytes(frame * 3)

    audio = MP3(str(mp3_path))
    audio.add_tags()
    audio.tags.add(TIT2(encoding=3, text=["Test Title"]))
    audio.tags.add(TPE1(encoding=3, text=["Test Artist"]))
    audio.tags.add(TALB(encoding=3, text=["Test Album"]))
    audio.tags.add(COMM(encoding=3, lang="eng", text="rock instrumental"))
    audio.save()
    return str(mp3_path)


@pytest.mark.unit
class TestMp3Parser:
    def test_can_handle_mp3(self):
        parser = Mp3Parser()
        assert parser.can_handle("song.mp3")
        assert parser.can_handle("SONG.MP3")
        assert not parser.can_handle("song.flac")

    def test_read_metadata(self, mp3_file):
        parser = Mp3Parser()
        meta = parser.read_metadata(mp3_file)
        assert meta["title"] == "Test Title"
        assert meta["artist"] == "Test Artist"
        assert meta["album"] == "Test Album"

    def test_read_comment(self, mp3_file):
        parser = Mp3Parser()
        cats = parser.read_comment(mp3_file)
        assert "rock" in cats
        assert "instrumental" in cats

    def test_read_comment_raw(self, mp3_file):
        parser = Mp3Parser()
        raw = parser.read_comment_raw(mp3_file)
        assert raw == "rock instrumental"

    def test_write_comment(self, mp3_file):
        parser = Mp3Parser()
        assert parser.write_comment(mp3_file, ["jazz", "fusion"])
        cats = parser.read_comment(mp3_file)
        assert cats == ["jazz", "fusion"]

    def test_read_metadata_missing_file(self):
        parser = Mp3Parser()
        assert parser.read_metadata("/nonexistent/file.mp3") == {}

    def test_read_comment_missing_file(self):
        parser = Mp3Parser()
        assert parser.read_comment("/nonexistent/file.mp3") == []
```

Similar pattern for `test_metadata_flac.py` using `mutagen.flac.FLAC`.

**Dependencies**: Step 3 (parsers exist)
**Risk**: Low
**Parallel track**: Part of Track A

---

### Step 7: Write Categorizer and Category Source Tests

**Files to create:**
- `tests/core/test_categorizer.py`
- `tests/core/test_category_sources.py`

**Action**: Test with mock `ITrackRepository`:

```python
# tests/core/test_category_sources.py
import pytest
from unittest.mock import MagicMock
from src.core.category_sources import ArtistCategorySource, SimilarCategoryCategorySource
from src.models.track import Track


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    return repo


@pytest.mark.unit
class TestArtistCategorySource:
    def test_suggests_from_same_artist(self, mock_repo, sample_track):
        other = Track(
            id=99, file_path="/tmp/other.mp3", title="Other",
            artist="Test Artist", album="A", duration=100.0,
            categories=["jazz"], album_art=None, folder_path="/tmp",
        )
        mock_repo.get_tracks_by_artist.return_value = [sample_track, other]

        source = ArtistCategorySource(mock_repo)
        suggestions = source.get_suggestions(
            sample_track, {"rock", "instrumental"}, max_results=5
        )
        assert any(s[0] == "jazz" for s in suggestions)

    def test_empty_for_unknown_artist(self, mock_repo, sample_track):
        sample_track.artist = ""
        source = ArtistCategorySource(mock_repo)
        suggestions = source.get_suggestions(sample_track, set(), max_results=5)
        assert suggestions == []

    def test_excludes_existing_categories(self, mock_repo, sample_track):
        other = Track(
            id=99, file_path="/tmp/other.mp3", title="Other",
            artist="Test Artist", album="A", duration=100.0,
            categories=["rock"], album_art=None, folder_path="/tmp",
        )
        mock_repo.get_tracks_by_artist.return_value = [sample_track, other]

        source = ArtistCategorySource(mock_repo)
        suggestions = source.get_suggestions(
            sample_track, {"rock", "instrumental"}, max_results=5
        )
        assert not any(s[0] == "rock" for s in suggestions)
```

**Dependencies**: Steps 2 and 5
**Risk**: Low
**Parallel track**: Part of Track C

---

### Step 8: Write Scanner Tests

**File to create**: `tests/core/test_scanner.py`

**Action**: Test `Scanner` with a temp directory containing test audio files. Mock `metadata` functions for unit tests, use real files for integration tests.

**Dependencies**: Step 3 (metadata package)
**Risk**: Low
**Parallel track**: Can be done alongside any track

---

## Parallel Work Summary

```
Track A (metadata)          Track B (library)           Track C (categories)
─────────────────           ─────────────────           ────────────────────
Step 1: test infra (shared) Step 1: test infra (shared) Step 1: test infra (shared)
Step 2: interfaces (shared) Step 2: interfaces (shared) Step 2: interfaces (shared)
Step 3: metadata package    Step 4: library refactor    Step 5: category sources
Step 6: metadata tests      Step 4: library tests       Step 7: categorizer tests
                            Step 8: scanner tests

Merge order: A → B → C (C depends on B for ITrackRepository)
```

## Acceptance Criteria

- [ ] `python -m src.ui.main_window` launches and functions identically to current
- [ ] `src/core/metadata.py` (file) replaced by `src/core/metadata/` (package) with backward-compat `__init__.py`
- [ ] `Mp3Parser` and `FlacParser` each handle their format independently
- [ ] `MetadataRegistry` dispatches to correct parser by extension
- [ ] Zero silent `except Exception` blocks — all exceptions logged with context
- [ ] `IMetadataParser`, `ITrackRepository`, `ICategorySource` Protocols defined
- [ ] `Categorizer` accepts pluggable `ICategorySource` list
- [ ] `pytest --cov=src/core --cov-report=term-missing` shows >= 80% on core modules
- [ ] `ruff check src/` passes with no errors
- [ ] No UI files changed except the single-line `Categorizer` initialization in `main_window.py`

## Test Strategy

| Test file | What it covers | Type |
|---|---|---|
| `tests/core/test_metadata_mp3.py` | `Mp3Parser` read/write with real temp files | Integration |
| `tests/core/test_metadata_flac.py` | `FlacParser` read/write with real temp files | Integration |
| `tests/core/test_metadata_registry.py` | `MetadataRegistry` dispatch logic | Unit |
| `tests/core/test_library.py` | `LibraryManager` CRUD, search, protocol conformance | Unit |
| `tests/core/test_categorizer.py` | `Categorizer` add/remove with mocked repo + metadata | Unit |
| `tests/core/test_category_sources.py` | `ArtistCategorySource`, `SimilarCategoryCategorySource` | Unit |
| `tests/core/test_scanner.py` | `Scanner` with mocked metadata functions | Unit |

## Risks & Mitigations

- **Risk**: Replacing `metadata.py` (file) with `metadata/` (package) breaks imports
  - Mitigation: `__init__.py` re-exports all existing public functions with identical signatures
- **Risk**: `Categorizer` suggestion behavior changes subtly with new source pattern
  - Mitigation: Write characterization tests capturing current behavior before refactoring
- **Risk**: FLAC parser handles edge case differently than combined function
  - Mitigation: Integration tests with real audio files for both formats
```

---