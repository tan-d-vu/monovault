# Action Plan — MonoVault Improvements

**Date:** 2026-04-21
**Scope:** Addresses the 15 findings from the code audit, organized into 5 tiers and sequenced into 3 waves for parallel execution.

---

## TL;DR — The parallelization insight

The main bottleneck for parallel work is **`src/ui/main_window.py`** — 7 of the 15 findings touch it. Everything that edits `main_window.py` must be serialized to avoid merge conflicts. Everything else can run concurrently.

```
Wave 1 (parallel, 4 tracks):
  ├─ Track A: main_window.py/scanner.py overhaul   (Tier 1: #1, #2, #3)
  ├─ Track B: Tooling & CI                          (Tier 4: #9, #10, #12)
  ├─ Track C: Docs cleanup                          (Tier 4: #11)
  └─ Track D: UI test scaffold                      (Tier 3: #8 foundation)

Wave 2 (parallel, 3 tracks, after Wave 1 lands):
  ├─ Track E: Error surfacing + input guards       (Tier 1: #4, #5)
  ├─ Track F: Row-index map (surgical perf)         (Tier 2: #6)
  └─ Track G: UX polish                             (Tier 5: #13, #14, #15)

Wave 3 (optional / deferred):
  └─ Track H: QAbstractTableModel migration         (Tier 2: #7)
```

---

## Wave 1 — Parallel tracks

### Track A — Scan-flow overhaul (Tier 1: #1, #2, #3)

**Owner target:** one focused PR, ~1-2 days.
**Files touched:** `src/ui/main_window.py`, `src/core/scanner.py`.
**Why grouped:** all three findings live in the same `_add_folder` / `_refresh_library` / `_scan_folder` / `_load_tracks` call chain. Fixing them in separate PRs would cause rebase pain.

