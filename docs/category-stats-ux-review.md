 ---
  Category Stats Tab & Filter — UX Review

  Critical Issues (Most Impactful)

  1. No active filter indicator in the Library tab
  The biggest usability hole. When you double-click a category and get switched to Library, the search box is empty and shows nothing. After the 5-second status bar message fades, there is zero indication that
  the track list is a filtered subset. Users will think they're seeing all tracks and act on that assumption — adding categories, assessing their library — while actually working on a filtered view. A persistent
  banner or label like ▶ Filtered by: "rock" [×] at the top of the track table panel is essential.

  2. No way to clear the category filter
  Once a category filter is active, there's no affordance to clear it. The user has to intuit that typing anything in the search box and then clearing it resets the view. The filter_by_category path bypasses
  _pending_query entirely, so the search input gives no clue. The clear/reset path needs to be explicit.

  3. Double-click to filter is invisible
  Nothing on the category stats tab communicates that rows are double-clickable to filter. No tooltip, no "click to filter" hint, no cursor change, no button. The action is completely hidden. A single-click
  "Filter →" button per row, or at minimum a tooltip on the row, would make this discoverable.

  ---
  Significant Issues

  4. Two different "filter" concepts share the same mental model
  The Filter categories... search input at the top of the Stats tab filters the list of categories shown in the stats table. The double-click triggers a library filter. Both are called "filter" but do completely
  different things in different scopes. Rename the stats tab search to something like Search categories... to distinguish it.

  5. Category filter ignores the folder tree filter
  filter_by_category calls self._repo.get_all_tracks() — it ignores whatever folders are currently checked in the folder tree. If you've scoped to a subfolder and then filter by category, you suddenly see tracks
  from all folders. The method should intersect with the folder-filtered set, not replace it.

  6. Tab switch on double-click is jarring
  Double-clicking a category on the Stats tab immediately teleports the user to the Library tab. There's no opt-in, no affordance — you're browsing stats and suddenly you're somewhere else. The UX should be
  additive: show a "Show in library" button or right-click action rather than an involuntary context switch.

  ---
  Minor Issues

  7. Stale data with no visual indication
  The dirty flag (_dirty) is silent. When categories change, the Stats tab becomes stale but doesn't show anything until the user manually switches tabs (which triggers show_if_dirty). The Refresh button exists
  but users won't know to click it unless they notice the data seems off. A subtle "Data may be outdated — Refresh" nudge would help.

  8. Orphan threshold (⚠ flag) is not explained
  _orphan_threshold = 1 is hardcoded. The ⚠ flag column has no tooltip, no legend. Users seeing a warning icon with no explanation will be confused about what it means and what they should do.

  9. Co-occurrence panel (Pairs) has no context
  The right panel shows Pair | Count with no title or explanation. "Count" of what? A label like "Category Co-occurrences" with a one-line description (e.g., "How often two categories appear together") would make
   it immediately understandable.

  10. filter_by_category doesn't publish to EventBus
  _execute_search publishes SearchResultsChanged on the bus, but filter_by_category silently bypasses it. Any future subscribers or features expecting that signal will be blind to category filter activations.
  Consistency requires publishing there too.

  ---
  Summary Priority

  ┌─────┬───────────────────────────────────────┬──────────┐
  │  #  │                 Issue                 │ Severity │
  ├─────┼───────────────────────────────────────┼──────────┤
  │ 1   │ No active filter indicator in Library │ Critical │
  ├─────┼───────────────────────────────────────┼──────────┤
  │ 2   │ No way to clear category filter       │ Critical │
  ├─────┼───────────────────────────────────────┼──────────┤
  │ 3   │ Double-click action is invisible      │ Critical │
  ├─────┼───────────────────────────────────────┼──────────┤
  │ 4   │ Two "filter" concepts, one word       │ Medium   │
  ├─────┼───────────────────────────────────────┼──────────┤
  │ 5   │ Category filter ignores folder filter │ Medium   │
  ├─────┼───────────────────────────────────────┼──────────┤
  │ 6   │ Involuntary tab switch on activate    │ Medium   │
  ├─────┼───────────────────────────────────────┼──────────┤
  │ 7   │ Silent stale data state               │ Low      │
  ├─────┼───────────────────────────────────────┼──────────┤
  │ 8   │ Unexplained orphan threshold/flag     │ Low      │
  ├─────┼───────────────────────────────────────┼──────────┤
  │ 9   │ Pairs panel has no context            │ Low      │
  ├─────┼───────────────────────────────────────┼──────────┤
  │ 10  │ Missing EventBus publish              │ Low      │
  └─────┴───────────────────────────────────────┴──────────┘

  Want me to fix any of these? I'd suggest starting with 1 + 2 + 3 as they're the most disorienting.