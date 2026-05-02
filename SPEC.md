# MonoVault — Specification Document

## 1. Project Overview

**Project Name**: MonoVault
**Type**: Desktop Application (Music File Manager)
**Core Feature**: Lightweight local music library manager with manual categorization via metadata tags
**Target Users**: Music collectors who want to organize their library by adding custom categories directly to audio file tags

---

## 2. UI/UX Specification

### 2.1 Layout Structure

**Window Model**: Single main window (`MainWindow`) with optional dialogs for settings/folder selection and trash management.

**Main Layout**:
```
┌─────────────────────────────────────────────────────────────────────┐
│  [Library] [Duplicates] [Categories]  │  TRACK DETAILS & CATEGORIES │
│ ─────────────────────────────────     │                             │
│  FOLDER PANEL  │  TRACK TABLE         │  [Album art]                │
│  [Tree view]   │  [Sortable table]    │  Title / Artist / Album     │
│                │                      │  Date Added                 │
│                │                      │  [Category pills]           │
│                │                      │  [Category input]           │
│                │                      │  [Suggestion buttons]       │
├────────────────┴──────────────────────┴─────────────────────────────┤
│  [Scan progress bar — hidden when idle]                             │
├─────────────────────────────────────────────────────────────────────┤
│  PLAYBACK BAR: [Prev][Play/Pause][Next] ──●──── 00:00/00:00  [Vol] │
└─────────────────────────────────────────────────────────────────────┘
```

**Panel Sizes**:
- Folder Panel: 200px default (resizable)
- Track Table: fills remaining space in Library tab
- Details Panel: 280px (non-collapsible)

### 2.2 Visual Design

**Color Palette** (from `styles.py`):
- Primary Background: `#0A0A0A`
- Secondary Background: `#1A1A1A`
- Accent: `#808080`
- Text Primary: `#E5E5E5`
- Text Secondary: `#999999`
- Border: `#333333`

**Typography**:
- Font: Segoe UI (Windows), SF Pro (macOS), sans-serif fallback
- Base size: 12px; headings: 14px bold; labels: 10px

### 2.3 Components

**Folder Panel**:
- Tree view of added folders with nested subfolders
- Tri-state checkboxes for folder/subfolder filtering (Checked / Unchecked / PartiallyChecked)
- Right-click: Show Folder (opens in OS file explorer) / Remove Folder

**Track Table** (Library tab):
- Columns: #, Title, Artist, Album, Duration, Categories, Date Added
- Sortable by any column (click header)
- Multi-select: Ctrl+Click, Shift+Click
- Right-click: Clear Categories / Move to Trash
- Playing track highlighted

**Duplicates Tab**:
- "Find Duplicates" button triggers union-find detection across all library tracks
- Groups listed with columns: Group, Title, Artist, Album, Duration, Comments, Filename, Location
- Right-click: Move to Trash (reuses same trash flow as Library tab)
- Invalidated on library refresh; refreshed after track deletion

**Categories Tab**:
- Summary: total unique categories, untagged track count
- Category list table: Name, Track Count (sortable)
- Orphan filter (categories used by ≤ N tracks)
- Text filter input
- Right-click on single category: Filter to Library / Rename / Delete
- Right-click on multiple categories: Merge / Delete
- "Filter to Library" switches to Library tab with results applied
- Rename/merge/delete apply to all tracks across entire library

**Track Details Panel**:
- Album art (200×200, placeholder if none)
- Title (bold), Artist — Album, Date Added
- Category pills (each with × button to remove)
- Category input field (single word, Enter to add; multi-word rejected with hint)
- Suggestion buttons (up to 5)

**Playback Bar**:
- Previous / Play-Pause / Next buttons
- Seek slider with time display (`MM:SS / MM:SS`)
- Volume slider
- Now-playing label (Title — Artist)

**Trash Dialog** (`Ctrl+Shift+T`):
- Table: Title, Artist, Album, Duration, Categories, Original Path, Deleted At
- Multi-select: Restore / Delete Permanently
- Empty Trash button (purges all entries across all folders)
- Entries from unwatched folders are shown but Restore is disabled

**Toast Notifications**: Non-modal, auto-dismissing overlay for write failures, trash operations, restore results.

**Scan Progress Bar**: Shows `Scanning N/M — filename` during background scan; Cancel button.

---

## 3. Functional Specification

### 3.1 Library Management

- **Add Folder** (`Ctrl+O`): File dialog selects folder; path is canonicalized (resolves symlinks). Requires write access. Creates volume ID sidecar and registers in config.
- **Remove Folder**: Right-click in folder tree → Remove. Removes all tracks for that folder from in-memory library.
- **Folder Persistence**: `~/.monovault/config.json` stores folder list.
- **Scan**: Background `QThread` via `ScannerWorker`. Recursive scan for MP3/FLAC. Progress reported per file. Cancellable. New tracks are added to library folder-by-folder as they arrive.
- **Refresh** (`Ctrl+R`): Clears library, re-scans all folders. Shows "Refresh Complete" dialog when done.
- **Folder Filter**: Checking/unchecking folder tree items filters the track table. Subfolders get individual checkboxes; parent tri-state reflects child aggregate.

### 3.2 Audio Playback

- **Play**: Double-click track or `Enter`; also `Space` toggles playback for selected track
- **Pause/Resume**: Play/Pause button or `Space`
- **Next/Previous**: Buttons in playback bar; navigates within current track list view
- **Seek**: Drag position slider
- **Volume**: Volume slider (0–100)
- **Now Playing**: Label shows `Title — Artist` of currently loaded track

