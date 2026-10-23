"""Desktop GUI tests.

These build the real Tk application (window included). The whole module is
skipped when Tk cannot start - e.g. on a headless CI runner - so the core
suite still runs everywhere.

Every test runs under the shared ``EZSORT_HOME`` isolation fixture, so the
app never touches the real user configuration or history.
"""

from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter", reason="tkinter is not available")

from ezsort.gui import theme, tokens  # noqa: E402


# ----------------------------------------------------------------------
# Pure helpers (no window needed)
# ----------------------------------------------------------------------

#: Every palette role the pages and widgets rely on. The design tokens are
#: the single source of truth; a palette must define exactly these roles.
REQUIRED_ROLES = list(tokens.COLOR_ROLES)


def test_both_palettes_define_every_role():
    for name, palette in theme.PALETTES.items():
        missing = [role for role in REQUIRED_ROLES if role not in palette]
        assert not missing, f"{name} palette is missing roles: {missing}"


def test_palette_role_values_are_hex_colors():
    for name, palette in theme.PALETTES.items():
        for role in REQUIRED_ROLES:
            if role == "name":
                continue
            value = palette[role]
            assert value.startswith("#") and len(value) in (4, 7), (
                f"{name}.{role} = {value!r} is not a hex color"
            )


def _luminance(hex_color: str) -> float:
    text = hex_color.lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    r, g, b = (int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("palette_name", sorted(theme.PALETTES))
def test_body_text_contrast_meets_wcag_aa(palette_name):
    """Normal-size body text must clear the 4.5:1 WCAG AA threshold."""
    p = theme.PALETTES[palette_name]
    assert _contrast(p["text"], p["surface"]) >= 4.5
    assert _contrast(p["text"], p["bg"]) >= 4.5


@pytest.mark.parametrize("palette_name", sorted(theme.PALETTES))
def test_secondary_text_is_readable(palette_name):
    """Secondary text (captions, hints) still needs 4.5:1 against surfaces."""
    p = theme.PALETTES[palette_name]
    assert _contrast(p["text_secondary"], p["surface"]) >= 4.5, (
        f"{palette_name}: secondary-on-surface contrast too low"
    )
    assert _contrast(p["text_secondary"], p["bg"]) >= 4.5
    assert _contrast(p["text_secondary"], p["sidebar"]) >= 4.5


@pytest.mark.parametrize("palette_name", sorted(theme.PALETTES))
def test_accent_button_label_contrast(palette_name):
    """The primary button's label must be legible on the accent fill."""
    p = theme.PALETTES[palette_name]
    assert _contrast(p["on_accent"], p["accent"]) >= 4.5


@pytest.mark.parametrize("palette_name", sorted(theme.PALETTES))
def test_status_colors_visible_on_surface(palette_name):
    """Moved/failed/warning row colors must be readable on table rows."""
    p = theme.PALETTES[palette_name]
    for role in ("success", "danger", "warning"):
        assert _contrast(p[role], p["surface"]) >= 4.5, (
            f"{palette_name}: {role} not readable on surface"
        )


def test_row_tag_stripes_alternate_rows():
    assert theme.row_tag(0) == ()
    assert theme.row_tag(1) == ("odd",)
    assert theme.row_tag(2) == ()
    assert theme.row_tag(3) == ("odd",)


def test_short_path_keeps_short_paths_intact():
    assert theme.short_path("C:\\Users\\me\\Downloads", 64) == (
        "C:\\Users\\me\\Downloads"
    )


def test_short_path_truncates_and_keeps_the_tail():
    long_path = "C:\\" + "\\".join(f"segment{i}" for i in range(20))
    shortened = theme.short_path(long_path, 40)
    assert len(shortened) <= 40
    assert shortened.endswith(long_path[-8:]), "the filename must stay visible"
    assert "..." in shortened


def test_get_palette_defaults_to_dark():
    assert theme.get_palette(None)["name"] == "dark"
    assert theme.get_palette("bogus")["name"] == "dark"
    assert theme.get_palette("light")["name"] == "light"


# ----------------------------------------------------------------------
# The real application (skipped when Tk cannot start)
# ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    """One real EzSortApp for the whole module (window is withdrawn)."""
    try:
        from ezsort.gui.app import EzSortApp
        application = EzSortApp()
    except Exception as exc:  # no display / no Tk
        pytest.skip(f"Tk application could not start: {exc}")
    application.root.withdraw()
    try:
        yield application
    finally:
        try:
            application.runner.close()
            application.root.destroy()
        except Exception:
            pass


def _pump(app, rounds: int = 3) -> None:
    for _ in range(rounds):
        app.root.update()
        app.root.update_idletasks()


def _show(app, page_name: str):
    """Make *page_name* visible (which lazily builds it) and return it."""
    app.show_page(page_name)
    _pump(app)
    return app.pages[page_name]


def test_app_constructs_with_all_pages(app):
    _pump(app)
    expected = {"dashboard", "organizer", "categories", "history",
                "activity", "settings"}
    # Pages are built lazily on first show; visit each one.
    for name in expected:
        app.show_page(name)
        _pump(app)
    assert expected <= set(app.pages), (
        f"missing pages: {expected - set(app.pages)}"
    )
    app.show_page("dashboard")
    _pump(app)


def test_title_contains_the_version(app):
    from ezsort import __version__
    assert __version__ in app.root.title()


@pytest.mark.parametrize("page_name", ["dashboard", "organizer", "categories",
                                       "history", "activity", "settings"])
def test_every_page_shows_without_error(app, page_name):
    app.show_page(page_name)
    _pump(app)
    assert app.current_page == page_name
    assert str(app.pages[page_name].winfo_manager()) == "grid"


def test_window_icon_is_configured(app):
    """The app must locate its bundled icon when running from source."""
    from ezsort.gui.app import app_icon_path

    icon = app_icon_path()
    assert icon is not None and icon.is_file(), (
        "packaging/ezsort.ico was not found from the source tree"
    )


def test_frozen_icon_lookup_matches_the_spec(tmp_path, monkeypatch):
    """Frozen builds must find the icon where the spec puts it.

    Regression test: the spec bundles the icon into ``packaging/`` inside
    the PyInstaller bundle, but the lookup only checked the bundle root,
    so the frozen app silently lost its taskbar/title-bar icon.
    """
    import sys as _sys
    from ezsort.gui import app as app_module

    # The spec's datas entry: (icon, "packaging") -> MEIPASS/packaging/.
    bundled = tmp_path / "packaging"
    bundled.mkdir()
    (bundled / "ezsort.ico").write_bytes(b"icon")

    monkeypatch.setattr(_sys, "frozen", True, raising=False)
    monkeypatch.setattr(_sys, "_MEIPASS", str(tmp_path), raising=False)

    found = app_module.app_icon_path()
    assert found == bundled / "ezsort.ico", (
        f"frozen lookup returned {found}, but the spec bundles the icon "
        f"at {bundled / 'ezsort.ico'}"
    )


def test_icon_lookup_degrades_gracefully_when_missing(tmp_path, monkeypatch):
    """No icon anywhere -> None, never an exception (app must still start)."""
    import sys as _sys
    from ezsort.gui import app as app_module

    monkeypatch.setattr(_sys, "frozen", True, raising=False)
    monkeypatch.setattr(_sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(_sys, "executable", str(tmp_path / "EzSort.exe"),
                        raising=False)

    assert app_module.app_icon_path() is None


def test_theme_switch_updates_palette_and_styles(app, pinned_config):
    from ezsort.gui.theme import apply_styles

    original = pinned_config.get("theme", "dark")
    try:
        pinned_config["theme"] = "light"
        app.palette = theme.get_palette("light")
        apply_styles(app.root, app.palette)
        _pump(app)
        assert theme.active_palette()["name"] == "light"
        for page in app.pages.values():
            page.apply_theme()
        _pump(app)
    finally:
        app.palette = theme.get_palette(original)
        apply_styles(app.root, app.palette)
        _pump(app)
    assert theme.active_palette()["name"] == original


@pytest.mark.parametrize("page_name,flex_row", [
    ("organizer", 3),
    ("history", 2),
    ("activity", 2),
])
def test_only_the_scrollable_row_flexes(app, page_name, flex_row,
                                        pinned_config):
    """A page's chrome rows must never absorb or lose height.

    Regression test: ``Page.__init__`` gives body row 0 ``weight=1``. For
    pages whose row 0 is a toolbar/chip bar that meant the row both
    swallowed spare height and was squashed first in a short window -
    clipping the Organizer's scan summary in half.
    """
    page = _show(app, page_name)
    _pump(app)
    body = page.body

    info = body.grid_rowconfigure(flex_row)
    assert info["weight"] > 0, (
        f"{page_name}: row {flex_row} should absorb the extra height"
    )
    for row_index in range(0, flex_row):
        assert body.grid_rowconfigure(row_index)["weight"] == 0, (
            f"{page_name}: body row {row_index} has weight!=0, so grid will "
            f"squash it whenever the window is short"
        )


def test_organizer_options_row_is_not_squashed_in_short_windows(app,
                                                                pinned_config):
    """The scan summary must stay readable even in a short window.

    Regression test: ``Page.__init__`` gives the body's first row weight=1,
    so in a short window grid shrank the options card along with the table
    and clipped the "N file(s) scanned | N move(s) planned" summary in half.
    Only the scrollable results table may flex.
    """
    organizer = _show(app, "organizer")
    _pump(app)
    body = organizer.body

    # The options and toolbar rows must not be flexible...
    for row_index in (0, 1):
        assert body.grid_rowconfigure(row_index)["weight"] == 0, (
            f"body row {row_index} has weight!=0, so grid will squash it "
            f"whenever the window is short"
        )
    # ...and the results table must be.
    assert body.grid_rowconfigure(3)["weight"] > 0, (
        "the results table row should absorb the extra height"
    )

    # Behavioural check: shrink the window hard and confirm the options
    # card keeps its full requested height instead of being clipped.
    original_geometry = app.root.geometry()
    try:
        app.root.geometry("1180x520")
        _pump(app, rounds=10)
        card = body.grid_slaves(row=0, column=0)[0]
        assert card.winfo_height() >= card.winfo_reqheight() - 2, (
            f"options card was squashed to {card.winfo_height()}px "
            f"(needs {card.winfo_reqheight()}px) - its content would be "
            f"clipped"
        )
    finally:
        app.root.geometry(original_geometry)
        _pump(app)


def test_shortcut_navigation_switches_pages(app):
    """Ctrl+1..6 jump between pages (bind_all needs a focused widget)."""
    app.show_page("dashboard")
    _pump(app)
    # bind_all only fires for events on the focused widget chain, and a
    # withdrawn test window has no focus by default.
    app.root.deiconify()
    try:
        app.root.focus_force()
        _pump(app)
        app.root.event_generate("<Control-Key-4>")  # Ctrl+4 -> history
        _pump(app)
        assert app.current_page == "history"

        app.root.event_generate("<Control-Key-1>")  # Ctrl+1 -> dashboard
        _pump(app)
        assert app.current_page == "dashboard"
    finally:
        app.root.withdraw()
        _pump(app)


@pytest.mark.parametrize("theme_name", ["light", "dark"])
def test_sidebar_brand_follows_theme(app, theme_name, pinned_config):
    """The brand block is plain tk widgets - it must recolor on switch.

    Regression test: ``apply_theme`` used to recolor only ttk-styled
    chrome, so the "EzSort / v0.3.0" block and the sidebar rules kept the
    previous theme's colors (a black block in light mode).
    """
    from ezsort.gui.theme import apply_styles

    previous = pinned_config.get("theme", "dark")
    try:
        app.apply_theme(theme_name)
        _pump(app)
        palette = theme.get_palette(theme_name)
        assert app.palette["name"] == theme_name

        for widget, bg_role, fg_role in app._brand_widgets:
            expected_bg = palette[bg_role]
            actual = widget.cget("bg")
            assert actual.lower() == expected_bg.lower(), (
                f"{widget} background is {actual}, expected {expected_bg} "
                f"for the {theme_name} theme"
            )
            if fg_role:
                expected_fg = palette[fg_role]
                actual_fg = widget.cget("fg")
                assert actual_fg.lower() == expected_fg.lower(), (
                    f"{widget} foreground is {actual_fg}, expected "
                    f"{expected_fg} for the {theme_name} theme"
                )

        for sep_widget in app._sidebar_separators:
            expected = palette["border"]
            actual = sep_widget.cget("bg")
            assert actual.lower() == expected.lower(), (
                f"separator is {actual}, expected {expected}"
            )
    finally:
        app.apply_theme(previous)
        _pump(app)
    assert app.palette["name"] == previous


def test_sidebar_brand_survives_repeated_theme_switches(app, pinned_config):
    """Switching back and forth must not leave stale colors behind."""
    from ezsort.gui.theme import apply_styles

    previous = pinned_config.get("theme", "dark")
    try:
        for name in ("light", "dark", "light", "dark"):
            app.apply_theme(name)
            _pump(app)
            palette = theme.get_palette(name)
            for widget, bg_role, _fg in app._brand_widgets:
                assert widget.cget("bg").lower() == palette[bg_role].lower(), (
                    f"{widget} kept a stale background after switching "
                    f"back to {name}"
                )
    finally:
        app.apply_theme(previous)
        _pump(app)
    del apply_styles  # imported for parity with other theme tests


def test_cancel_tokens_are_per_task(app):
    """A watch-mode token must never be cancellable through 'organizing'."""
    from ezsort.gui.workers import CancelToken

    token = CancelToken()
    app._cancel_tokens["watching"] = token
    try:
        # Nothing named "organizing" is running: cancel_current must not
        # touch the watch token (this was a real bug before 0.3.0).
        app.cancel_current()
        _pump(app)
        assert not token.cancelled, "cancel_current cancelled the wrong task!"
        assert app.cancel_token_for("watching") is token
        assert app.cancel_token_for("organizing") is None
    finally:
        app._cancel_tokens.pop("watching", None)


def test_start_task_refuses_while_exclusive_task_runs(app):
    """Second exclusive task is refused, not silently queued."""
    import threading
    import time

    release = threading.Event()
    results = []

    def blocker():
        release.wait(timeout=5)
        return "done"

    try:
        first = app.start_task("organizing", blocker,
                               on_done=lambda r: results.append(r))
        assert first is True
        second = app.start_task("scanning", blocker,
                                on_done=lambda r: results.append(r))
        assert second is False, "exclusive task was not refused"
        assert app.is_busy()
    finally:
        release.set()
        for _ in range(100):
            _pump(app)
            if not app.is_busy() and results:
                break
            time.sleep(0.05)
    assert results == ["done"], f"first task did not finish cleanly: {results}"
    assert not app.is_busy()


def test_organizer_partial_checkbox_is_inverted_against_config(app,
                                                              pinned_config):
    """The checkbox offers to *sort* partials; config stores 'skip'."""
    organizer = _show(app, "organizer")
    pinned_config["skip_partial_downloads"] = True
    organizer.sync_options_from_config()
    _pump(app)
    assert organizer.partial_var.get() is False, (
        "with skipping enabled the 'sort partials too' box must be "
        "unchecked"
    )

    pinned_config["skip_partial_downloads"] = False
    organizer.sync_options_from_config()
    assert organizer.partial_var.get() is True


def test_organizer_preview_invalidates_on_option_change(app):
    organizer = _show(app, "organizer")
    organizer.running = False
    organizer.preview = object()  # pretend a plan exists
    organizer.sort_btn.state(["!disabled"])
    organizer._options_changed()
    _pump(app)
    assert organizer.preview is None
    assert "disabled" in organizer.sort_btn.state()


def test_organizer_options_change_is_ignored_mid_run(app):
    organizer = _show(app, "organizer")
    fake_preview = object()
    organizer.running = True
    organizer.preview = fake_preview
    organizer._options_changed()
    assert organizer.preview is fake_preview, (
        "an executing plan must not be discarded mid-run"
    )
    organizer.running = False
    organizer.preview = None


def test_activity_chips_start_at_zero(app):
    activity = _show(app, "activity")
    activity.render_all()
    _pump(app)
    for key, (var, _label, _color) in activity.chip_vars.items():
        assert var.get() == "0", f"chip '{key}' was not reset"


def test_activity_counts_only_known_kinds(app):
    activity = _show(app, "activity")
    activity.render_all()
    _pump(app)
    activity.append_entry({"type": "moved", "message": "a"})
    activity.append_entry({"type": "moved", "message": "b"})
    activity.append_entry({"type": "failed", "message": "c"})
    activity.append_entry({"type": "error", "message": "d"})
    activity.append_entry({"type": "info", "message": "e"})
    _pump(app)
    assert activity.counts["moved"] == 2
    assert activity.counts["failed"] == 1
    assert activity.counts["error"] == 1
    # "info" is not a counter and must not leak into the chips.
    assert activity.chip_vars["moved"][0].get() == "2"
    assert activity.chip_vars["errors"][0].get() == "1"


def test_activity_cancel_button_tracks_running_task(app):
    """The cancel button is only enabled while a cancellable run exists."""
    from ezsort.gui.workers import CancelToken

    activity = _show(app, "activity")
    activity._poll_cancel_state()  # apply state immediately for the test
    _pump(app)
    assert "disabled" in activity.cancel_btn.state(), (
        "cancel must start disabled while nothing runs"
    )

    app._cancel_tokens["organizing"] = CancelToken()
    try:
        activity._poll_cancel_state()
        _pump(app)
        assert "disabled" not in activity.cancel_btn.state(), (
            "cancel must enable while a cancellable run exists"
        )
    finally:
        app._cancel_tokens.pop("organizing", None)
    activity._poll_cancel_state()
    _pump(app)
    assert "disabled" in activity.cancel_btn.state()


# ----------------------------------------------------------------------
# End-to-end: a real preview + sort through the Organizer page
# ----------------------------------------------------------------------

def _wait_until(app, predicate, timeout: float = 20.0, label: str = "condition"):
    """Pump the Tk event loop until *predicate* holds or time out."""
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        app.root.update()
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {label}")


#: Config keys the end-to-end tests toggle on the shared app instance.
MUTATED_CONFIG_KEYS = (
    "confirm_before_move", "skip_partial_downloads", "skip_hidden",
    "recursive", "duplicate_strategy", "theme",
)


@pytest.fixture
def pinned_config(app):
    """Snapshot the shared app config and restore it after the test.

    The app is module-scoped, so any config key a test flips would
    otherwise leak into every later test and make results depend on
    execution order.
    """
    saved = {key: app.config.get(key) for key in MUTATED_CONFIG_KEYS}
    try:
        yield app.config
    finally:
        for key, value in saved.items():
            if value is None:
                app.config.pop(key, None)
            else:
                app.config[key] = value
        organizer = app.pages.get("organizer")
        if organizer is not None:
            organizer.sync_options_from_config()


def test_organizer_sorts_a_real_folder_end_to_end(app, tmp_path, pinned_config):
    """Regression test: the full sort path must run without raising.

    A NameError inside the worker (``cancel_check`` referenced but not
    defined after the per-task cancel-token refactor) used to fail every
    sort with "Sorting failed". Worker exceptions surface through
    on_error, so only an end-to-end run like this catches it.
    """
    folder = tmp_path / "downloads"
    folder.mkdir()
    (folder / "photo.jpg").write_bytes(b"jpeg")
    (folder / "report.pdf").write_bytes(b"pdf")
    (folder / "notes.txt").write_bytes(b"text")
    (folder / "leftover.crdownload").write_bytes(b"partial")

    organizer = _show(app, "organizer")
    # Showing the page auto-previews the last-used folder in the
    # background; wait for that scan to release the engine before we
    # drive our own, or start_task() refuses and nothing ever appears.
    _wait_until(app, lambda: not app.is_busy(), label="auto-preview settling")
    pinned_config["confirm_before_move"] = False  # no modal dialog in tests
    # Earlier tests mutate the shared config; pin the settings this test
    # depends on so it cannot pass or fail based on execution order.
    pinned_config["skip_partial_downloads"] = True
    pinned_config["skip_hidden"] = True
    organizer.sync_options_from_config()
    errors: list[BaseException] = []

    organizer.set_folder(folder)
    _pump(app)
    organizer.preview_folder()
    _wait_until(app, lambda: organizer.preview is not None,
                label="preview completion")
    assert organizer.preview.ready == 3, (
        f"expected 3 planned moves, got {organizer.preview.ready}"
    )

    # Capture worker failures: a raised exception inside the worker goes to
    # on_error, which by default only toasts. Recording them makes the
    # NameError-style regression fail the test instead of hiding in a toast.
    real_start_task = app.start_task

    def watching_start_task(label, fn, on_done=None, on_error=None, exclusive=True):
        def wrapped_on_error(exc):
            errors.append(exc)
            if on_error:
                on_error(exc)

        return real_start_task(label, fn, on_done=on_done,
                               on_error=wrapped_on_error, exclusive=exclusive)

    app.start_task = watching_start_task
    try:
        organizer.sort_files()
        _wait_until(app, lambda: not organizer.running,
                    label="sort completion")
    finally:
        app.start_task = real_start_task

    assert not errors, f"the sort worker raised: {errors!r}"
    assert (folder / "Images" / "photo.jpg").exists(), "photo.jpg not moved"
    assert (folder / "Documents" / "report.pdf").exists(), "report.pdf not moved"
    assert (folder / "Documents" / "notes.txt").exists(), "notes.txt not moved"
    assert (folder / "leftover.crdownload").exists(), (
        "a partial download must never be moved"
    )
    # The plan is spent, so the user is asked to preview again.
    assert organizer.preview is None
    assert "disabled" in organizer.sort_btn.state()


def test_organizer_ignores_a_scan_that_lands_too_late(app, tmp_path,
                                                      pinned_config):
    """A scan started for an old folder must not overwrite a newer choice.

    Regression test: previews run on a worker thread. Picking folder B
    while folder A's scan is still running used to let A's result land
    afterwards, so the table showed a plan for a folder the user had
    already left (and Sort would have operated on the wrong folder).
    """
    folder_a = tmp_path / "folder-a"
    folder_a.mkdir()
    (folder_a / "old.pdf").write_bytes(b"pdf")
    folder_b = tmp_path / "folder-b"
    folder_b.mkdir()
    (folder_b / "new.pdf").write_bytes(b"pdf")

    organizer = _show(app, "organizer")
    # Let any auto-preview from a previous test release the engine first,
    # otherwise our own preview_folder() is refused as "busy".
    _wait_until(app, lambda: not app.is_busy(), label="auto-preview settling")
    pinned_config["confirm_before_move"] = False
    pinned_config["skip_partial_downloads"] = True
    pinned_config["skip_hidden"] = True
    organizer.sync_options_from_config()

    organizer.set_folder(folder_a)
    _pump(app)
    organizer.preview_folder()          # scan of A is now in flight

    # The user changes their mind before A's scan reports back.
    organizer.set_folder(folder_b)
    _wait_until(app, lambda: not app.is_busy(), label="scan A settling")

    assert organizer.preview is None, (
        "the stale scan for the old folder populated the table"
    )
    assert folder_a.name not in str(organizer.summary_var.get()), (
        f"summary still describes the old folder: "
        f"{organizer.summary_var.get()!r}"
    )

    # A fresh preview for the new folder still works normally.
    organizer.preview_folder()
    _wait_until(app, lambda: organizer.preview is not None,
                label="preview for folder B")
    assert organizer.preview.folder == folder_b
    assert organizer.preview.ready == 1


def test_organizer_cancel_stops_a_run_early(app, tmp_path, pinned_config):
    """Cancelling mid-run leaves the app consistent (no stuck busy state)."""
    import time

    folder = tmp_path / "many-files"
    folder.mkdir()
    for i in range(40):
        (folder / f"file{i:02d}.pdf").write_bytes(b"pdf" * 10)

    organizer = _show(app, "organizer")
    _wait_until(app, lambda: not app.is_busy(), label="auto-preview settling")
    pinned_config["confirm_before_move"] = False
    pinned_config["skip_partial_downloads"] = True
    pinned_config["skip_hidden"] = True
    organizer.sync_options_from_config()

    organizer.set_folder(folder)
    _pump(app)
    organizer.preview_folder()
    _wait_until(app, lambda: organizer.preview is not None,
                label="preview completion")
    assert organizer.preview.ready == 40

    organizer.sort_files()
    _wait_until(app, lambda: organizer.running, label="run start")
    app.cancel_current()  # requests cancellation via the per-task token
    _wait_until(app, lambda: not organizer.running, label="cancel completion",
                timeout=25.0)

    time.sleep(0.2)
    _pump(app)
    assert "disabled" in organizer.cancel_btn.state(), (
        "cancel button must return to disabled"
    )
    assert not app.is_busy(), "app must not be left busy after a cancel"
    assert app.cancel_token_for("organizing") is None, (
        "the organizing token must be released"
    )
    # Partial progress is still recorded, so nothing is silently lost.
    from ezsort.history import get_history

    history = get_history()
    assert history, "a cancelled run must still record what it moved"


# ----------------------------------------------------------------------
# Filters, scrolling and large folders
# ----------------------------------------------------------------------

def test_organizer_filter_and_search_narrow_the_table(app, tmp_path,
                                                      pinned_config):
    """Filter chips and search must hide rows without losing the plan."""
    from ezsort import engine

    folder = tmp_path / "filter-downloads"
    folder.mkdir()
    (folder / "photo.jpg").write_bytes(b"jpeg")
    (folder / "report.pdf").write_bytes(b"pdf")
    (folder / "leftover.crdownload").write_bytes(b"partial")

    organizer = _show(app, "organizer")
    _wait_until(app, lambda: not app.is_busy(), label="auto-preview settling")
    pinned_config["skip_partial_downloads"] = True
    pinned_config["skip_hidden"] = True
    organizer.sync_options_from_config()

    preview = engine.build_preview(folder, config=app.config, recursive=False)
    organizer.set_folder(folder)
    organizer.preview = preview
    organizer._populate(preview)
    _pump(app)

    assert len(organizer.tree.get_children()) == 3
    assert organizer.table_badge is not None

    organizer.filter_var.set("Moves")
    organizer._apply_filter()
    assert len(organizer.tree.get_children()) == 2
    assert "2 of 3" in organizer.table_badge.cget("text")

    organizer.filter_var.set("Skipped")
    organizer._apply_filter()
    visible = organizer.tree.get_children()
    assert len(visible) == 1
    assert "Skipped" in str(organizer.tree.item(visible[0], "values"))

    organizer.filter_var.set("All rows")
    organizer.search.set("report")
    organizer._apply_filter()
    visible = organizer.tree.get_children()
    assert len(visible) == 1
    assert "report.pdf" in str(organizer.tree.item(visible[0], "values"))

    organizer.search.clear()
    organizer._apply_filter()
    assert len(organizer.tree.get_children()) == 3


def test_activity_filter_and_search_match_entries(app):
    activity = _show(app, "activity")
    activity.render_all()
    activity.append_entry(
        {"time": "10:00:00", "type": "moved", "message": "Moved 3 files"})
    activity.append_entry(
        {"time": "10:00:01", "type": "failed", "message": "Could not move x"})
    activity.append_entry(
        {"time": "10:00:02", "type": "info", "message": "Watch mode is idle"})

    activity.filter_var.set("moved")
    activity._rebuild_text()
    text = activity.text.get("1.0", "end")
    assert "Moved 3 files" in text
    assert "Could not move x" not in text
    assert "Watch mode is idle" not in text

    activity.filter_var.set("all")
    activity.search.set("watch")
    activity._rebuild_text()
    text = activity.text.get("1.0", "end")
    assert "Watch mode is idle" in text
    assert "Moved 3 files" not in text

    activity.search.clear()
    activity._rebuild_text()
    text = activity.text.get("1.0", "end")
    assert "Moved 3 files" in text
    assert "Watch mode is idle" in text


def test_scrollable_frame_updates_its_scroll_region(app):
    """A page may bind <Configure> on the body without breaking scrolling.

    Regression test: Dashboard's ``_resize_recent`` replaced
    ScrollableFrame's own body binding (Tkinter replaces unless add="+"),
    so the scroll region stayed empty and tall content was silently
    clipped with no way to scroll.
    """
    from tkinter import ttk

    from ezsort.gui.components import ScrollableFrame

    win = tk.Toplevel(app.root)
    try:
        win.geometry("320x160+0+0")
        scroll = ScrollableFrame(win, bg_role="bg", auto_hide=True)
        scroll.pack(fill="both", expand=True)
        for index in range(60):
            ttk.Label(scroll.body, text=f"row {index}").pack(anchor="w")
        # Simulate the Dashboard's own binding (without add="+").
        scroll.body.bind("<Configure>", lambda _e: None)
        _pump(app, rounds=10)

        region = str(scroll.canvas.cget("scrollregion"))
        assert region, "the canvas never received a scroll region"
        parts = [int(float(v)) for v in region.split()]
        assert parts[3] > scroll.canvas.winfo_height(), (
            "60 rows should be taller than the 160px viewport"
        )
        assert scroll.scrollbar.winfo_ismapped(), (
            "the auto-hide scrollbar should be visible for overflowing content"
        )
    finally:
        win.destroy()


def test_ten_thousand_files_preview_and_table(app, tmp_path):
    """A 10k-file folder must plan and render without pathological slowness."""
    import time

    from ezsort import engine

    folder = tmp_path / "ten-thousand"
    folder.mkdir()
    for index in range(10_000):
        (folder / f"file{index:05d}.pdf").write_bytes(b"pdf")

    started = time.perf_counter()
    preview = engine.build_preview(folder, config=app.config, recursive=False)
    preview_seconds = time.perf_counter() - started
    assert len(preview.operations) == 10_000
    assert preview_seconds < 30.0, (
        f"planning 10k files took {preview_seconds:.1f}s"
    )

    organizer = _show(app, "organizer")
    _wait_until(app, lambda: not app.is_busy(), label="auto-preview settling")
    table = organizer.table
    table.clear()
    rows = [
        (f"file{index:05d}.pdf", "Documents", "Documents/file.pdf", "Move")
        for index in range(10_000)
    ]
    started = time.perf_counter()
    table.insert_batched(rows, batch_size=500)
    _wait_until(
        app, lambda: len(table.tree.get_children()) == 10_000,
        timeout=20.0, label="10k table rows",
    )
    table_seconds = time.perf_counter() - started
    assert table_seconds < 20.0, (
        f"inserting 10k rows took {table_seconds:.1f}s"
    )
    table.clear()
