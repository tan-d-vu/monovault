---
status: not-started
phase: 1
updated: 2026-04-03
---

# Implementation Plan: Flash-Drive / Portable Volume Support

## Goal

Make MusicVault portable-friendly by storing per-folder metadata sidecars, using relative paths internally, and re-associating volumes at startup when mount points change.

## Context & Decisions

| Decision | Rationale |
|----------|-----------|
| Per-folder `.monovault/` dir created automatically | User confirmed no prompt needed; silent creation |
| Categories stay in file tags only (mutagen) | No fallback JSON for categories; tags are the source of truth |
| Per-folder sidecar + volume_id + global mapping | Combines portability (sidecar) with re-association (volume_id) |
| No migration from old global `library.json` | User will test clean; old approach treated as non-existent |
| No hot-plug detection | Startup-only re-association is sufficient |
| Read-only folder handling | If `.monovault` creation fails, show non-modal warning, continue with tags only |
| Relative POSIX keys in per-folder `library.json` | Ensures path entries survive mount-point changes |

---

## Phase 1: Core Infrastructure [PENDING]

### 1.1 New module `src/core/volume_utils.py`

Create a new module for volume identification and discovery.

**Functions:**

```python
def generate_volume_id() -> str
```
- Returns `uuid.uuid4().hex`

```python
def read_volume_id(folder: Path) -> Optional[str]
```
- Reads `<folder>/.monovault/volume_id` text file
- Returns `None` if file missing or unreadable

```python
def write_volume_id(folder: Path) -> str
```
- Creates `<folder>/.monovault/` dir if needed
- Generates new volume_id via `generate_volume_id()`
- Writes to `<folder>/.monovault/volume_id`
- Returns the id
- Raises `OSError` on write failure (caller handles)

```python
def ensure_volume_id(folder: Path) -> Optional[str]
```
- Reads existing volume_id; if missing, writes a new one
- Wraps `write_volume_id` in try/except for read-only filesystems
- Returns `None` on failure (logged as warning)

```python
def get_mount_search_paths() -> list[Path]
```
- Linux: `/run/media/<user>/*, /media/<user>/*, /mnt/*, /media/*`
- macOS: `/Volumes/*`
- Windows: drive letters `A:\` through `Z:\` (that exist)
- Uses `platform.system()` + `os.getlogin()` / `getpass.getuser()`

```python
def find_volume_by_id(volume_id: str) -> Optional[Path]
```
- Iterates `get_mount_search_paths()`
- For each mount root, checks `<mount>/.monovault/volume_id`
- Returns the first path whose volume_id matches, or `None`

**File references (context for implementation):**
- `src/core/config.py:13-18` — existing platform detection pattern to follow

---

### 1.2 Modify `src/core/library_store.py` — per-folder mode

Change `LibraryStore` to support a `base_dir` parameter for folder-scoped storage with relative POSIX keys.

**Current state** (`library_store.py:7-13`):
- Constructor takes no args, always writes to `~/.monovault/library.json`
- Keys are absolute file paths

**Changes:**

```python
class LibraryStore:
    def __init__(self, base_dir: Optional[Path] = None):
