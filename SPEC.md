# MusicVault - Specification Document

## 1. Project Overview

**Project Name**: MusicVault  
**Type**: Desktop Application (Music File Manager)  
**Core Feature**: Lightweight local music library manager with manual categorization via metadata tags  
**Target Users**: Music collectors who want to organize their music library by adding custom categories to audio files

---

## 2. UI/UX Specification

### 2.1 Layout Structure

**Window Model**: Single main window with optional dialogs for settings/folder selection

**Main Layout (3-panel design)**:
```
┌─────────────────────────────────────────────────────────────────┐
│  Menu Bar: File | View | Help                                   │
├──────────────┬─────────────────────────┬───────────────────────┤
│              │                         │                       │
│   FOLDER     │      TRACK LIST         │    TRACK DETAILS      │
│   PANEL      │      (main view)        │    & CATEGORIES       │
│              │                         │                       │
│  [Tree view] │  [Table with columns]   │  [Album art + info]   │
│              │                         │  [Categories box]     │
│              │                         │  [Suggestions]        │
│              │                         │                       │
├──────────────┴─────────────────────────┴───────────────────────┤
│  PLAYBACK BAR: [<<][>>][Play/Pause] ───●────── [Vol] 00:00/00:00│
└─────────────────────────────────────────────────────────────────┘
```

**Panel Sizes**:
- Folder Panel: 200px (resizable, min 150px)
- Track List: flexible (fill remaining space)
- Details Panel: 280px (resizable, min 220px)

**UI Mode Toggle**: User can switch between Tree View (folder-based) and Flat List (all tracks)

### 2.2 Visual Design

**Color Palette**:
- Primary Background: `#0A0A0A` (black)
- Secondary Background: `#1A1A1A` (dark gray)
- Accent Color: `#808080` (gray)
- Accent Hover: `#A0A0A0` (lighter gray)
- Text Primary: `#E5E5E5` (off-white)
- Text Secondary: `#999999` (medium gray)
- Border Color: `#333333` (dark gray)

**Typography**:
- Font Family: Segoe UI (Windows), SF Pro (Mac), fallback: sans-serif
- Headings: 14px bold
- Body: 12px regular
- Small/Labels: 10px regular

**Spacing System**:
- Base unit: 4px
- Small padding: 8px
- Medium padding: 12px
- Large padding: 16px
- Panel gaps: 4px

**Visual Effects**:
- Panel separators: 1px solid border
- Selected row: accent background with 20% opacity
- Hover states: background lightens by 5%
- Focus ring: 2px accent border

### 2.3 Components

**Folder Panel**:
- Tree view of added folders
- Checkbox to enable/disable folder
- Right-click: Remove folder
- States: Normal, Selected, Disabled (unchecked)

**Track List Table**:
- Columns: #, Title, Artist, Album, Duration, Categories
- Sortable columns (click header)
- Multi-select support (Ctrl+Click, Shift+Click)
- States: Normal, Hover, Selected, Playing (highlighted)

**Track Details Panel**:
- Album art (200x200 max, placeholder if none)
- Title (bold, 14px)
- Artist - Album (secondary text)
- Duration
- Categories display (as pills/tags)
- Category input field with "Add" button

**Category Suggestions Box**:
- 5 suggestion buttons max
- Click to add category to current track
- Hover tooltip showing source (same artist / similar category)

**Playback Bar**:
- Previous/Next buttons
- Play/Pause button (toggles)
- Seek slider with time display
- Volume slider with icon
- Current track info (title - artist)

---

## 3. Functional Specification

### 3.1 Core Features

#### 3.1.1 Library Management
- **Add Folders**: File > Add Folder (multi-select dialog)
- **Remove Folders**: Right-click folder > Remove
- **Folder Persistence**: Folders stored in JSON config file (`~/.monovault/config.json`)
- **Scan Folders**: Recursive scan for MP3, FLAC files
- **Metadata Reading**: Extract ID3 (MP3), Vorbis (FLAC) tags
- **Album Art**: FLAC uses `audio.pictures`, MP3 uses APIC frame (all formats working)
- **Storage**: In-memory for performance (files remain source of truth)
- **Refresh**: Menu option to rescan all folders

#### 3.1.2 Audio Playback
- **Play**: Double-click track or press Play button
- **Pause**: Click Pause button or spacebar
- **Stop**: Click Stop button or press Escape
- **Next/Previous**: Skip to next/previous in current view
- **Seek**: Drag slider or click on progress bar
- **Volume**: Drag slider (0-100%)
- **Mute**: Click volume icon to toggle mute

#### 3.1.3 Categorization
- **View Categories**: Displayed in Track List column and Details panel
- **Add Category**: Type in input field, press Enter or click Add
- **Remove Category**: Click X on category pill
- **Category Storage**: Write to COMMENT/COMM metadata tag
- **Format**: Each category = one word, space-separated for multiple

