# Design and engineering decisions (v0.4.0)

This release rebuilds the desktop presentation layer without changing the
sorting engine, the CLI contract, or the on-disk history format's meaning.
The notes below record the non-obvious choices so future changes can see
*why* the UI looks and behaves the way it does.

## Visual language

- **Flat, crisp surfaces instead of rounded cards.** Tk's native widgets
  cannot draw reliable rounded corners across Windows themes and DPI
  levels. Cards therefore use a 1px border, a flat fill, and spacing to
  create hierarchy. This is deliberate, not a missing style.
- **No gradients, glow, glass, or emoji.** The palette is warm-neutral
  slate for dark mode and warm paper for light mode. Both palettes were
  designed independently rather than inverted from one another.
- **One spacing/type/radius scale.** All page padding, gaps, control
  heights, font sizes, and radii come from `ezsort/gui/tokens.py` and are
  scaled from the real display DPI. Pages do not hard-code pixel values.
- **Contrast is tested, not eyeballed.** `tests/test_gui.py` checks body,
  secondary, accent-label, and status colors against WCAG AA (4.5:1) in
  both themes. Palette edits must keep those tests green.
- **The interface never invents data.** Statistics, badges, progress,
  history rows, activity entries, and empty states are all derived from
  the engine, config, history, or activity log. There are no placeholder
  numbers or dead buttons.

## Window and layout

- **DPI awareness is requested before the first Tk window exists.** The
  app asks for per-monitor-v2 awareness and falls back to system-DPI
  awareness, then derives a single UI scale from `winfo_fpixels("1i")`.
  Without this, Windows bitmap-scales the entire interface.
- **The window is clamped to the work area.** The requested height is
  limited to `screen_height - 120` so the status bar never hides behind
  the Windows taskbar on 1080p displays.
- **Minimum usable size is 1281x851 physical pixels.** At 120 DPI that is
  roughly 1024x680 logical pixels. Every page was captured and inspected
  at that size; content reflows or scrolls, and the status bar stays
  visible.
- **Tables never dictate page width.** The table asks for a tiny width,
  disables grid propagation, and re-proportions columns from the width it
  is actually given. There is no horizontal scrollbar; long values are
  middle-ellipsized and carry the full text in a tooltip.
- **Scrollbars appear only when needed.** `ScrollableFrame` compares the
  content's bounding box to the canvas height and hides the scrollbar when
  everything fits. Pages may bind `<Configure>` on the body, but must use
  `add="+"` so the frame's own handler survives.

## Data and compatibility

- **History format changes are additive.** New batches carry `status`,
  `cancelled`, and `total_planned`; operations carry `status`. A fully
  undone batch stays on disk as a tombstone (`undone`, `undone_at`,
  `restored`, empty `operations`) so History can explain it, but it is
  excluded from statistics and cannot be undone twice. v0.3.0 files load
  unchanged and undo normally (covered by a regression test).
- **Activity is persisted.** `activity.json` keeps the last 500 entries in
  the same `time`/`type`/`message` shape, so old readers and old files stay
  compatible. Corrupt files are moved aside rather than discarded.
- **Undo reports are structured.** `UndoReport` carries restored, missing,
  conflict, and error details so the GUI can tell the truth instead of
  collapsing every outcome into "success" or "failed".
- **CLI and GUI share one engine.** A golden test runs both front ends on
  identical synthetic folders and asserts the resulting file trees match,
  including hidden files and partial downloads that must stay put.

## Performance

- **Planning is O(n).** The planner resolves the target folder once and
  maps each source lexically onto it; it never calls `Path.resolve()` per
  file or per destination. This took a 10k-file preview from roughly 100
  seconds to under 10 seconds on the test machine.
- **The scanner trusts `DirEntry`.** File size, extension, and type come
  from the directory entry already read, avoiding four extra filesystem
  probes per file.
- **Table inserts are O(1) amortized.** The empty-state check only runs
  when the first row is inserted, not on every row. A 10k-row render is
  covered by a performance test.

## Testing and release

- **All tests use isolated profiles and synthetic data.** `EZSORT_HOME`
  points at a temporary directory; no test reads or writes the real user
  profile, Downloads folder, config, history, or activity log.
- **Screenshots come from the real app.** `scripts/capture_ui.py` launches
  the actual Tk application against a throwaway profile and a synthetic
  demo folder. It maps the window before setting geometry, parks the
  cursor, and hides toasts/tooltips so captures are deterministic.
- **Windows builds are onedir zips.** The GUI and CLI keep separate output
  folders (`EzSort` and `ezsort-cli`) because Windows paths are
  case-insensitive. Releases attach both zips plus `SHA256SUMS.txt`.
- **The tag must point at the tested commit.** CI runs the full suite,
  builds both executables, verifies them end to end (launch, screenshot,
  persistence, clean close), and only then publishes the tag's release.