```

- **If `base_dir` is provided (per-folder mode):**
  - Store file: `<base_dir>/.monovault/library.json`
  - Create `.monovault/` dir on first write (not in constructor)
  - Keys: relative POSIX paths from `base_dir` (e.g., `"subdir/track.mp3"`)
  - `record_if_new(file_path)` converts absolute path to relative POSIX before keying
  - `get(file_path)` converts absolute path to relative POSIX for lookup

- **If `base_dir` is `None` (legacy/global mode — kept for backward compat but unused in new code):**
  - Existing behavior: `~/.monovault/library.json` with absolute keys

**New helper method:**
```python
def _to_key(self, file_path: str) -> str
```
- If `self._base_dir` is set: `PurePosixPath(Path(file_path).relative_to(self._base_dir))`
- Otherwise: return `file_path` as-is

**Save behavior change:**
- In per-folder mode, create `.monovault/` dir lazily on first `save()` call
- If dir creation fails (read-only), log warning and skip save (don't crash)

---

### 1.3 Modify `src/core/config.py` — add volumes mapping

Extend global config JSON to track volume associations.

**Current JSON format** (`config.py:34`):
```json
{"folders": ["/path/to/music1"]}
```

**New JSON format:**
```json
{
  "folders": ["/path/to/music1"],
  "volumes": {
    "a1b2c3d4...": {
      "paths": ["/run/media/user/USBDRIVE/music"],
      "created_at": "2026-04-03T12:00:00"
    }
  }
}
```

**New fields on `Config`:**
```python
self.volumes: dict[str, dict] = {}   # volume_id -> {"paths": [...], "created_at": "..."}
```

**New methods:**

```python
def register_volume(self, volume_id: str, folder_path: str) -> None
```
- Adds or updates the volume entry:
  - If volume_id already in `self.volumes`, append `folder_path` to `paths` if not present
  - Otherwise create new entry with `paths: [folder_path]` and `created_at: now()`
- Calls `self.save()`

```python
def get_volume_paths(self, volume_id: str) -> list[str]
```
- Returns the `paths` list for a volume_id, or `[]`

```python
def update_volume_path(self, volume_id: str, old_path: str, new_path: str) -> None
```
- Replaces `old_path` with `new_path` in the volume's paths list
- Also replaces `old_path` with `new_path` in `self.folders`
- Calls `self.save()`

**Modify `_load()`** (`config.py:20-29`):
- Also read `data.get("volumes", {})`

**Modify `save()`** (`config.py:31-34`):
- Also write `"volumes": self.volumes`

---

## Phase 2: Scanner & Integration [PENDING]

### 2.1 Modify `src/core/scanner.py` — per-folder LibraryStore creation

**Current state** (`scanner.py:10-13`):
- Constructor takes optional `LibraryStore` passed from outside

**Changes:**

Remove the `library_store` constructor parameter. Instead, `scan_folder` creates a per-folder `LibraryStore` internally.

```python
class Scanner:
    def __init__(self):
        self.progress_callback: Optional[callable] = None
```

**Modify `scan_folder()`** (`scanner.py:15-31`):
```python
def scan_folder(self, folder_path: str) -> list[Track]:
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return []

    store = LibraryStore(base_dir=folder)
    audio_files = self._find_audio_files(folder)
    tracks = []

    for i, file_path in enumerate(audio_files):
        track = self.process_file(file_path, folder_path, store)
        if track:
            tracks.append(track)
        if self.progress_callback:
            self.progress_callback(i + 1, len(audio_files))

    store.save()
    return tracks
```

**Modify `process_file()`** (`scanner.py:42`):
- Add `store` parameter: `def process_file(self, file_path: str, folder_path: str, store: Optional[LibraryStore] = None) -> Optional[Track]`
- Use `store.record_if_new(file_path)` instead of `self._store.record_if_new(file_path)`

---

### 2.2 Modify `src/ui/main_window.py` — volume lifecycle

**Current state** (`main_window.py:44-49`):
```python
self.library = LibraryManager()
self.library_store = LibraryStore()
self.scanner = Scanner(library_store=self.library_store)
```

**Changes to `__init__`:**
```python
self.library = LibraryManager()
self.scanner = Scanner()       # no more global LibraryStore
```
- Remove `self.library_store` entirely

**Changes to `_load_library()`** (`main_window.py:179-190`):

After populating the folder tree, add volume re-association logic:

```python
def _load_library(self):
    self._reassociate_volumes()        # NEW — must run before scanning
    folders = self.library.get_folders()
    populate_folder_tree(self.folder_tree_widget, folders)
    # ... rest unchanged
