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
├── venv/                    # Virtual environment (created after setup)
├── src/
│   ├── models/              # Data models
│   │   └── track.py         # Track dataclass
│   ├── core/                # Business logic
│   │   ├── library.py       # In-memory library manager
│   │   ├── metadata.py      # Audio metadata read/write
│   │   ├── scanner.py       # Library folder scanner
│   │   ├── playback.py      # Audio playback engine
│   │   └── categorizer.py   # Category suggestions
│   └── ui/                  # PyQt UI components
│       ├── main_window.py   # Main application window
│       ├── widgets.py       # Custom widgets
│       └── styles.py        # UI theme/styles
├── resources/               # Icons, images
├── pyproject.toml           # Project configuration
├── SPEC.md                  # Full specification
└── AGENTS.md                # This file
```

## Setup Instructions

### 1. Create and Activate Virtual Environment

```bash
cd /home/tdv/projects/monovault
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 2. Install Dependencies

```bash
pip install PyQt6 mutagen
```

### 3. Run Development Mode

```bash
python -m src.ui.main_window
```

### 4. Build Executable (Windows)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed src/ui/main_window.py
```

## Architecture Decisions

### 1. PyQt6 over Tkinter/PySimpleGUI
- **Reason**: Rich UI capabilities, native look, excellent documentation
- **Alternative considered**: CustomTkinter (simpler but less flexible)

### 2. mutagen for metadata
- **Reason**: Mature library supporting MP3 (ID3), FLAC (Vorbis), WAV (RIFF)
- **Alternative**: eyeD3 (MP3 only), tinytag (read-only)

### 3. In-memory storage
- **Reason**: 2000+ tracks uses only ~700KB memory, simpler than SQLite
- **Design**: All tracks kept in memory; audio files remain source of truth

### 4. COMMENT tag for categories
- **Reason**: Universal across MP3/FLAC/WAV, user-editable in other apps
- **Format**: Space-separated words (e.g., "rock favorite workout")

### 5. Category suggestion algorithm
- **Source 1**: Categories from tracks with same artist
- **Source 2**: Categories from tracks sharing any category
- **Limit**: Max 5 suggestions
- **Normalization**: Lowercase, deduplicated, exclude existing

### 6. Debounced search (1.5s)
- **Reason**: Performance for large libraries; no enter key needed
- **Implementation**: QTimer with single shot

## Key Modules

### library.py
- `add_folder(path)` - Add folder to library
- `add_track(track)` - Add track (handles duplicates by file_path)
- `get_all_tracks()` - Get all tracks
- `search(query)` - Search by title, artist, album, category
- `get_tracks_by_artist(artist)` - Get tracks by artist
- `get_tracks_with_categories(categories)` - Get tracks with matching categories
- `update_track(track)` - Update track in memory
- `clear()` - Clear all tracks

### metadata.py
- `read_metadata(path)` - Extract title, artist, album, duration, art
- `write_comment(path, categories)` - Write COMMENT tag
- `read_comment(path)` - Read COMMENT tag
- FLAC uses `audio.pictures` for album art (not tags)

### scanner.py
- `scan_folder(path)` - Recursively find audio files
- `process_file(file_path, folder_path)` - Process single file

### playback.py
- Wraps QMediaPlayer for audio playback
- Volume, seek, play/pause/stop controls

### categorizer.py
- `get_suggestions(track)` - Return 5 suggestions
- Uses library for artist/category lookups

## Running Tests

```bash
# TBD - tests to be added
```

## Known Limitations

- No real-time metadata change detection (manual refresh only)
- Playback: basic controls (no equalizer, no playlist)
- Search: simple string matching, no fuzzy search