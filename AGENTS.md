# MonoVault Development Guide

## Project Overview

MonoVault is a lightweight desktop music file manager with manual categorization via metadata tags.

See `SPEC.md` for the full feature specification, UI component details, and edge case handling.

## Technology Stack

- **Language**: Python 3.10+
- **UI Framework**: PyQt6
- **Audio Metadata**: mutagen
- **Storage**: In-memory (no database); per-folder `.monovault/` sidecars for persistence
- **Packaging**: PyInstaller

## Project Structure

```
monovault/
├── venv/
├── src/
│   ├── models/
│   │   └── track.py              # Track dataclass (id, file_path, title, artist, album,
│   │                             #   duration, categories, album_art, folder_path,
│   │                             #   comments, date_added + computed properties)
│   ├── core/
│   │   ├── config.py             # JSON config (~/.monovault/config.json): folders + volume registry
│   │   ├── library.py            # In-memory dict[int, Track] store; search; deduplication
│   │   ├── library_store.py      # Per-folder date-added cache ({folder}/.monovault/library.json)
│   │   ├── scanner.py            # Recursive folder scanner; returns Track objects
│   │   ├── playback.py           # QMediaPlayer wrapper with position/duration/state signals
│   │   ├── categorizer.py        # Category CRUD + bulk rename/merge/delete via replace_categories_everywhere
│   │   ├── category_sources.py   # Pluggable suggestion sources (ArtistCategorySource, SimilarCategoryCategorySource)
│   │   ├── category_stats.py     # compute_stats() → CategoryStats (counts, co-occurrences, orphans)
│   │   ├── duplicates.py         # find_duplicates() — union-find over 3 rules (artist+title, filename, title+duration)
│   │   ├── trash.py              # Per-folder TrashManager ({folder}/.monovault/trash/); atomic manifest writes
│   │   ├── interfaces.py         # Protocol interfaces: IMetadataParser, ITrackRepository, ICategorySource
│   │   ├── events.py             # EventBus + frozen domain event dataclasses
│   │   ├── volume_utils.py       # Portable/flash-drive volume ID sidecar read/write/discover
│   │   └── metadata/
│   │       ├── __init__.py       # Public API: read_metadata, write_comment, read_comment
│   │       ├── base.py           # Abstract parser base
│   │       ├── mp3_parser.py     # ID3/MP3 parser (mutagen)
│   │       ├── flac_parser.py    # Vorbis/FLAC parser (mutagen)
│   │       └── registry.py       # Parser registry by file extension
│   └── ui/
│       ├── main_window.py        # MainWindow — layout, signal wiring, controller coordination
│       ├── panels.py             # Folder tree, track details, playback bar, scan progress factory fns
│       ├── track_table.py        # TrackTableManager + Column enum
│       ├── category_stats_tab.py # CategoryStatsTab — usage stats, filter, rename/merge/delete
│       ├── duplicates_tab.py     # DuplicatesTab — runs find_duplicates, lists groups
│       ├── trash_dialog.py       # TrashDialog — list/restore/purge trashed tracks
│       ├── scanner_worker.py     # Background ScannerWorker (QThread) with progress/cancel
│       ├── widgets.py            # CategoryPill (× button), SuggestionButton, Toast
│       ├── styles.py             # THEME dict + global STYLESHEET
│       ├── controllers/
│       │   ├── playback_controller.py   # Playback state, track nav, seeking
│       │   ├── search_controller.py     # Debounced search + category filter
│       │   ├── category_controller.py   # Category CRUD, suggestions, async metadata writes
│       │   └── delete_controller.py     # Trash move/restore/purge coordinating TrashManager
│       ├── dialogs/
│       │   └── merge_dialog.py   # MergeDialog — multi-select category merge UI
│       └── workers/
│           └── metadata_worker.py  # MetadataWriteWorker (QThreadPool) for async tag writes
├── tests/
│   ├── conftest.py
│   ├── core/                     # Unit/integration tests for all core modules
│   └── ui/                       # Qt controller and widget tests (pytest-qt)
├── docs/                         # Implementation plans and architecture notes
├── pyproject.toml
├── SPEC.md
└── AGENTS.md
```