```

**New method `_reassociate_volumes()`:**

```python
def _reassociate_volumes(self) -> None:
    """Check each configured folder. If missing, attempt re-association via volume_id."""
    config = self.library.config
    for folder in list(config.folders):
        if Path(folder).exists():
            continue

        # Folder is missing — find its volume_id from config
        for vol_id, vol_info in config.volumes.items():
            if folder in vol_info.get("paths", []):
                new_path = find_volume_by_id(vol_id)
                if new_path:
                    new_folder = str(new_path)
                    config.update_volume_path(vol_id, folder, new_folder)
                    break
        else:
            # Could not re-associate; leave as-is (will skip during scan)
            pass

    self.library.folders = config.get_folders()
```

**Changes to `_add_folder()`** (`main_window.py:199-204`):

After adding a folder, ensure volume_id is created and registered:

```python
def _add_folder(self):
    folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
    if folder:
        self.library.add_folder(folder)
        self._register_volume(folder)       # NEW
        self._load_library()
```

**New method `_register_volume()`:**
```python
def _register_volume(self, folder: str) -> None:
    """Create volume_id sidecar and register in global config."""
    vol_id = ensure_volume_id(Path(folder))
    if vol_id:
        self.library.config.register_volume(vol_id, folder)
```

**Changes to `_scan_folder()`** (`main_window.py:206-210`):

No changes needed — `Scanner` now handles `LibraryStore` creation internally.

But remove the reference to `self.library_store` that no longer exists.

**Show warning for read-only folders:**

In `_add_folder`, if `ensure_volume_id` returns `None`, show a non-modal warning:

```python
if vol_id is None:
    QMessageBox.warning(
        self,
        "Read-Only Folder",
        f"Cannot create metadata in '{folder}'.\n"
        "Categories will still be saved in file tags,\n"
        "but date-added tracking won't be available for this folder.",
    )
```

---

## Phase 3: Bug Fixes [PENDING]

### 3.1 Fix `Track.location` property

**Current code** (`track.py:25-33`):
```python
@property
def location(self) -> str:
    if not self.folder_path:
        return ""
    folder = Path(self.folder_path)
    try:
        relative = Path(self.file_path).relative_to(folder.parent)  # BUG
        return str(relative.parent)
    except ValueError:
        return ""