#### 3.1.4 Category Suggestions
- **Algorithm**:
  1. Get all categories from tracks with same artist
  2. Get all categories from tracks sharing any category with current track
  3. Deduplicate and exclude existing categories
  4. Limit to 5 suggestions
- **Display**: Clickable buttons in Details panel

#### 3.1.5 Bulk Operations
- **Multi-select**: Ctrl+Click for individual, Shift+Click for range
- **Clear Categories**: Select tracks > Right-click > Clear Categories
- **Confirmation**: Dialog asking to confirm bulk action

#### 3.1.6 Search
- **Scope**: Categories, Title, Artist, Album
- **Behavior**: Filter track list as user types
- **Debounce**: 1.5 second delay before applying filter
- **Clear**: Clear button or Escape to reset

### 3.2 User Interactions and Flows

**First Launch Flow**:
1. Empty library shown
2. User clicks File > Add Folder
3. Select folder(s) in dialog
4. App scans and populates library
5. Tracks displayed in list

**Playback Flow**:
1. Select track in list
2. Click Play or double-click
3. Track loads and plays
4. Playback bar shows progress
5. Can seek, adjust volume, pause

**Categorization Flow**:
1. Select track in list
2. Details panel shows current categories
3. Type new category in input
4. Press Enter or click Add
5. Category saved to file metadata
6. UI updates with new category

**Suggestion Flow**:
1. Select track
2. Suggestions populate based on algorithm
3. Click suggestion button
4. Category added to track

### 3.3 Data Flow & Processing

**Modules**:

1. **LibraryManager**
   - `add_folder(path: str)` - Add folder to watch list
   - `remove_folder(path: str)` - Remove folder
   - `scan_library()` - Rescan all folders
   - `get_tracks(filters: dict)` - Get filtered tracks

2. **MetadataReader**
   - `read_metadata(file_path: str)` - Read audio file metadata
   - `write_metadata(file_path: str, data: dict)` - Write metadata
   - `extract_album_art(file_path: str)` - Extract embedded art

3. **PlaybackEngine**
   - `load(track: Track)` - Load track for playback
   - `play()`, `pause()`, `stop()` - Playback controls
   - `seek(position: float)` - Seek to position
   - `set_volume(level: int)` - Set volume 0-100

4. **CategoryEngine**
   - `get_suggestions(track: Track)` - Get 5 category suggestions
   - `add_category(track: Track, category: str)` - Add category
   - `remove_category(track: Track, category: str)` - Remove category
   - `clear_categories(track: Track)` - Clear all categories

5. **SearchEngine**
   - `search(query: str)` - Search and return filtered tracks

6. **LibraryManager**
   - `add_folder(path: str)` - Add folder to watch list
   - `remove_folder(path: str)` - Remove folder
   - `scan_library()` - Rescan all folders
   - `get_tracks(filters: dict)` - Get filtered tracks

### 3.4 Edge Cases

- **Empty folders**: Show "No audio files found" message
- **Corrupt audio files**: Skip and log error, continue scanning
- **Missing metadata**: Show "Unknown" for missing fields
- **No album art**: Show placeholder image
- **Write permission denied**: Show error dialog, don't crash
- **Very long categories**: Truncate display, show full on hover
- **Unicode in categories**: Support fully (UTF-8)
- **Large library (10k+ files)**: Progress indicator during scan

---

## 4. Acceptance Criteria

### 4.1 Success Conditions

1. **Library Scanning**
   - [ ] Can add multiple folders
   - [ ] Scans recursively for MP3, FLAC
   - [ ] Displays all tracks in list
   - [ ] Shows progress for large scans

2. **Playback**
   - [ ] Plays selected track
   - [ ] Pause/resume works
   - [ ] Stop works
   - [ ] Seek works
   - [ ] Volume control works
   - [ ] Next/Previous works

3. **Categorization**
   - [ ] Can add category to track
   - [ ] Category saved to file COMMENT tag
   - [ ] Can remove category
   - [ ] Categories display in list and details

4. **Suggestions**
   - [ ] Shows up to 5 suggestions
   - [ ] Suggestions from same artist
   - [ ] Suggestions from similar categories
   - [ ] Click adds category to track

5. **Bulk Operations**
   - [ ] Can select multiple tracks
   - [ ] Can clear categories from selection

6. **Search**
   - [ ] Search filters by title, artist, album, category
   - [ ] Works with debounce delay

7. **Packaging**
   - [ ] Builds to single .exe on Windows
   - [ ] App launches without dependencies

### 4.2 Visual Checkpoints

1. Dark theme with purple accent applied
2. Three-panel layout visible
3. Album art displays when available
4. Categories shown as colored pills
5. Playback bar functional at bottom
6. Smooth scrolling in track list