## Build, Test & Lint Commands

```bash
# Activate venv (Linux/macOS)
source venv/bin/activate

# Install dependencies (including dev)
pip install -e ".[dev]"

# Run the application
python -m src.ui.main_window

# Run all tests
pytest

# Run a single test file
pytest tests/core/test_library.py

# Run tests by marker
pytest -m unit
pytest -m integration

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Lint
ruff check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/

# Build executable (Windows)
pyinstaller --onefile --windowed src/ui/main_window.py --name MonoVault
```

## Architecture Decisions

### Storage layout
- **Global config**: `~/.monovault/config.json` — folder list + portable volume registry
- **Per-folder metadata**: `{folder}/.monovault/library.json` — date-added cache (relative POSIX paths as keys)
- **Per-folder trash**: `{folder}/.monovault/trash/manifest.json` + UUID-named audio files
- **Volume sidecar**: `{folder}/.monovault/volume_id` — UUID for portable drive reassociation
- Files are always the source of truth; in-memory state is rebuilt on every launch

### Category storage
- Written to COMMENT tag (COMM for MP3, COMMENT for FLAC) as a space-separated string (`"rock favorite workout"`)
- Writes are async via `MetadataWriteWorker` on a `QThreadPool(maxThreadCount=1)`; failures revert from disk

### UI layout
```
QVBoxLayout (central widget)
├── QSplitter (horizontal) — outer_splitter
│   ├── QTabWidget
│   │   ├── Library tab → inner QSplitter: folder_tree_panel | track_table_panel
│   │   ├── Duplicates tab → DuplicatesTab
│   │   └── Categories tab → CategoryStatsTab
│   └── details_panel (280px, non-collapsible)
├── scan_progress_bar (hidden when idle)
└── playback_bar (fixed at bottom)
```

### Duplicate detection
Three independent rules merged via union-find:
1. Same `artist` + `title` (case-insensitive)
2. Same `filename` (case-insensitive)
3. Same `title` + duration within 1.0 s tolerance

### Category suggestion algorithm
1. Collect categories from tracks by same artist
2. Collect categories from tracks sharing any existing category
3. Deduplicate, exclude already-applied, return up to 5

### Portable volume support
On launch, any configured folder that no longer exists is matched against the volume registry by UUID. If the volume is found at a new mount point, the path is updated automatically.

## Code Style Guidelines

### Imports
- Absolute imports: `from src.core.library import LibraryManager`
- Order: stdlib → third-party → local; sorted alphabetically within groups

### Formatting
- Line length: 100 characters (`ruff format`)
- 4 spaces, no tabs; no trailing whitespace

### Types
- Type hints on all function signatures
- `X | None` (not `Optional[X]`); built-in generics: `list[str]`, `dict[str, int]`
- Dataclasses for data containers

### Naming
- Classes: `PascalCase` | Functions/methods: `snake_case` | Constants: `UPPER_SNAKE_CASE`
- Private members: `_prefix` | Files: `snake_case.py`

### Error handling
- Catch specific exceptions; never swallow silently without logging
- Log before re-raising when appropriate

### Testing
- Markers: `@pytest.mark.unit`, `@pytest.mark.integration`
- Fixtures from `conftest.py`: `sample_track`, `sample_tracks`, `qapp`
- One assertion per test; descriptive names: `test_<method>_<expected_behavior>`

## Key Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+F` | Focus search |
| `Ctrl+R` | Refresh library |
| `Ctrl+O` | Add folder |
| `Ctrl+Shift+T` | Open Trash dialog |
| `Space` (track table) | Toggle playback |
| `Enter` (track table) | Play selected track |
| `Delete` (track table) | Move selected to Trash |

## Known Limitations

- No real-time file-system change detection (manual refresh only)
- Playback: basic controls only (no equalizer, playlist queue)
- Search: simple case-insensitive substring matching, no fuzzy search