```

**Fix:** Change `folder.parent` to `folder`:
```python
relative = Path(self.file_path).relative_to(folder)
```

The current code anchors at the parent of the library folder rather than the library folder itself, producing incorrect relative paths.

---

## Phase 4: Tests [PENDING]

### 4.1 `tests/core/test_volume_utils.py`

Test all functions in `volume_utils.py`:

| Test | Description |
|------|-------------|
| `test_generate_volume_id_is_hex_uuid` | 32-char hex string |
| `test_write_and_read_volume_id` | Round-trip write then read |
| `test_read_volume_id_missing` | Returns `None` for non-existent dir |
| `test_ensure_volume_id_creates_new` | Creates when missing |
| `test_ensure_volume_id_reads_existing` | Returns existing without overwriting |
| `test_ensure_volume_id_readonly` | Returns `None` on read-only dir (no crash) |
| `test_get_mount_search_paths_linux` | Mocked platform, check expected paths |
| `test_find_volume_by_id_found` | Creates temp dirs with volume_id, verifies match |
| `test_find_volume_by_id_not_found` | Returns `None` when no match |

### 4.2 `tests/core/test_library_store_local.py`

Test per-folder `LibraryStore` behavior:

| Test | Description |
|------|-------------|
| `test_per_folder_store_creates_dotdir_on_save` | `.monovault/` created lazily |
| `test_per_folder_store_uses_relative_keys` | Keys are POSIX-relative, not absolute |
| `test_record_if_new_relative_key` | `record_if_new` with absolute path stores relative key |
| `test_get_with_absolute_path` | `get()` resolves absolute → relative lookup |
| `test_save_readonly_dir_no_crash` | Logs warning, doesn't raise |
| `test_round_trip_save_load` | Save data, create new `LibraryStore` on same dir, data persists |
| `test_global_mode_still_works` | `LibraryStore()` with no args uses `~/.monovault` (backward compat) |

### 4.3 `tests/core/test_config_volumes.py`

Test volume-related `Config` methods:

| Test | Description |
|------|-------------|
| `test_register_volume_new` | New volume_id creates entry with path and timestamp |
| `test_register_volume_existing_adds_path` | Second path appended, not duplicated |
| `test_get_volume_paths` | Returns correct paths list |
| `test_get_volume_paths_unknown` | Returns `[]` for unknown volume_id |
| `test_update_volume_path` | Replaces old path in volumes and in folders |
| `test_save_load_round_trip_with_volumes` | Volumes survive save/load cycle |

### 4.4 `tests/core/test_scanner_per_folder.py`

Test that Scanner creates per-folder stores:

| Test | Description |
|------|-------------|
| `test_scan_creates_sidecar` | After scanning, `<folder>/.monovault/library.json` exists |
| `test_scan_sidecar_has_relative_keys` | JSON keys are relative POSIX paths |
| `test_scan_no_store_arg` | Scanner() takes no library_store arg |

### 4.5 `tests/ui/test_volume_reassociation.py`

Test re-association logic (unit-level, mocked filesystem):

| Test | Description |
|------|-------------|
| `test_reassociate_finds_moved_volume` | Mock `find_volume_by_id` returns new path; config updated |
| `test_reassociate_skips_existing_folders` | Existing folders untouched |
| `test_reassociate_no_match_leaves_config` | Missing volume with no match stays in config |
| `test_register_volume_on_add_folder` | Adding folder triggers `ensure_volume_id` + `register_volume` |

### 4.6 `tests/models/test_track_location.py`

| Test | Description |
|------|-------------|
| `test_location_uses_folder_not_parent` | Verify fix for `folder.parent` bug |
| `test_location_empty_folder_path` | Returns `""` |
| `test_location_file_not_under_folder` | Returns `""` |

---

## Phase 5: Cleanup [PENDING]

### 5.1 Remove global `library.json` usage

- Delete `~/.monovault/library.json` handling from any remaining code paths
- Ensure `LibraryStore()` (no-arg) is not called anywhere in production code
- Keep backward-compat constructor for tests only if needed

### 5.2 Run full test suite and lint

```bash
pytest --cov=src --cov-report=term-missing
ruff check src/ tests/
ruff format src/ tests/
```

Fix any failures or style issues.

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `src/core/volume_utils.py` | **NEW** | Volume ID generation, read/write, mount discovery |
| `src/core/library_store.py` | MODIFY | Add `base_dir` param, relative POSIX keys, lazy dir creation |
| `src/core/config.py` | MODIFY | Add `volumes` dict, `register_volume`, `update_volume_path` |
| `src/core/scanner.py` | MODIFY | Remove `library_store` param, create per-folder store in `scan_folder` |
| `src/ui/main_window.py` | MODIFY | Remove global `LibraryStore`, add `_reassociate_volumes`, `_register_volume` |
| `src/models/track.py` | MODIFY | Fix `location` property bug (`folder.parent` → `folder`) |
| `tests/core/test_volume_utils.py` | **NEW** | Volume utils tests |
| `tests/core/test_library_store_local.py` | **NEW** | Per-folder LibraryStore tests |
| `tests/core/test_config_volumes.py` | **NEW** | Config volumes tests |
| `tests/core/test_scanner_per_folder.py` | **NEW** | Scanner per-folder store tests |
| `tests/ui/test_volume_reassociation.py` | **NEW** | Re-association logic tests |
| `tests/models/test_track_location.py` | **NEW** | Track.location bug fix tests |

## Notes

- 2026-04-03: No migration needed per user decision — clean-slate approach.
- 2026-04-03: Hot-plug explicitly declined. Re-association runs at startup only.
- 2026-04-03: Categories remain in file tags (mutagen). The per-folder sidecar only stores `date_added` metadata.
