# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app
python -m src.ui.main_window

# Lint
ruff check src/

# Format
ruff format src/

# Tests
pytest

# Build standalone executable (Windows)
pyinstaller --onefile --windowed src/ui/main_window.py --name MusicVault
```

The venv is at `./venv`. Activate with `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows).

## Architecture

**PyQt6 desktop app** — single `MainWindow` with no secondary windows except dialogs.

### Data flow

```
Files (MP3/FLAC)
  └─ Scanner → Track objects → LibraryManager (in-memory dict)
                                      └─ Categorizer → writes back to file via metadata.write_comment()
```

The **library is purely in-memory**; files are the source of truth. On every launch, folders are re-scanned from the list persisted in `~/.monovault/config.json`. Categories are read from and written directly to the audio file's COMMENT/COMM metadata tag as a space-separated string (e.g. `"rock instrumental 90s"`).

### Module responsibilities

| Module | Role |
|---|---|
| `src/models/track.py` | `Track` dataclass — central data object passed everywhere |
| `src/core/config.py` | Persists folder list to `~/.monovault/config.json` |
| `src/core/library.py` | In-memory `dict[int, Track]` store; search; tracks by artist/category |
| `src/core/library_store.py` | Persists track addition dates to `~/.monovault/library.json` |
| `src/core/scanner.py` | Recursively scans folders for MP3/FLAC, returns `Track` objects |
| `src/core/metadata/` | Reads ID3/Vorbis tags via `mutagen` (format-registry package); `write_comment()` saves categories |
| `src/core/categorizer.py` | Add/remove/suggest categories; calls `write_comment` then updates library |
| `src/core/playback.py` | Thin wrapper around `QMediaPlayer`; emits position/duration/state signals |
| `src/ui/main_window.py` | `MainWindow` — all layout creation and signal wiring |
| `src/ui/widgets.py` | `CategoryPill` (row widget with × button), `SuggestionButton` |
| `src/ui/styles.py` | `THEME` dict (color tokens) and `STYLESHEET` string applied globally |

### UI layout

Three-panel `QSplitter` (folder tree | track table | details) above a fixed playback bar. The details panel contains a `QScrollArea` wrapping `categories_container` — its `QVBoxLayout` must have `AlignTop` and the container must use `QSizePolicy.Minimum` vertically, or categories will space out to fill the scroll area.

### Category suggestion algorithm

1. Collect categories from other tracks by same artist
2. Collect categories from tracks sharing any category with the current track
3. Deduplicate, exclude already-applied categories, limit to 5

### Config files

- `~/.monovault/config.json` — stores added folders as `{"folders": ["/path", ...]}`
- `~/.monovault/library.json` — caches file modification times for change detection
