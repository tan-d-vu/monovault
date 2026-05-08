---
status: not-started
phase: 1
updated: 2026-05-08
---

# Implementation Plan: Date Filter

## Goal
Add preset date filters to the track table via right-click on the "Date Added" column header, composing with the existing text search and folder-tree selection.

## Context & Decisions

| Decision | Rationale |
|----------|-----------|
| Presets only (no date picker) | User specified; covers the common cases without added UI complexity |
| Right-click on Date Added header | Discoverable and non-intrusive — no permanent UI real estate used |
| Filter resets on restart | User specified; avoids persisting filter state |
| `DatePreset` enum lives in `src/core/date_filter.py` | Core logic (cutoff calculation, track filtering) is UI-agnostic and testable in isolation |
| Post-filter in `search_immediate` | Boolean search already owns the single filtering path (parse → evaluate). Date filter is a cheap post-step on those results — no restructuring needed. |
| No `_active_category` needed | Category filtering now goes through the search query string (`category:"rock"`), so `SearchController` has no separate category state to track. |
| `date_added` is always a valid ISO date | Confirmed: `record_if_new` derives from `mtime` even for read-only folders. No null-handling needed in filter logic. |

## Phase 1: Core Filter Logic [PENDING]

- [ ] **1.1 Create `src/core/date_filter.py`** ← CURRENT
  - `DatePreset` enum: `LAST_7_DAYS`, `LAST_30_DAYS`, `LAST_3_MONTHS`, `THIS_YEAR`
  - `cutoff_date(preset: DatePreset) -> date` — returns the earliest date that passes the filter
  - `apply_date_filter(tracks: list[Track], preset: DatePreset | None) -> list[Track]` — returns subset where `track.date_added >= cutoff.isoformat()`; returns `tracks` unchanged when `preset is None`
- [ ] 1.2 Write `tests/core/test_date_filter.py`
  - One test per preset verifying cutoff boundary (track on cutoff date passes, day before fails)
  - Test that `preset=None` returns all tracks unchanged

## Phase 2: SearchController Integration [PENDING]

Boolean search already provides a single filtering path (`parse` → `evaluate`). The date
filter slots in as a post-step with minimal changes:

- [ ] 2.1 Add `_date_preset: DatePreset | None = None` to `SearchController.__init__`
- [ ] 2.2 Extract `_apply_filters(self) -> None` — single emission point:
  ```
  node = parse(self._pending_query)
  tracks = get_all_tracks()
  if node: tracks = [t for t in tracks if evaluate(node, t)]
  tracks = apply_date_filter(tracks, self._date_preset)
  emit results_changed(tracks)
  ```
- [ ] 2.3 Rewrite `search_immediate` and `get_all_tracks` to update state then delegate to `_apply_filters()`
- [ ] 2.4 Add `set_date_filter(preset: DatePreset | None) -> None` — stores `_date_preset`, calls `_apply_filters()`
- [ ] 2.5 Write `tests/ui/test_search_controller_date.py`
  - Date filter applied on top of boolean search results
  - `set_date_filter(None)` clears filter and emits unfiltered results
  - Changing date filter re-emits with updated results

## Phase 3: UI — Header Context Menu [PENDING]

- [ ] 3.1 Add `date_filter_changed = pyqtSignal(object)` to `TrackTableManager` and `_active_date_preset: DatePreset | None = None` field
- [ ] 3.2 Enable right-click on header:
  - `self._header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)`
  - Connect `self._header.customContextMenuRequested` → `_on_header_context_menu`
- [ ] 3.3 Implement `_on_header_context_menu(pos: QPoint) -> None`:
  - Resolve logical column: `self._header.logicalIndexAt(pos)`
  - Return early if not `TrackTableColumn.DATE_ADDED`
  - Build `QMenu` with actions for each `DatePreset` + a "Clear date filter" separator+action
  - Mark active preset with a checkmark (`action.setCheckable(True); action.setChecked(...)`)
  - On action triggered: update `_active_date_preset`, emit `date_filter_changed`
- [ ] 3.4 Wire in `MainWindow`: connect `track_table_manager.date_filter_changed` → `search_controller.set_date_filter`

## Notes
- 2026-05-03: `date_added` confirmed always populated — `record_if_new` uses `mtime` as fallback for read-only folders, so no empty-date edge case in filter logic.
- 2026-05-08: Boolean search removed separate category filter code path. `filter_by_category` method no longer exists — category filtering is via `category:"name"` query syntax. Phase 2 simplified accordingly: no `_active_category` field, no multiple code paths to merge.
