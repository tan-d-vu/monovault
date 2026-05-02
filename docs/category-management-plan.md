# Category Management — Implementation Plan

## Goal

Add the ability to **rename**, **merge**, and **delete** categories across the entire library from the Categories tab. The operations apply to every track in the in-memory library and persist to file metadata via the existing `MetadataWriteWorker` pool.

## Prerequisites

**Depends on `category-stats-plan.md` being implemented first.** It assumes:
- `src/ui/category_stats_tab.py` exists with `CategoryStatsTab(QWidget)` and a populated categories table.
- `src/core/category_stats.py` exists with `compute_stats`.
- `MainWindow` already has the Categories tab wired.

## User decisions baked into this plan

- Actions live in the Categories tab (right-click context menu, mirroring `src/ui/duplicates_tab.py`).
- One core operation: rename, merge, and delete are the same operation with different inputs (replace one or more source categories with an optional target).
- Failure mode: per-file write failures use the existing `_on_write_finished` → `_revert_from_disk` flow. **No new bulk-tracking machinery** — match the existing `clear_categories_bulk` pattern (`src/ui/controllers/category_controller.py:101`). This is the same volume of writes through the same single-thread pool; if toast spam on failure becomes a problem, it should be solved once for both flows.
- No undo. (Documented as a future-work item — see "Out of scope".)
- All categories remain lowercase + no whitespace (matches existing `Categorizer.parse_add_category` at `src/core/categorizer.py:35`).

## Verified codebase facts

- `Categorizer` (`src/core/categorizer.py`) takes `library: ITrackRepository`. To iterate, use `self._library.get_all_tracks()` (interface method) — do NOT poke `self._library.tracks` directly.
- `Track` is a mutable `@dataclass`. Its `categories: list[str]` and `comments: str` fields are independent storage.
- `panels.update_categories(track, categories_layout, on_remove)` (`src/ui/panels.py:328`) does two things: (1) rebuilds the category-pill widgets in the **selected track's** details panel, and (2) sets `track.comments = " ".join(track.categories)`. The second is a domain-data side effect masquerading as UI code.
- `MainWindow._on_categories_changed` (`src/ui/main_window.py:672`) calls `update_categories(track, self.categories_layout, ...)`. If we emit `categories_changed` for non-selected tracks (which our bulk operations will), the details panel pill area gets rebuilt with the wrong track's pills. We must fix this — see the `_on_categories_changed` change below.
- `MetadataWriteSignals.finished` is `pyqtSignal(str, bool, str)` — `(file_path, success, error_message)` (`src/ui/workers/metadata_worker.py:13`). The existing `_on_write_finished` already handles failures by reverting the in-memory state from disk and emitting `write_failed`.
- `EventBus.publish(CategoriesChanged(track=track))` is the existing pattern (`src/core/events.py:59`).
- The existing `clear_categories_bulk` at `src/ui/controllers/category_controller.py:101` is the precedent to copy. It loops, calls `apply_categories(track, [])`, emits `categories_changed`, schedules a write, and returns the count. No completion signal, no batch tracking.
- `tests/core/test_categorizer.py` and `tests/ui/test_category_controller.py` show the testing style — top-level `make_track`, `MagicMock` for the library, `make_ctrl` helper that mocks out `_schedule_write`. The bulk-clear tests at `tests/ui/test_category_controller.py:255` are a direct template.

## Architecture

### Modified file: `src/core/categorizer.py`

Add **one** method.

```python
def replace_categories_everywhere(
    self, sources: set[str], target: str | None
) -> list[Track]:
    """Replace each of `sources` (case-insensitive) with `target` on every track.

    - rename: sources={"rock"}, target="metal"
    - merge:  sources={"rock", "punk"}, target="metal"
    - delete: sources={"rock"}, target=None

    `target` (when not None) is normalized: stripped, lowercased; must be
    non-empty and contain no whitespace, else ValueError.

    Sources are matched case-insensitively. The target is excluded from sources
    (so `replace({"rock", "metal"}, "metal")` only replaces "rock").

    Categories that collide with `target` after replacement are dedup'd while
    preserving first-occurrence order.

    Also updates `track.comments = " ".join(track.categories)` so the comments
    column and duplicates tab stay in sync without depending on the UI layer.

    Returns the list of Track objects whose categories were modified.
    """
    target_norm: str | None = None
    if target is not None:
        target_norm = target.strip().lower()
        if not target_norm:
            raise ValueError("target cannot be empty")
        if any(c.isspace() for c in target_norm):
            raise ValueError("target cannot contain whitespace")

    source_set = {s.strip().lower() for s in sources if s.strip()}
    if target_norm is not None:
        source_set.discard(target_norm)
    if not source_set:
        return []

    modified: list[Track] = []
    for track in self._library.get_all_tracks():
        lowered = [c.lower() for c in track.categories]
        if not any(s in lowered for s in source_set):
            continue
        new_cats: list[str] = []
        seen: set[str] = set()
        for c in track.categories:
            cl = c.lower()
            if cl in source_set:
                if target_norm is None:
                    continue  # delete
                replacement = target_norm
            else:
                replacement = cl
            if replacement in seen:
                continue
            seen.add(replacement)
            new_cats.append(replacement)
        track.categories = new_cats
        track.comments = " ".join(new_cats)
        self._library.update_track(track)
        modified.append(track)
    return modified
```