**Steps:**
1. **Fix double-scan (#1)** — Drop the trailing `self._scan_folder(folder)` at `main_window.py:261`. `_load_library()` already scans it.
2. **Fix N-times repopulate (#2)** — In `_refresh_library` (line 269) and `_load_library` (line 189), scan all folders first, then call `_load_tracks()` once. Change `_scan_folder` to NOT call `_load_tracks()` internally — make that the caller's responsibility.
3. **Move scanning off UI thread (#3)** — Introduce `ScannerWorker(QObject)` moved to a `QThread`, emitting:
   - `progress(int scanned, int total, str current_file)`
   - `folder_done(str folder, list[Track] tracks)`
   - `all_done()`
   - `error(str folder, str message)`

   Main window shows a non-modal progress widget in the status area (not a modal dialog — dialogs block the user from using the library during scan). Show `folder_name (i/total)` + a cancel button. Respect cancellation between files.

**Acceptance:**
- Adding a folder with 5k files no longer freezes the UI for > 100ms.
- Adding a folder reads each file exactly once (verify via tmp-file mtime assertion in new test).
- `_refresh_library` rebuilds `QTableWidget` exactly once regardless of folder count.

**Risk:** `QThread` + Qt signals over Track objects (which carry `bytes` for album art) can be heavy to serialize across threads. Mitigation: keep `Track` passage within the worker-owned event loop or use `QMetaObject.invokeMethod` for UI updates. No new data-class changes required.

---

### Track B — Tooling & CI (Tier 4: #9, #10, #12)

**Owner target:** one small PR, ~1 hour. Fully parallel with A.
**Files touched:** `pyproject.toml`, `requirements.txt` (delete), `.github/workflows/ci.yml` (new).

**Steps:**
1. **Configure ruff (#9)** — Add to `pyproject.toml`:
   ```toml
   [tool.ruff]
   line-length = 100
   target-version = "py310"

   [tool.ruff.lint]
   select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
   ignore = ["E501"]  # handled by formatter
   ```
   Run `ruff check --fix src/ tests/` and review the diff.
2. **Consolidate deps (#10)** — Delete `requirements.txt`. Update `AGENTS.md` install line to `pip install -e ".[dev]"` only. Keep `REQUIREMENTS.md` (functional spec) — it's a different thing.
3. **Add CI (#12)** — `.github/workflows/ci.yml` running `ruff check`, `ruff format --check`, and `pytest` on push/PR against Python 3.10, 3.11, 3.12. Use `xvfb-run` on Linux for Qt tests.

**Acceptance:** CI green, `ruff check src/` still passes, `pytest` still passes.

**Risk:** low. If ruff auto-fix changes semantics, revert the offending rule.

---

### Track C — Docs cleanup (Tier 4: #11)

**Owner target:** one PR, ~1 hour. Fully parallel.
**Files touched:** `AGENTS.md`, `SPEC.md`, `REQUIREMENTS.md`, `plan.md`, `docs/*.md`.

**Steps:**
1. **Reconcile with current code.** `AGENTS.md:26-27` references `src/core/metadata.py` but the module is now `src/core/metadata/` (a package). Fix paths throughout. The "Project Structure" tree is missing `controllers/`, `events.py`, `interfaces.py`, `volume_utils.py`, `category_sources.py`.
2. **Deduplicate.** `REQUIREMENTS.md` + `SPEC.md` overlap heavily. Proposal: `SPEC.md` is the functional spec (what the app does), `AGENTS.md` is the developer guide (how to build it), `CLAUDE.md` stays as-is (agent instructions). Delete `REQUIREMENTS.md` and `plan.md` (stale scratch files).
3. **Archive completed work.** Move `docs/cross-computer-flash-drive-support-plan.md`, `docs/phase-4-*.md`, and `docs/implementation-summary-*.md` into `docs/archive/`. Keep `docs/portable-volume-support.md` if it's the maintained reference.

**Acceptance:** Top-level markdown count drops from 5 to 3. Every file path mentioned in remaining docs exists on disk.

**Risk:** zero. Documentation-only.

---

### Track D — UI test scaffold (Tier 3: #8 foundation)

**Owner target:** one PR, ~half day. Parallel with A, B, C.
**Files touched:** `pyproject.toml` (add `pytest-qt`), `tests/conftest.py`, `tests/ui/test_main_window_smoke.py` (new), `tests/core/test_scanner.py` (new), `tests/core/test_playback.py` (new).

**Why this goes in Wave 1:** adds the harness without touching `main_window.py`'s behavior, so it can't conflict with Track A. Once Track A lands, tests for the scan flow drop into the existing scaffold cleanly in Wave 2.

**Steps:**
1. Add `pytest-qt` to dev deps.
2. Extend `conftest.py` with a `main_window` fixture that builds `MainWindow()` pointing at a tmp_path config.
3. Write smoke tests that exercise the current (buggy) behavior — they will need to be updated after Track A. That's fine; tracking coverage is the point.
4. Add unit tests for `scanner.py` (`process_file` with sample MP3/FLAC), `playback.py` (state transitions via `QMediaPlayer` mock).

**Acceptance:** Tests for `scanner.py`, `playback.py`, and a smoke test for `main_window.py` boot. Coverage report shows `src/core/scanner.py` and `src/core/playback.py` above 70%.

**Risk:** pytest-qt setup on macOS can require `offscreen` platform plugin. Mitigation: `QT_QPA_PLATFORM=offscreen` env var in conftest.

---

## Wave 2 — Parallel tracks (after Wave 1 merges)

### Track E — Error surfacing + input guards (Tier 1: #4, #5)

**Files touched:** `src/ui/main_window.py` (category flow only), `src/core/categorizer.py`, `src/ui/widgets.py` (new `Toast` widget, optional).
**Depends on:** Track A (main_window.py churn settled).

**Steps:**
1. **Propagate write result (#4)** — Change `Categorizer.add_category` / `remove_category` / `clear_categories` to return `Result` (or raise a `MetadataWriteError`). `CategoryController` catches and emits a new signal `write_failed(track, reason)`. `MainWindow` shows an inline toast and rolls back the in-memory category list.
2. **Guard multi-word input (#5)** — In `_on_add_category_input` (main_window.py:348), reject input containing whitespace with a one-line hint below the input ("Categories must be a single word"). Don't auto-mangle.

**Acceptance:** Unit test forcing `write_comment` to return `False` shows the pill disappears again and an error is visible; typing "classical music" shows the guard hint.

---

### Track F — Row-index map (Tier 2: #6)

**Files touched:** `src/ui/main_window.py`, `src/ui/track_table.py`.
**Depends on:** Track A (scan flow is where the map is populated).

**Steps:**
1. Add `self._row_by_track_id: dict[int, int] = {}` populated in `TrackTableManager.populate()`.
2. `_refresh_track_in_table` does `row = self._row_by_track_id.get(track.id); if row is None: return` — O(1).
3. Keep the map in sync when rows are removed (currently only happens on `library.clear`).

**Acceptance:** micro-benchmark: 10k-row table + 1k category updates runs in < 200ms (vs. multiple seconds currently).

**Risk:** low — surgical, single data structure.

---

### Track G — UX polish (Tier 5: #13, #14, #15)

**Files touched:** `src/ui/main_window.py`.
**Depends on:** Track A.

**Steps:**
1. **Shortcuts (#13)** — `QShortcut(QKeySequence("Ctrl+F"))` → search focus, `Space` on table → play/pause, `Del` on pill → remove, `Ctrl+R` → refresh, `Ctrl+O` → add folder.
2. **Don't full-reload on mutation (#14)** — `_add_folder` / `_remove_folder` should only affect the folder touched, not iterate the whole library. Scan the added folder; drop only that folder's tracks on remove.
3. **Dead signal (#15)** — Either wire `_on_folder_clicked` to filter the track table by folder, or remove `self.folder_tree_widget.itemClicked.connect(self._on_folder_clicked)` and the empty method. Pick one per your product intent.

---

## Wave 3 — Deferred (optional)

### Track H — QAbstractTableModel migration (Tier 2: #7)

**Ship only when library routinely exceeds ~20k tracks.** This is a meaningful rewrite of `track_table.py`. After Track F lands, the perf floor is high enough that this is a "when we outgrow it" change, not an immediate need.

**Design sketch:**
- `TrackTableModel(QAbstractTableModel)` holds `list[Track]` directly — no cell-by-cell storage.
- `CategoryDelegate(QStyledItemDelegate)` renders the category column with pills without per-cell widgets.
- Row-index map from Track F is replaced by the model's natural row lookup.

**Risk:** medium. Selection / sort / context-menu code all sits on the widget today; all of it needs re-wiring.

---

## Per-tier action plans (quick reference)

### Tier 1 — Real bugs
| # | Finding | Track | Wave |
|---|---|---|---|
| 1 | Double-scan on add_folder | A | 1 |
| 2 | Refresh rebuilds table N times | A | 1 |
| 3 | Scanner blocks UI thread | A | 1 |
| 4 | Silent metadata-write failures | E | 2 |
| 5 | Multi-word category input mangled | E | 2 |

### Tier 2 — Scale & performance
| # | Finding | Track | Wave |
|---|---|---|---|
| 6 | O(n) row lookup | F | 2 |
| 7 | QTableWidget → QAbstractTableModel | H | 3 (deferred) |

### Tier 3 — Tests
| # | Finding | Track | Wave |
|---|---|---|---|
| 8 | Zero UI-layer tests | D | 1 (scaffold), 2 (flesh out) |

### Tier 4 — DX & tooling
| # | Finding | Track | Wave |
|---|---|---|---|
| 9  | Ruff has no rules configured | B | 1 |
| 10 | Duplicated deps declarations | B | 1 |
| 11 | Docs sprawl | C | 1 |
| 12 | No CI | B | 1 |

### Tier 5 — UX polish
| # | Finding | Track | Wave |
|---|---|---|---|
| 13 | No keyboard shortcuts | G | 2 |
| 14 | Full library reload on mutation | G | 2 |
| 15 | Dead folder-tree click handler | G | 2 |

---

## Conflict map

File-level conflict analysis — any two tracks that touch the same file cannot run concurrently unless noted.

| File | A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|---|
| `src/ui/main_window.py` | ✔ |   |   |   | ✔ | ✔ | ✔ |
| `src/core/scanner.py`   | ✔ |   |   | ✔* |   |   |   |
| `src/core/categorizer.py` |   |   |   |   | ✔ |   |   |
| `src/ui/track_table.py` |   |   |   |   |   | ✔ |   |
| `pyproject.toml`        |   | ✔ |   | ✔ |   |   |   |
| `tests/**`              |   |   |   | ✔ |   |   |   |
| Docs                    |   |   | ✔ |   |   |   |   |

`*` Track D touches `scanner.py` tests only, not the module itself — safe to parallelize with A.
`pyproject.toml` conflict between B and D: trivial to merge (add sections vs. add dep); sequence locally or coordinate.

Within a wave, tracks run in parallel if their columns don't overlap. All Wave 2 tracks share `main_window.py` and **must merge serially** — but they can be developed in parallel and rebased.

---

## Suggested PR sequence

1. **PR-1 (Track B)** — Ruff config + consolidate deps + CI. Lands first so everything else benefits from the gate.
2. **PR-2 (Track C)** — Docs cleanup. Independent; easy review.
3. **PR-3 (Track D)** — Test scaffold. Locks in existing-behavior baseline.
4. **PR-4 (Track A)** — Scan flow overhaul. The big one. Should be reviewable because tests (PR-3) catch regressions.
5. **PR-5 (Track E)**, **PR-6 (Track F)**, **PR-7 (Track G)** — In any order, but each one rebases on the previous since all three touch `main_window.py`.
6. **PR-8 (Track H)** — Only if warranted.

---

## Effort estimate

| Wave | Work | Wall-clock (1 engineer) | Wall-clock (parallel) |
|---|---|---|---|
| 1 | A + B + C + D | ~3-4 days serial | ~1.5 days with 4 tracks |
| 2 | E + F + G | ~2 days serial | ~1 day with 3 tracks |
| 3 | H | ~2-3 days |  |
| **Total (without H)** | | **~5-6 days** | **~2.5 days** |
