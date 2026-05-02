# Duplicate Detection — Implementation Plan

## Goal

Add a "Find Duplicates" feature that identifies likely duplicate tracks in the library using metadata, presents them in a new tab, and lets the user act on them via the existing delete flow.

## Detection rules (v1)

A pair of tracks is considered a duplicate if **any** of these rules match. Matched pairs are unioned into groups via union-find, so a single group may have been connected by multiple rules.

| # | Rule | Key |
|---|------|-----|
| A | Same artist + same title | `(artist_norm, title_norm)` |
| B | Same filename | `basename_norm` |
| C | Same title + duration within ±1.0s | `title_norm`, then duration window |

**Normalization:** lowercase, strip leading/trailing whitespace. Nothing more aggressive in v1.

**Missing metadata:** if `title` or `artist` is empty, the track is skipped from rules A and C but still participates in rule B (filename) — per the user's choice.

**Minimum group size:** 2. Singletons are not reported.

## Architecture

### New files

**`src/core/duplicates.py`** — pure logic, no Qt.
```python
@dataclass
class DuplicateGroup:
    tracks: list[Track]

def find_duplicates(tracks: list[Track]) -> list[DuplicateGroup]:
    """Return groups of size >= 2. Order: largest groups first."""
```
Implementation:
- Union-find over track indices.
- Three passes (one per rule); each pass builds a dict from key → list of track indices and unions matches.
- Rule C: per `title_norm`, sort indices by duration and union consecutive pairs whose duration diff ≤ 1.0.
- Collect connected components, return components with ≥ 2 members.

**`src/ui/duplicates_tab.py`** — `DuplicatesTab(QWidget)`:
- Top bar: "Find Duplicates" `QPushButton` + status `QLabel` (`"12 groups · 28 tracks"`).
- Main area: a single `QTableWidget` (flat list, per the user's choice — verify simply first).
  - Columns: `Group`, `Title`, `Artist`, `Album`, `Duration`, `Filename`, `Location`.
  - `Group` column shows an integer group id so the user can sort/scan by group; rows are populated in group order so duplicates land adjacent.
  - Each cell stores its `Track` in `UserRole`, matching the existing `TrackTableManager` pattern.
- Right-click context menu: "Move to Trash" — reuses `DeleteController` already wired in `MainWindow`.
- Delete key shortcut via event filter — same pattern as the main track table.
- Multi-select enabled (`ExtendedSelection`).
- After a successful delete, removes the affected rows; if a group drops below 2 tracks, removes the remaining row(s) of that group too.

### Modified files

**`src/ui/main_window.py`**:
1. Wrap the existing 3-panel `QSplitter` in a `QTabWidget`.
   - Tab 0: "Library" — the current splitter, unchanged.
   - Tab 1: "Duplicates" — `DuplicatesTab` instance.
2. Pass `library_manager` and `delete_controller` into `DuplicatesTab` so it can read tracks and trigger deletes.
3. Connect `delete_controller.delete_completed` to a `DuplicatesTab.on_tracks_deleted(track_ids)` slot so the duplicates view stays in sync regardless of which tab triggered the delete.
4. Connect the scanner's `all_done` signal to a `DuplicatesTab.invalidate()` slot — clears stale results and resets the status label after a rescan.

No changes to `library.py`, `track.py`, or `delete_controller.py`.

## UI layout (Duplicates tab)

```
┌──────────────────────────────────────────────────────────┐
│  [ Find Duplicates ]   12 groups · 28 tracks             │
├──────────────────────────────────────────────────────────┤
│  Group │ Title          │ Artist  │ Album  │ Duration... │
│   1    │ Bohemian Rhap. │ Queen   │ Night  │  5:55       │
│   1    │ Bohemian Rhap. │ Queen   │ Hits   │  5:55       │
│   2    │ Wish You Were  │ Floyd   │ Wish   │  5:32       │
│   2    │ Wish You Were  │ Floyd   │ Echoes │  5:33       │
│   ...                                                    │
└──────────────────────────────────────────────────────────┘
```

The `Group` column is the v1 visual grouping cue. Rows already arrive in group order, so duplicates are visually adjacent; the column lets the user verify at a glance which rows belong together.

## Behavior

- **Find Duplicates button:** runs `find_duplicates(library.get_all_tracks())` synchronously on the UI thread. Metadata-only matching is O(n) and fast even for tens of thousands of tracks; no worker thread for v1.
- **Empty result:** status label shows `"No duplicates found."`, table is cleared.
- **Re-scanning the library:** invalidates current results (clears table, resets status to `"Click Find Duplicates to scan."`).
- **Switching tabs:** results persist until a new scan is run or the library is rescanned.
- **Delete:** identical UX to the main track table — `QMessageBox.question` confirmation, then `DeleteController.delete_tracks(...)`. The same `_confirm_and_delete_tracks` helper on `MainWindow` should be reused (extract to a method the tab can call, or expose via the controller wiring).

## Step-by-step implementation order

1. **Core logic + tests.** Write `src/core/duplicates.py` with `find_duplicates()` and a small union-find helper. Add `tests/test_duplicates.py` covering: empty input, no duplicates, rule A only, rule B only, rule C with ±1s edge, missing-metadata fallback to filename, transitive merging across rules.
2. **Skeleton tab.** Create `src/ui/duplicates_tab.py` with the button + empty table + status label. No logic yet.
3. **Wire QTabWidget into MainWindow.** Move the existing splitter into tab 0, add the new tab as tab 1. Verify the app still runs and looks the same.
4. **Wire Find Duplicates.** On click, call `find_duplicates`, populate the table, update status.
5. **Wire delete.** Add context menu + Delete key handler. Reuse `_confirm_and_delete_tracks`. Listen to `delete_completed` to update rows.
6. **Wire scan invalidation.** Clear results when scanner finishes.
7. **Manual smoke test:** create a test folder with known duplicates (re-encoded MP3, renamed copy, same song on two albums), confirm groups appear correctly and delete works.

## Testing checklist

- [ ] Empty library → button click produces "No duplicates found."
- [ ] Library with no duplicates → same.
- [ ] Two identical files at different paths → one group of 2 (rule A + B + C all hit).
- [ ] Same song on two albums → group of 2 (rule A hits; B and C may or may not).
- [ ] Renamed file with intact metadata → group via rule A.
- [ ] Stripped metadata + identical filename → group via rule B.
- [ ] Same title, different artist, same duration → group via rule C (intentional — accepts some false positives in v1).
- [ ] Track with empty title and artist but matching filename → groups via rule B only.
- [ ] Delete a duplicate → row disappears; if group drops to 1 track, that row also disappears.
- [ ] Rescan library → duplicates tab clears.

## Out of scope (v1)

- Audio fingerprinting (decided against — too much work).
- Aggressive normalization (`feat.`, `(Remastered)`, punctuation stripping).
- Picking a "keeper" automatically.
- Merging categories from soon-to-be-deleted duplicates onto the keeper.
- Tree/expandable group display — flat for v1.
- Background-thread scanning, progress bar — not needed at metadata speeds.
- Persisting results across app restarts.

These are good v2 candidates if v1 proves the UX.
