# MusicVault - Music File Management Application

## Requirements Summary

### Technology Stack
- **Language**: Python 3.10+
- **Framework**: PyQt6 (rich UI capabilities)
- **Packaging**: PyInstaller (single .exe on Windows)
- **Storage**: In-memory (no database), with mtime cache for change detection
- **UI Language**: English

### Supported Platforms
- Windows (.exe via PyInstaller)
- MacOS (via PyInstaller or similar)
- Linux (direct execution)

### Core Features

#### 1. Library Management
- Scan 1 or more folders recursively
- Support audio formats: MP3, FLAC
- In-memory storage for performance (2000+ tracks ~700KB)
- Album art extraction and display
- Track addition dates stored in `~/.monovault/library.json`
- Folder persistence in `~/.monovault/config.json`

#### 2. Audio Playback
- Play/pause/stop
- Volume control
- Seek functionality
- Basic track info (name, artist, length)
- Previous/next track navigation

#### 3. Categorization System
- Categories stored in metadata tag (COMM for MP3, COMMENT for FLAC)
- Each word in tag = one category
- Multiple categories per file supported
- Case-insensitive (normalized to lowercase)

#### 4. Category Suggestions
- Max 5 suggestions per track
- Suggestion sources:
  - Categories from same artist
  - Categories from tracks with similar categories

#### 5. Quick Actions
- Multi-select tracks
- Clear categories from selected tracks
- Manual refresh option

#### 6. Search
- Search by: categories, track name, album, artist
- Debounced search (1.5 second delay without enter)

#### 7. UI Layout
- Three-panel layout (folder tree | track table | details)
- Album art display
- Dark theme

## Out of Scope (for now)
- Real-time metadata change detection (manual refresh only)
- Playlists
- Export to CSV