Implementation notes:
- After this method, every modified track's categories are lowercased. That matches the existing convention enforced by `parse_add_category`.
- We update `track.comments` directly because the existing UI helper that does this (`panels.update_categories`) only runs for the selected track. Without this line, the duplicates tab and any cached comment displays for non-selected tracks would be stale.
- Dedup preserves first-occurrence order via `seen`. Tests below pin this.
- `list(...)` snapshot isn't necessary because `get_all_tracks()` already returns a fresh list.

### Modified file: `src/ui/controllers/category_controller.py`

Add one wrapper method. Pattern matches `clear_categories_bulk` exactly.

```python
def replace_everywhere(
    self, sources: set[str], target: str | None
) -> list[Track]:
    """Apply rename/merge/delete via the categorizer, emit signals, schedule writes.

    Returns the list of modified tracks (same as the categorizer method) so the
    caller can show a count. Raises ValueError if target is invalid.
    """
    modified = self._categorizer.replace_categories_everywhere(sources, target)
    if not modified:
        return modified

    for track in modified:
        self.categories_changed.emit(track)
        if self._bus:
            from ...core.events import CategoriesChanged
            self._bus.publish(CategoriesChanged(track=track))
        self._schedule_write(track.file_path, track.categories)

    if self._current_track and self._current_track in modified:
        self._refresh_suggestions()

    return modified
```

No new signal, no `_bulk_state`, no changes to `_on_write_finished`. Per-file write failures fall through the existing `write_failed` → revert flow.

### Modified file: `src/ui/main_window.py`

Fix the existing handler so emitting `categories_changed` for a non-selected track doesn't corrupt the details panel.

**Edit `_on_categories_changed`** (`src/ui/main_window.py:672`):

```python
def _on_categories_changed(self, track: Track) -> None:
    if track is self.category_ctrl.current_track:
        update_categories(track, self.categories_layout, self._on_remove_category)
    self.track_table_manager.update_track(track)
    self.duplicates_tab.update_track(track)
    self.category_stats_tab.invalidate()  # added by the stats plan; safe to leave
```

