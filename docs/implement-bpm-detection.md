---
status: complete
phase: 5
updated: 2026-05-02
---

# Implementation Plan: BPM Detection

## Goal
Add per-folder-cached aubio-based BPM detection to the track table with a `~BPM` column that populates in the background after scanning.

## Context & Decisions

| Decision | Rationale | Source |
|----------|-----------|--------|
| Use `aubio` | C extension — ~5–10× faster than librosa, no ffmpeg dependency for FLAC/WAV, lighter install | User requirement |
| Separate `bpm_cache.json` per folder | Keeps BPM cache decoupled from `library.json` (date-added); same `.monovault/` sidecar pattern | `library_store.py` convention |
| `bpm: float \| None` on Track | Optional field — None until analyzed; avoids blocking scan on first launch | Model evolution |
| Display as integer, store as float | DJs read whole numbers (128, not 128.3); float stored for precision | UX convention |
| `~BPM` column header | Explicitly signals estimated value to user | User requirement |
| `QThread` worker (not `QRunnable`) | Batch sequential analysis with per-track progress signal; matches `ScannerWorker` pattern | `scanner_worker.py` pattern |
| Hydrate cache before starting worker | Tracks with cached BPM show instantly; worker only runs on uncached tracks | Performance |
| Remove from BpmStore on permanent delete only | Soft-deleted tracks keep their cache entry so BPM is preserved on restore; purge cleans up dead keys | UX / trash lifecycle |
| Sanity bounds: 40–250 BPM | Outside this range aubio result is noise; return `None` instead | Audio analysis heuristic |

---

## Phase 1: Model + Core [PENDING]

- [ ] **1.1 Add `aubio` to `pyproject.toml` dependencies** ← CURRENT
- [ ] 1.2 Add `bpm: float | None = None` field to `Track` dataclass (`src/models/track.py`)
- [ ] 1.3 Create `src/core/bpm_store.py` — per-folder JSON cache at `.monovault/bpm_cache.json`
  - Keys: relative POSIX paths (same as `LibraryStore._to_key`)
  - Values: `float | None` (None means "analyzed but no result"; missing key means "not yet analyzed")
  - Public API: `get(file_path) -> float | None | _MISSING`, `set(file_path, bpm)`, `save()`
- [ ] 1.4 Create `src/core/bpm_analyzer.py` — single `analyze_bpm(file_path: str) -> float | None`
  - Uses `aubio.source` + `aubio.tempo("default", win_size, hop_size, sample_rate)`
  - Reads up to 60 s of audio (early exit for long files)
  - Returns `round(bpm, 1)` or `None` if `< 4` beats detected or BPM outside 40–250

## Phase 2: Background Worker [PENDING]

- [ ] 2.1 Create `src/ui/workers/bpm_worker.py`
  - `BpmWorkerSignals(QObject)`: `track_analyzed = pyqtSignal(int, object)` (track_id, `float | None`), `finished = pyqtSignal()`, `progress = pyqtSignal(int, int)` (done, total)
  - `BpmWorker(QThread)`: takes `tracks: list[Track]` + `bpm_store: BpmStore`; checks cache first, calls `analyze_bpm` only on cache misses; supports `cancel()` via `_cancelled` flag

## Phase 3: Track Table `~BPM` Column [PENDING]

- [ ] 3.1 Extend `TrackTableColumn` in `src/ui/track_table.py`:
  - Insert `BPM = 7` before `COUNT`; shift `COUNT` to `8`
  - Add `"~BPM"` to `_COLUMN_LABELS`
  - Add `ResizeToContents` to `_COLUMN_RESIZE_MODES`
  - Add padding entry to `_PADDING_MAP`
- [ ] 3.2 Render BPM in `_set_row`: `_NumericItem(str(int(round(track.bpm))))` if not None, else empty; right-aligned
- [ ] 3.3 Add `update_bpm(self, track_id: int, bpm: float | None) -> bool` to `TrackTableManager` — updates only the BPM cell without re-rendering the whole row

## Phase 4: MainWindow Integration [PENDING]

- [ ] 4.1 Instantiate `BpmStore` per scanned folder alongside `LibraryStore` in `main_window.py`
- [ ] 4.2 After scan completes (`_on_scan_complete`): read BpmStore for each track, set `track.bpm`, call `table_manager.update_track(track)` to populate cached values immediately
- [ ] 4.3 Start `BpmWorker` for tracks where BpmStore has no entry; connect `track_analyzed` → update `library._tracks[id].bpm`, call `table_manager.update_bpm(track_id, bpm)`, save to BpmStore
- [ ] 4.4 Reuse `scan_progress_bar` for BPM analysis progress (hide when worker finishes); cancel existing worker before starting a new scan
- [ ] 4.5 Hook into `delete_controller.py` purge path: call `bpm_store.remove(file_path)` on permanent delete only — soft delete leaves cache intact so restore preserves BPM

## Phase 5: Tests [PENDING]

- [ ] 5.1 `tests/core/test_bpm_store.py` — get/set/cache-miss/save round-trip; read-only filesystem graceful skip
- [ ] 5.2 `tests/core/test_bpm_analyzer.py` — mock `aubio.source` + `aubio.tempo`; assert returns None for < 4 beats; assert sanity bounds
- [ ] 5.3 `tests/ui/test_track_table_bpm.py` — column count is 9; BPM cell renders integer; None renders empty; `update_bpm` patches only BPM cell

## Notes

- 2026-05-02: Plan created. aubio reads most formats natively; MP3 support depends on system libav/ffmpeg but FLAC/WAV work without it — acceptable for now.
- BpmStore treats a missing key as "not analyzed" and an explicit `None` value as "analyzed but undetectable" — this avoids re-analyzing silence/corrupt files on every launch.
- `scan_progress_bar` reuse: show with `setFormat("Analyzing BPM… %p%")` during worker; hide on `finished`. If a rescan starts, call `bpm_worker.cancel()` and wait for `finished` before starting new scan.
