```markdown
# MonoVault Refactoring — Overview

## Summary

Three-phase refactoring to transform MonoVault from a tightly-coupled god-object architecture into a modular, testable, extensible desktop application. Each phase is independently deliverable and mergeable.

## Current State

| Metric | Value |
|---|---|
| Total source lines | ~1,632 |
| Largest file | `main_window.py` (750 lines) |
| Test coverage | ~0% (no tests directory exists) |
| Interfaces/Protocols | 0 |
| Silent `except Exception` blocks | 6 (all in `metadata.py`) |

## Target State

| Metric | Target |
|---|---|
| Largest file | < 300 lines |
| Test coverage | >= 80% |
| Interfaces/Protocols | 3+ (metadata, repository, category source) |
| Silent exception handlers | 0 |
| Controllers extracted from MainWindow | 3 (playback, search, category) |

## Phase Dependency Map

```
Phase 1: Extract Interfaces & Fix Testability
    │
    ├── [No UI changes, pure backend refactoring]
    ├── IMetadataParser + Mp3Parser + FlacParser
    ├── ITrackRepository (LibraryManager implements)
    ├── ICategorySource (pluggable suggestions)
    ├── Proper error logging in metadata.py
    └── Test infrastructure + ~80% core coverage
         │
         ▼
Phase 2: Decompose MainWindow
    │
    ├── [UI restructuring, depends on Phase 1 interfaces]
    ├── PlaybackController
    ├── SearchController
    ├── CategoryController
    └── MainWindow becomes thin coordinator
         │
         ▼
Phase 3: Event Bus
    │
    ├── [Architectural, depends on Phase 2 controllers]
    ├── EventBus with publish/subscribe
    ├── Controllers communicate via events
    └── New features = new subscribers only
```

## Cross-Phase Dependencies

| Dependency | From | To | Why |
|---|---|---|---|
| `ITrackRepository` | Phase 1 | Phase 2 | Controllers depend on repository interface, not concrete `LibraryManager` |
| `IMetadataParser` | Phase 1 | Phase 2 | `CategoryController` uses metadata writes via interface |
| `ICategorySource` | Phase 1 | Phase 2 | `CategoryController` uses pluggable suggestion strategy |
| Test infrastructure | Phase 1 | Phase 2 | Phase 2 controllers need existing test patterns |
| Controller boundaries | Phase 2 | Phase 3 | Event bus replaces direct references between controllers |

## Parallel Work Tracks

### Phase 1 (3 parallel tracks)
- **Track A**: `IMetadataParser` + `Mp3Parser` + `FlacParser` + metadata tests
- **Track B**: `ITrackRepository` + `LibraryManager` refactor + library tests
- **Track C**: `ICategorySource` + suggestion strategies + categorizer tests

Merge order: A first (no deps), then B (no deps on A), then C (depends on B for `ITrackRepository`).

### Phase 2 (2 parallel tracks after sequential setup)
- **Sequential**: Create controller base patterns and `MainWindow` scaffold
- **Track D**: `PlaybackController` extraction + tests
- **Track E**: `SearchController` + `CategoryController` extraction + tests (E depends on Phase 1 Track C)

### Phase 3 (2 parallel tracks)
- **Track F**: `EventBus` implementation + unit tests
- **Track G**: Controller migration to event bus (sequential, after F)

## Effort Estimates

| Phase | Estimated Effort | Risk |
|---|---|---|
| Phase 1 | 3-4 days | Low — no UI changes, pure refactoring |
| Phase 2 | 4-5 days | Medium — UI restructuring, regression risk |
| Phase 3 | 2-3 days | Medium — architectural change, but controllers already isolated |
| **Total** | **9-12 days** | |

## Verification Checkpoints

After each phase, the application must:
1. Launch with `python -m src.ui.main_window` and function identically to before
2. Pass `ruff check src/` with no errors
3. Pass `pytest` with >= 80% coverage on changed modules
4. Have no silent `except Exception` blocks (Phase 1+)

## New File Structure (Final)

```
src/
  models/
    track.py                    # Track dataclass (unchanged)
  core/
    interfaces.py               # NEW: IMetadataParser, ITrackRepository, ICategorySource
    config.py                   # Unchanged
    library.py                  # Modified: implements ITrackRepository
    library_store.py            # Unchanged
    scanner.py                  # Modified: uses IMetadataParser
    metadata/                   # NEW: package replacing metadata.py
      __init__.py               # Re-exports for backward compat
      base.py                   # IMetadataParser protocol
      mp3_parser.py             # Mp3Parser
      flac_parser.py            # FlacParser
      registry.py               # Format registry + factory
    categorizer.py              # Modified: uses ICategorySource
    category_sources.py         # NEW: ArtistCategorySource, SimilarCategorySource
    playback.py                 # Unchanged
    events.py                   # NEW (Phase 3): EventBus
  ui/
    main_window.py              # Slimmed to ~200 lines
    controllers/                # NEW (Phase 2)
      __init__.py
      playback_controller.py
      search_controller.py
      category_controller.py
    widgets.py                  # Unchanged
    styles.py                   # Unchanged
tests/
  __init__.py
  conftest.py                   # Shared fixtures
  core/
    __init__.py
    test_metadata_mp3.py
    test_metadata_flac.py
    test_metadata_registry.py
    test_library.py
    test_categorizer.py
    test_category_sources.py
    test_scanner.py
    test_events.py              # Phase 3
  ui/
    __init__.py
    test_playback_controller.py
    test_search_controller.py
    test_category_controller.py
```
```

---