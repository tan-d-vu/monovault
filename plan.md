# MusicVault - Music File Management Application

## Requirements Summary

### Technology Stack
- **Language**: Python (faster development)
- **Framework**: PyQt (rich UI capabilities)
- **Packaging**: PyInstaller (single .exe on Windows)
- **Storage**: In-memory (no database)
- **UI Language**: English

### Supported Platforms
- Windows (.exe via PyInstaller)
- MacOS (via PyInstaller or similar)

### Core Features

#### 1. Library Management
- Scan 1 or more folders recursively
- Support audio formats: MP3, FLAC
- In-memory storage for performance (2000+ tracks ~700KB)
- Album art extraction and display

#### 2. Audio Playback
- Play/pause/stop
- Volume control
- Seek functionality
- Basic track info (name, artist, length)

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
- Debounced search (~1-2 second delay without enter)

#### 7. UI Layout
- Configurable: tree view or flat list
- 2-3 panel layout (library + playback + details)
- Album art display

## Out of Scope (for now)
- Metadata change detection while app is running
- Playlists
- Export to CSV