### 3.3 Categorization

- **Add Category**: Type in input field, press Enter. Single words only (space in input shows inline hint, does not submit).
- **Remove Category**: Click × on category pill
- **Bulk Clear**: Right-click selected tracks → Clear Categories (confirmation dialog)
- **Category Storage**: Written to COMMENT/COMM metadata tag as space-separated string
- **Async Writes**: `MetadataWriteWorker` on `QThreadPool(maxThreadCount=1)`. On failure: reverts in-memory state from disk and shows toast.

### 3.4 Category Suggestions

Algorithm (up to 5 results, deduplicated, excluding existing categories):
1. Categories from other tracks by the same artist (`ArtistCategorySource`)
2. Categories from tracks sharing any existing category (`SimilarCategoryCategorySource`)

### 3.5 Category Management (Categories Tab)

- **Rename**: Single category → new name. Applied to all tracks in library.
- **Merge**: Select multiple categories → merge into one target. Applied to all tracks.
- **Delete**: Remove one or more categories from all tracks entirely.
- **Orphan Detection**: `CategoryStats.orphans(threshold)` returns categories used by ≤ threshold tracks.
- **Filter to Library**: Clicking a category filters the Library tab's track table to matching tracks. "Untagged" filter shows tracks with no categories.

### 3.6 Duplicate Detection

**Trigger**: "Find Duplicates" button in Duplicates tab.

**Rules** (union-find — any match groups tracks together):
1. Same `artist` + `title` (case-insensitive, trimmed)
2. Same `filename` (case-insensitive)
3. Same `title` + duration within 1.0 second tolerance

Groups with only one track are not reported. Groups are sorted largest-first.

### 3.7 Trash / Delete

- **Move to Trash** (`Delete` key or right-click → Move to Trash): Moves file to `{folder}/.monovault/trash/<uuid>.<ext>`. Writes atomic manifest (`tmp + os.replace`). Removes track from library and date-added store.
- **Restore**: Moves file back to original path. Collision-safe: appends `(restored)` suffix if path already exists. Re-adds track to library with original date_added.
- **Purge**: Permanently deletes trashed file and removes manifest entry.
- **Empty Trash**: Purges all entries across all watched folders.
- Playback is stopped and media source cleared before deleting the currently-playing track (releases file handle on Windows).

### 3.8 Search

- Search box (`Ctrl+F` to focus) filters by Title, Artist, Album, Category
- Case-insensitive substring match
- Debounced (300 ms delay)
- Category filter from Categories tab bypasses text search

### 3.9 Portable Volume Support

- On add-folder: `ensure_volume_id()` writes a UUID to `{folder}/.monovault/volume_id` and registers it in `~/.monovault/config.json`.
- On launch: any configured folder that doesn't exist is looked up by UUID across mounted volumes. If found at a new mount point, the path is updated automatically.

---

## 4. Data Model

### Track
| Field | Type | Source |
|-------|------|--------|
| `id` | `int` | Assigned by LibraryManager |
| `file_path` | `str` | Filesystem |
| `title` | `str` | ID3/Vorbis tag |
| `artist` | `str` | ID3/Vorbis tag |
| `album` | `str` | ID3/Vorbis tag |
| `duration` | `float` | Audio stream (seconds) |
| `categories` | `list[str]` | COMMENT/COMM tag |
| `album_art` | `bytes \| None` | APIC frame / FLAC picture |
| `folder_path` | `str` | Parent watched folder |
| `comments` | `str` | Full COMMENT tag raw value |
| `date_added` | `str` | `{folder}/.monovault/library.json` |

Computed properties: `filename`, `location`, `duration_formatted`, `categories_str`

### Storage Files
| Path | Format | Content |
|------|--------|---------|
| `~/.monovault/config.json` | JSON | `{"folders": [...], "volumes": {...}}` |
| `{folder}/.monovault/library.json` | JSON | `{"relative/path.mp3": "YYYY-MM-DD", ...}` |
| `{folder}/.monovault/trash/manifest.json` | JSON | `{trash_id: {trash_filename, original_relpath, ...}}` |
| `{folder}/.monovault/volume_id` | plaintext | UUID hex string |

---

## 5. Edge Cases

- **Corrupt audio files**: Scanner skips and logs; scan continues
- **Missing metadata**: Shown as "Unknown" in UI
- **No album art**: Placeholder shown in details panel
- **Write permission denied**: Toast notification; in-memory state reverted from disk
- **Multi-word category input**: Inline hint shown; submission blocked
- **Duplicate category**: Silently ignored (case-insensitive deduplication)
- **Read-only folder**: Warning dialog on add; date-added tracking skipped; category writes still attempted via file tags
- **Trash restore collision**: Appends `(restored)` / `(restored 2)` etc. to filename
- **Empty library**: Track table shows empty; scan can still be initiated
- **Scan cancelled**: Partial results retained; progress bar hidden

---

## 6. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+F` | Focus search input |
| `Ctrl+R` | Refresh library |
| `Ctrl+O` | Add folder |
| `Ctrl+Shift+T` | Open Trash dialog |
| `Space` (track table) | Toggle playback |
| `Enter` (track table) | Play selected track |
| `Delete` (track table) | Move selected tracks to Trash |

---

## 7. Known Limitations

- No real-time filesystem change detection (manual refresh only)
- Playback: basic controls only (no equalizer, no queue/playlist)
- Search: simple case-insensitive substring, no fuzzy matching
- Supported formats: MP3, FLAC only