Why this is safe for the existing flows:
- Single-track add/remove/clear: the edited track *is* the selected track, so `update_categories` still runs.
- `clear_categories_bulk` from a multi-row context menu: the edited tracks are all selected, but only one is `current_track`. Today the handler rebuilds the details panel pill area for *each* of the cleared tracks (functionally a flicker; the final state is correct because all categories are empty). After this change, only the current_track's pills get rebuilt — same final state, no flicker. **Equivalent or better.**
- Our new bulk operations: edited tracks are mostly *not* selected. Today, this would corrupt the details panel pill area (it'd show the last-emitted track's pills instead of the selected track's). After this change, the selected track's pills stay correct.

The `track.comments` side effect that `update_categories` previously performed for every emitted track is now performed inside `Categorizer.replace_categories_everywhere` instead, so no track ends up with stale comments.

### Stats tab additions

Edit `src/ui/category_stats_tab.py` (created in the stats plan).

#### Switch to multi-select on the categories table

```python
self._category_table.setSelectionMode(
    QAbstractItemView.SelectionMode.ExtendedSelection
)
```

#### Add right-click context menu and Delete-key shortcut

Mirror `src/ui/duplicates_tab.py`:

```python
self._category_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
self._category_table.customContextMenuRequested.connect(self._on_context_menu)
self._category_table.installEventFilter(self)
```

#### Add intent signals (the tab does not call the controller directly)

```python
class CategoryStatsTab(QWidget):
    category_filter_requested = pyqtSignal(str)             # already exists
    rename_requested = pyqtSignal(str, str)                 # old, new
    merge_requested = pyqtSignal(list, str)                 # sources, target
    delete_requested = pyqtSignal(list)                     # categories to delete
```

`MainWindow` wires these to the controller — same pattern as `DuplicatesTab.track_selected`.

#### Context menu and prompts

```python
def _on_context_menu(self, pos) -> None:
    selected = self._selected_categories()
    if not selected:
        return
    menu = QMenu(self)
    rename_action = menu.addAction("Rename...")
    merge_action = menu.addAction("Merge into...")
    menu.addSeparator()
    delete_action = menu.addAction("Delete from all tracks")

    rename_action.setEnabled(len(selected) == 1)

    viewport = self._category_table.viewport()
    anchor = viewport if viewport is not None else self._category_table
    action = menu.exec(anchor.mapToGlobal(pos))

    if action == rename_action and len(selected) == 1:
        self._prompt_rename(selected[0])
    elif action == merge_action:
        self._prompt_merge(selected)
    elif action == delete_action:
        self._prompt_delete(selected)


def _selected_categories(self) -> list[str]:
    rows = sorted({item.row() for item in self._category_table.selectedItems()})
    out: list[str] = []
    for row in rows:
        item = self._category_table.item(row, 0)
        if item is None:
            continue
        cat = item.data(Qt.ItemDataRole.UserRole)
        if cat:
            out.append(cat)
    return out


def _prompt_rename(self, old: str) -> None:
    count = self._stats.counts.get(old, 0) if self._stats else 0
    new, ok = QInputDialog.getText(
        self, "Rename Category",
        f'Rename "{old}" (used by {count} tracks) to:',
        text=old,
    )
    if not ok:
        return
    new_norm = new.strip().lower()
    if not new_norm or any(c.isspace() for c in new_norm):
        QMessageBox.warning(self, "Invalid Name",
            "Category must be non-empty and contain no whitespace.")
        return
    if new_norm == old:
        return
    confirm = QMessageBox.question(
        self, "Confirm Rename",
        f'Rename "{old}" → "{new_norm}" on {count} tracks?\n'
        "This writes to file metadata and cannot be undone.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if confirm == QMessageBox.StandardButton.Yes:
        self.rename_requested.emit(old, new_norm)


def _prompt_merge(self, sources: list[str]) -> None:
    dialog = MergeDialog(sources, self._all_category_names(), self)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    target = dialog.target_value()
    affected = sum(self._stats.counts.get(s, 0) for s in sources) if self._stats else 0
    confirm = QMessageBox.question(
        self, "Confirm Merge",
        f'Merge {len(sources)} categories into "{target}"?\n'
        f"Up to {affected} tracks will be modified.\n"
        "This writes to file metadata and cannot be undone.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if confirm == QMessageBox.StandardButton.Yes:
        self.merge_requested.emit(sources, target)


def _prompt_delete(self, categories: list[str]) -> None:
    affected = sum(self._stats.counts.get(c, 0) for c in categories) if self._stats else 0
    label = ", ".join(f'"{c}"' for c in categories)
    confirm = QMessageBox.question(
        self, "Confirm Delete",
        f"Delete {label} from all tracks?\n"
        f"{affected} tracks will be modified.\n"
        "This cannot be undone.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if confirm == QMessageBox.StandardButton.Yes:
        self.delete_requested.emit(categories)


def _all_category_names(self) -> list[str]:
    if not self._stats:
        return []
    return sorted(self._stats.counts.keys())


def eventFilter(self, obj, event):
    if obj is self._category_table and event.type() == QEvent.Type.KeyPress:
        if event.key() == Qt.Key.Key_Delete:
            selected = self._selected_categories()
            if selected:
                self._prompt_delete(selected)
            return True
    return super().eventFilter(obj, event)
```

(`QInputDialog`, `QMessageBox`, `QMenu`, `QDialog`, `QEvent` need to be added to imports.)

### New file: `src/ui/dialogs/merge_dialog.py`

Create `src/ui/dialogs/__init__.py` (empty) if `src/ui/dialogs/` doesn't exist.

```python
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCompleter, QDialog, QDialogButtonBox, QLabel, QLineEdit,
    QListWidget, QVBoxLayout,
)


class MergeDialog(QDialog):
    def __init__(self, sources: list[str], all_categories: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Merge Categories")
        self._target = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Merging these categories:"))

        sources_list = QListWidget()
        sources_list.addItems(sources)
        sources_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        sources_list.setMaximumHeight(120)
        layout.addWidget(sources_list)

        layout.addWidget(QLabel("Into target category:"))
        self._target_input = QLineEdit()
        completer = QCompleter(all_categories, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._target_input.setCompleter(completer)
        layout.addWidget(self._target_input)

        layout.addWidget(QLabel(
            "Tip: type an existing category name or a new one. "
            "Lowercase, no spaces."
        ))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        value = self._target_input.text().strip().lower()
        if not value or any(c.isspace() for c in value):
            return  # Stay open; user must enter a valid value.
        self._target = value
        self.accept()

    def target_value(self) -> str:
        return self._target
```

### MainWindow wiring

In `src/ui/main_window.py`, after the existing `category_filter_requested` connection (added by the stats plan), add:

```python
self.category_stats_tab.rename_requested.connect(self._on_category_rename_requested)
self.category_stats_tab.merge_requested.connect(self._on_category_merge_requested)
self.category_stats_tab.delete_requested.connect(self._on_category_delete_requested)
```

New slot methods:

```python
def _on_category_rename_requested(self, old: str, new: str) -> None:
    try:
        modified = self.category_ctrl.replace_everywhere({old}, new)
    except ValueError as e:
        self.toast.show_message(f"Rename failed: {e}")
        return
    self._announce_bulk(f'Renamed "{old}" → "{new}"', len(modified))

def _on_category_merge_requested(self, sources: list, target: str) -> None:
    try:
        modified = self.category_ctrl.replace_everywhere(set(sources), target)
    except ValueError as e:
        self.toast.show_message(f"Merge failed: {e}")
        return
    self._announce_bulk(
        f'Merged {len(sources)} categories into "{target}"', len(modified)
    )

def _on_category_delete_requested(self, categories: list) -> None:
    try:
        modified = self.category_ctrl.replace_everywhere(set(categories), None)
    except ValueError as e:
        self.toast.show_message(f"Delete failed: {e}")
        return
    label = ", ".join(f'"{c}"' for c in categories)
    self._announce_bulk(f"Deleted {label}", len(modified))

def _announce_bulk(self, what: str, count: int) -> None:
    noun = "track" if count == 1 else "tracks"
    self.statusBar().showMessage(f"{what} on {count} {noun}.", 5000)
    self.category_stats_tab.invalidate()
```

The `category_stats_tab.invalidate()` already happens via `_on_categories_changed` (added in the stats plan), but calling it again here is idempotent and makes the flow easy to follow.

The status bar shows the immediate count; per-file write failures are surfaced through the existing `category_ctrl.write_failed` → `_on_write_failed` toast path that's already wired.

## Tests

### `tests/core/test_categorizer.py` (extend)

Add a `TestReplaceCategoriesEverywhere` class. Use a real `LibraryManager` (cheap) so `get_all_tracks()` works. Examples:

```python
def test_rename_basic(self):
    library = LibraryManager()
    t1 = make_track(id=1, categories=["rock", "90s"])
    t2 = make_track(id=2, categories=["jazz"])
    library.add_track(t1)
    library.add_track(t2)
    cat = Categorizer(library)

    modified = cat.replace_categories_everywhere({"rock"}, "metal")

    assert {t.id for t in modified} == {1}
    assert library.get_track_by_id(1).categories == ["metal", "90s"]
    assert library.get_track_by_id(1).comments == "metal 90s"
    assert library.get_track_by_id(2).categories == ["jazz"]
```

Cover:
- Rename: basic replacement; case-insensitive source match; target dedup when track already has target; comments updated.
- Merge: multiple sources collapse onto target; target appearing in sources is a no-op for that one; dedup preserved.
- Delete (`target=None`): removes from all tracks; case-insensitive; empty result when no track has the category.
- Validation: empty target raises ValueError; whitespace target raises ValueError; `target=None` is **not** invalid.
- No matching tracks → returns `[]`, no library mutation.

### `tests/ui/test_category_controller.py` (extend)

Mirror the bulk-clear class at line 255. Use the existing `make_track` and `make_ctrl` helpers. Examples:

```python
def test_replace_everywhere_emits_signal_and_schedules_writes(self, qapp):
    categorizer = MagicMock()
    track1 = make_track(categories=["rock"])
    track2 = make_track(categories=["rock"])
    categorizer.replace_categories_everywhere.return_value = [track1, track2]
    ctrl = make_ctrl(categorizer)

    emitted = []
    ctrl.categories_changed.connect(emitted.append)

    result = ctrl.replace_everywhere({"rock"}, "metal")

    assert result == [track1, track2]
    assert emitted == [track1, track2]
    assert ctrl._schedule_write.call_count == 2

def test_replace_everywhere_empty_modified_is_noop(self, qapp):
    categorizer = MagicMock()
    categorizer.replace_categories_everywhere.return_value = []
    ctrl = make_ctrl(categorizer)
    result = ctrl.replace_everywhere({"unknown"}, "x")
    assert result == []
    ctrl._schedule_write.assert_not_called()

def test_replace_everywhere_refreshes_suggestions_when_current_modified(self, qapp):
    categorizer = MagicMock()
    categorizer.get_suggestions.return_value = []
    track = make_track(categories=["rock"])
    categorizer.replace_categories_everywhere.return_value = [track]
    ctrl = make_ctrl(categorizer)
    ctrl.select_track(track)
    categorizer.get_suggestions.reset_mock()

    ctrl.replace_everywhere({"rock"}, "metal")

    categorizer.get_suggestions.assert_called_once_with(track)
```

## Step-by-step for handoff

1. Add `replace_categories_everywhere` to `src/core/categorizer.py`. Don't modify any existing methods.
2. Add tests in `tests/core/test_categorizer.py` (new `TestReplaceCategoriesEverywhere` class). Run `pytest tests/core/test_categorizer.py`. Confirm green.
3. Add `replace_everywhere` wrapper to `src/ui/controllers/category_controller.py`. No new signal, no state changes, no `_on_write_finished` modification.
4. Add tests in `tests/ui/test_category_controller.py`. Run that file's tests. Confirm green.
5. Edit `src/ui/main_window.py:_on_categories_changed` to gate `update_categories` on `current_track` (per spec above). Run the existing test suite — `pytest tests/` — and confirm no regressions, especially `tests/ui/test_main_window_smoke.py` and any test exercising single-track edits.
6. Create `src/ui/dialogs/__init__.py` (if missing) and `src/ui/dialogs/merge_dialog.py`.
7. Modify `src/ui/category_stats_tab.py`:
   - Switch the categories table to `ExtendedSelection`.
   - Add the three new pyqtSignals.
   - Add the context menu, prompt methods, helpers, and `eventFilter` per spec.
   - Add the new imports (`QInputDialog`, `QMessageBox`, `QMenu`, `QDialog`, `QEvent`, `MergeDialog`).
8. Modify `src/ui/main_window.py`:
   - Connect the three new tab signals.
   - Add the four new slot methods.
9. Run `ruff check src/` and `ruff format src/`. Run full `pytest`.
10. Manual smoke test:
    - Tag two tracks with `"rock"` and one track with both `"rock"` and `"metal"`.
    - Categories tab → right-click `"rock"` → Rename to `"metal"`. Verify the dual-tagged track ends up with `["metal"]` (no duplicate) and the others now have `["metal"]` instead of `["rock"]`. Verify the file metadata on disk: `python -c "from src.core.metadata import read_comment; print(read_comment('/path/to/file.mp3'))"`.
    - Re-tag, repeat for merge (select two categories, merge into a third existing one).
    - Repeat for delete (select one or more, confirm).
    - Trigger a write failure: `chmod a-w` a folder mid-test, perform a rename touching a track in that folder, confirm the existing per-file failure toast (`write_failed` flow) shows up and the read-only file's in-memory state reverts to its on-disk categories.
    - With a track from the affected category selected in the Library tab, perform a rename. Confirm the details panel pills rebuild correctly to show the renamed category (this validates the `_on_categories_changed` gating fix).

## Out of scope (v1)

- **Undo.** Writes are async per file; an undo stack would need to snapshot pre-write state per track in memory and on disk. Future work.
- **End-of-batch failure summary.** v1 uses the same per-file toast mechanism as `clear_categories_bulk`. If toast spam becomes a problem at scale, fix it once for both flows by introducing batch tracking on the controller — don't fork the failure pathway.
- **Find-and-replace by regex / substring rename.**
- **Suggesting merges based on string similarity** (e.g. "Did you mean to merge 'rocks' into 'rock'?").
- **Showing affected tracks before confirming.** The Library tab filter (from the stats plan) covers preview — user can click the category in the stats tab before invoking Rename.
- **Concurrent bulk operations.** v1 relies on the modal confirm dialog flow taking long enough that nobody starts two at once.
- **Editing the lowercase invariant.**
