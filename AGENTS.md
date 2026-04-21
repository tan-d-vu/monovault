# MusicVault Development Guide

## Project Overview

MusicVault is a lightweight desktop music file manager with manual categorization via metadata tags.

## Technology Stack

- **Language**: Python 3.10+
- **UI Framework**: PyQt6
- **Audio Metadata**: mutagen
- **Storage**: In-memory (no database)
- **Packaging**: PyInstaller

## Project Structure

```
monovault/
├── venv/                        # Virtual environment
├── src/
│   ├── models/                  # Data models (Track dataclass)
│   │   └── track.py
│   ├── core/                    # Business logic
│   │   ├── config.py            # JSON config for folders
│   │   ├── library.py           # In-memory library manager
│   │   ├── library_store.py     # File mtime cache
│   │   ├── metadata/            # Audio metadata read/write (format registry)
│   │   │   ├── __init__.py      # Public API (read_metadata, write_comment, ...)
│   │   │   ├── base.py          # Abstract parser base
│   │   │   ├── mp3_parser.py    # ID3/MP3 parser
│   │   │   ├── flac_parser.py   # Vorbis/FLAC parser
│   │   │   └── registry.py      # Parser registry by extension
│   │   ├── scanner.py           # Library folder scanner
│   │   ├── playback.py          # Audio playback engine
│   │   ├── categorizer.py       # Category add/remove orchestration
│   │   ├── category_sources.py  # Pluggable suggestion sources
│   │   ├── interfaces.py        # Protocol interfaces (IMetadataParser, ITrackRepository, ICategorySource)
│   │   ├── events.py            # EventBus and domain event dataclasses
│   │   └── volume_utils.py      # Portable/flash-drive volume identification
│   └── ui/                      # PyQt UI components
│       ├── main_window.py       # Main application window
│       ├── panels.py            # Folder tree, track details, playback bar panels
│       ├── track_table.py       # Track table widget and column enum
│       ├── widgets.py           # CategoryPill, SuggestionButton
│       ├── styles.py            # UI theme/styles
│       ├── scanner_worker.py    # Background folder-scan QThread worker
│       ├── controllers/         # Decoupled controllers bound to MainWindow
│       │   ├── playback_controller.py
│       │   ├── search_controller.py
│       │   └── category_controller.py
│       └── workers/             # Background QThread workers
│           └── metadata_worker.py
├── tests/                       # Test suite
├── resources/                   # Icons, images
├── pyproject.toml               # Project configuration
├── SPEC.md                      # Full specification
└── AGENTS.md                    # This file
```

## Build, Test & Lint Commands

```bash
# Install dependencies (including dev)
pip install -e ".[dev]"

# Run the application
python -m src.ui.main_window

# Run all tests
pytest

# Run a single test file
pytest tests/core/test_library.py

# Run a single test
pytest tests/core/test_library.py::TestLibraryManager::test_add_track_returns_positive_int

# Run tests by marker
pytest -m unit
pytest -m integration

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Lint with ruff
ruff check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/

# Build executable (Windows)
pyinstaller --onefile --windowed src/ui/main_window.py
```

## Code Style Guidelines

### Imports
- Use absolute imports: `from src.core.library import LibraryManager`
- Group imports in order: stdlib, third-party, local
- Sort alphabetically within groups
- One module per line

### Formatting
- Line length: 100 characters max
- Use 4 spaces for indentation (no tabs)
- Use ruff for formatting: `ruff format`
- One blank line between top-level definitions
- No trailing whitespace

### Types
- Use type hints for all function signatures
- Use `Optional[X]` instead of `X | None`
- Use built-in types directly: `list[str]`, `dict[str, int]`
- Use dataclasses for simple data containers

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `LibraryManager`)
- **Functions/methods**: `snake_case` (e.g., `add_track`)
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: prefix with `_` (e.g., `_tracks`)
- **Files**: `snake_case.py`

### Error Handling
- Use exceptions for exceptional cases, not flow control
- Catch specific exceptions, not bare `Exception`
- Log errors before re-raising when appropriate
- Never swallow exceptions silently without logging

### Code Patterns

#### Dataclass for models
```python
@dataclass
class Track:
    id: int
    file_path: str
    title: str
    artist: str
    album: str
    duration: float
    categories: list[str]
    album_art: Optional[bytes]
    folder_path: str
    comments: str = ""
    date_added: str = ""
```

#### PyQt signal connections
```python
self.search_input.textChanged.connect(self._on_search_changed)
```

#### Protocol/Interface pattern
```python
from src.core.interfaces import ITrackRepository

class LibraryManager(ITrackRepository):
    ...
```

### Testing Guidelines
- Use pytest with markers: `@pytest.mark.unit`, `@pytest.mark.integration`
- Use fixtures from `conftest.py`: `sample_track`, `sample_tracks`, `qapp`
- Test one thing per test function
- Use descriptive test names: `test_<method>_<expected_behavior>`

## Architecture Decisions

### JSON Config Location
- `~/.monovault/config.json` (Linux/macOS), `%APPDATA%/monovault/config.json` (Windows)
- Format: `{"folders": ["/path/to/music1"]}`

### Category Storage
- Uses COMMENT tag (COMM for MP3, COMMENT for FLAC)
- Format: space-separated words ("rock favorite workout")

### Category Suggestions
- Max 5 suggestions from same-artist tracks and shared categories
- Lowercase, deduplicated, excludes existing categories

### Search
- Debounced 1.5s with QTimer.singleShot
- Case-insensitive substring matching on title, artist, album, categories

## Key Modules

| Module | Purpose |
|--------|---------|
| `src/core/library.py` | In-memory track storage, search, deduplication |
| `src/core/library_store.py` | Persists track addition dates and file mtime cache |
| `src/core/config.py` | JSON config file management |
| `src/core/metadata/` | Audio metadata read/write via `mutagen`; format-registry package |
| `src/core/scanner.py` | Recursive folder scanning for audio files |
| `src/core/playback.py` | `QMediaPlayer` wrapper with position/duration/state signals |
| `src/core/categorizer.py` | Add/remove categories; writes via `metadata.write_comment` |
| `src/core/category_sources.py` | Pluggable suggestion sources (by artist, by shared category) |
| `src/core/interfaces.py` | Protocol interfaces for parsers, repositories, suggestion sources |
| `src/core/events.py` | `EventBus` and frozen-dataclass domain events |
| `src/core/volume_utils.py` | Volume identification for portable/flash-drive support |
| `src/ui/main_window.py` | `MainWindow` — layout creation and controller wiring |
| `src/ui/panels.py` | Folder tree, track details, and playback bar panels |
| `src/ui/track_table.py` | Track table widget with column enum |
| `src/ui/widgets.py` | `CategoryPill`, `SuggestionButton` |
| `src/ui/styles.py` | `THEME` dict and global `STYLESHEET` |
| `src/ui/controllers/playback_controller.py` | Playback state, track navigation, seeking |
| `src/ui/controllers/search_controller.py` | Debounced search with result set management |
| `src/ui/controllers/category_controller.py` | Category CRUD and suggestions for selected track |
| `src/ui/scanner_worker.py` | Background folder-scan worker (QThread) with progress/cancel |
| `src/ui/workers/metadata_worker.py` | Background metadata scanning on a `QThread` |

## Known Limitations

- No real-time metadata change detection (manual refresh only)
- Playback: basic controls only (no equalizer, playlist)
- Search: simple string matching, no fuzzy search
