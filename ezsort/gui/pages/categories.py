"""Categories and custom classification rules - editable without JSON."""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from ezsort.constants import (
    CATEGORY_ORDER,
    ILLEGAL_PATH_CHARS,
    WINDOWS_RESERVED_NAMES,
)
from ezsort.gui import tokens
from ezsort.gui.components import (
    Badge,
    Card,
    ConfirmDialog,
    Dialog,
    Field,
    SearchBox,
    Table,
    ToolTip,
)
from ezsort.gui.pages import Page, sp
from ezsort.gui.theme import middle_ellipsis

if TYPE_CHECKING:  # pragma: no cover
    from ezsort.gui.app import EzSortApp

RULE_TYPES = [
    ("extension", "Extension is"),
    ("filename_contains", "Name contains"),
    ("filename_matches", "Name matches regex"),
    ("filename_starts", "Name starts with"),
    ("filename_ends", "Name ends with"),
]

VALID_TYPES = {t for t, _ in RULE_TYPES}
_EXTENSION_RE = re.compile(r"^\.[a-z0-9][a-z0-9._+-]*$")


def normalize_extensions(raw: str) -> tuple[list[str], str]:
    """Parse a user-entered extension list.

    Returns ``(extensions, error)``; ``error`` is empty on success.
    """
    tokens = [t for t in re.split(r"[\s,;]+", raw.strip()) if t]
    if not tokens:
        return [], "Enter at least one extension (for example .pdf, .docx)."
    result: list[str] = []
    for token in tokens:
        value = token.lower()
        if not value.startswith("."):
            value = "." + value
        if ".." in value or not _EXTENSION_RE.match(value):
            return [], f"'{token}' is not a valid extension."
        if value not in result:
            result.append(value)
    return result, ""


def summarize_extensions(extensions: list[str], max_chars: int = 34) -> str:
    """Summarise an extension list without cutting an extension in half."""
    if not extensions:
        return ""
    shown: list[str] = []
    for index, ext in enumerate(extensions):
        remaining = len(extensions) - index - 1
        suffix = f" +{remaining}" if remaining else ""
        candidate = ", ".join([*shown, ext])
        if shown and len(candidate) + len(suffix) > max_chars:
            break
        shown.append(ext)
    hidden = len(extensions) - len(shown)
    text = ", ".join(shown)
    if hidden:
        text += f" +{hidden}"
    if len(text) > max_chars:
        text = text[:max_chars - 3] + "..."
    return text


def validate_category_name(name: str, existing: list[str]) -> str:
    """Return an error message, or an empty string when the name is usable."""
    value = name.strip()
    if not value:
        return "Enter a category name."
    if len(value) > 60:
        return "Keep the category name under 60 characters."
    if any(ch in ILLEGAL_PATH_CHARS or ch in "\\/" for ch in value):
        return "A category name cannot contain \\ / : * ? \" < > |."
    if value.endswith(".") or value.startswith("."):
        return "A category name cannot start or end with a dot."
    if value.lower() in WINDOWS_RESERVED_NAMES:
        return f"'{value}' is a reserved Windows name."
    if value in existing:
        return "A category with that name already exists."
    return ""


class CategoryDialog(Dialog):
    """Create or edit a category's extension list."""

    def __init__(self, app, title: str, name: str = "",
                 extensions: list[str] | None = None,
                 existing: list[str] | None = None):
        super().__init__(app, title, width=560)
        self._existing = existing or []
        self._editing = bool(name)
        self.values: tuple[str, list[str]] | None = None

        self.name_field = Field(
            self.body, "Category name",
            hint="Used as the folder name inside the sorted folder.",
        )
        self.name_field.grid(row=0, column=0, sticky="ew")
        self.name_field.var.set(name)
        if self._editing:
            self.name_field.entry.state(["disabled"])

        self.ext_field = Field(
            self.body, "Extensions",
            hint="Comma or space separated. Compound endings such as .tar.gz work too.",
        )
        self.ext_field.grid(row=1, column=0, sticky="ew", pady=(sp("md"), 0))
        self.ext_field.var.set(", ".join(extensions or []))

        ttk.Label(
            self.body,
            text="Matching is case-insensitive. The first category that claims "
                 "an extension wins.",
            style="Muted.TLabel", wraplength=480, justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(sp("md"), 0))

        self.add_secondary("Cancel")
        self.add_primary("Save category")
        self._center()

    def confirm(self) -> None:
        name = self.name_field.var.get().strip()
        extensions, error = normalize_extensions(self.ext_field.var.get())
        if self._editing:
            name_error = ""
        else:
            name_error = validate_category_name(name, self._existing)
        if name_error:
            self.name_field.set_error(name_error)
        else:
            self.name_field.clear_state(
                "Used as the folder name inside the sorted folder.")
        if error:
            self.ext_field.set_error(error)
        else:
            self.ext_field.clear_state(
                "Comma or space separated. Compound endings such as .tar.gz work too.")
        if name_error or error:
            return
        self.values = (name, extensions)
        super().confirm()


class CategoriesPage(Page):
    def __init__(self, app: "EzSortApp", parent):
        super().__init__(
            app, parent,
            "Categories & Rules",
            "See how files are classified and manage your own rules - no JSON editing needed.",
        )
        self.selected_index: int | None = None
        self._build()
        self.load_all()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        body = self.body
        body.columnconfigure(0, weight=2, uniform="cats")
        body.columnconfigure(1, weight=3, uniform="cats")
        body.rowconfigure(0, weight=1)

        # ---- built-in categories -------------------------------------
        cat_card = Card(body, title="Categories")
        cat_card.grid(row=0, column=0, sticky="nsew", padx=(0, sp("md")))
        cat_card.body.rowconfigure(2, weight=1)
        self.cat_badge = Badge(cat_card.header, "0", "muted")
        self.cat_badge.grid(row=0, column=1, sticky="e")

        cat_help = ttk.Label(
            cat_card.body, style="SurfaceMuted.TLabel", justify="left",
            wraplength=360,
            text="Files are matched by extension, top to bottom. "
                 "Custom rules always win.",
        )
        cat_help.grid(row=0, column=0, sticky="w", pady=(0, sp("sm")))
        self._bind_wrap(cat_help, cat_card.body)

        self.cat_search = SearchBox(
            cat_card.body, placeholder="Filter categories…", width=24,
            on_change=lambda _t: self._apply_cat_filter(),
        )
        self.cat_search.grid(row=1, column=0, sticky="ew", pady=(0, sp("sm")))

        self.cat_table = Table(
            cat_card.body,
            columns=[
                ("Category", "Category", 150, "w"),
                ("Extensions", "Extensions", 210, "w"),
            ],
            height=10,
            empty_text="No categories match this filter.",
        )
        self.cat_table.grid(row=2, column=0, sticky="nsew")
        self.cat_tree = self.cat_table.tree
        self.cat_tree.bind("<<TreeviewSelect>>",
                           lambda e: self._sync_category_actions(), add="+")

        cat_actions = ttk.Frame(cat_card.body, style="Surface.TFrame")
        cat_actions.grid(row=3, column=0, sticky="ew", pady=(sp("sm"), 0))
        self.add_cat_btn = ttk.Button(
            cat_actions, text="Add category", style="Small.TButton",
            command=self.add_category)
        self.add_cat_btn.pack(side="left")
        self.edit_cat_btn = ttk.Button(
            cat_actions, text="Edit", style="Small.TButton",
            command=self.edit_category, state="disabled",
        )
        self.edit_cat_btn.pack(side="left", padx=(sp("sm"), 0))
        self.remove_cat_btn = ttk.Button(
            cat_actions, text="Remove", style="Small.TButton",
            command=self.remove_category, state="disabled",
        )
        self.remove_cat_btn.pack(side="left", padx=(sp("sm"), 0))
        cat_actions.bind("<Configure>", self._fit_cat_actions)

        # ---- custom rules ----------------------------------------------
        rule_card = Card(body, title="Custom rules")
        rule_card.grid(row=0, column=1, sticky="nsew")
        self.rule_badge = Badge(rule_card.header, "0", "muted")
        self.rule_badge.grid(row=0, column=1, sticky="e")

        rule_help = ttk.Label(
            rule_card.body, style="SurfaceMuted.TLabel", justify="left",
            wraplength=520,
            text="Rules run top to bottom and the first match wins. "
                 "Use Move up / Move down to change priority.",
        )
        rule_help.grid(row=0, column=0, sticky="w", pady=(0, sp("sm")))
        self._bind_wrap(rule_help, rule_card.body)

        rule_wrap = ttk.Frame(rule_card.body, style="Surface.TFrame")
        rule_wrap.grid(row=1, column=0, sticky="nsew")
        rule_wrap.columnconfigure(0, weight=1)
        rule_wrap.rowconfigure(0, weight=1)
        rule_card.body.rowconfigure(1, weight=1)
        self.rule_table = Table(
            rule_wrap,
            columns=[
                ("Priority", "#", 44, "center"),
                ("Pattern", "Value", 150, "w"),
                ("Type", "When", 130, "w"),
                ("Destination", "Destination", 170, "w"),
            ],
            height=5,
            empty_text="No custom rules yet - add one below.",
        )
        self.rule_table.grid(row=0, column=0, sticky="nsew")
        self.rule_tree = self.rule_table.tree
        self.rule_tree.bind("<<TreeviewSelect>>", self._on_rule_select)

        actions = ttk.Frame(rule_card.body, style="Surface.TFrame")
        actions.grid(row=2, column=0, sticky="ew", pady=(sp("sm"), sp("md")))
        self.remove_btn = ttk.Button(
            actions, text="Remove rule", style="Small.TButton",
            command=self.remove_rule, state="disabled",
        )
        self.remove_btn.pack(side="left")
        self.up_btn = ttk.Button(
            actions, text="Move up", style="Small.TButton",
            command=lambda: self.move_rule(-1), state="disabled",
        )
        self.up_btn.pack(side="left", padx=(sp("sm"), 0))
        self.down_btn = ttk.Button(
            actions, text="Move down", style="Small.TButton",
            command=lambda: self.move_rule(1), state="disabled",
        )
        self.down_btn.pack(side="left", padx=(sp("sm"), 0))

        # form
        form = ttk.Frame(rule_card.body, style="Alt.TFrame", padding=sp("md"))
        form.grid(row=3, column=0, sticky="ew")
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        form_header = ttk.Frame(form, style="Alt.TFrame")
        form_header.grid(row=0, column=0, columnspan=2, sticky="ew",
                         pady=(0, sp("sm")))
        form_header.columnconfigure(0, weight=1)
        self.form_title = ttk.Label(
            form_header, text="Rule editor", style="Alt.TLabel",
            font=("Segoe UI", 10, "bold"))
        self.form_title.grid(row=0, column=0, sticky="w")
        btns = ttk.Frame(form_header, style="Alt.TFrame")
        btns.grid(row=0, column=1, sticky="e")
        self.add_btn = ttk.Button(
            btns, text="Add rule", style="SmallAccent.TButton",
            command=self.add_rule,
        )
        self.add_btn.pack(side="left")
        self.update_btn = ttk.Button(
            btns, text="Update selected", style="Small.TButton",
            command=self.update_rule, state="disabled",
        )
        self.update_btn.pack(side="left", padx=(sp("sm"), 0))
        self.clear_btn = ttk.Button(
            btns, text="Clear form", style="Small.TButton",
            command=self.clear_form)
        self.clear_btn.pack(side="left", padx=(sp("sm"), 0))
        form_header.bind("<Configure>", self._fit_form_actions)

        type_row = ttk.Frame(form, style="Alt.TFrame")
        type_row.grid(row=1, column=0, columnspan=2, sticky="ew")
        type_row.columnconfigure(1, weight=1)
        ttk.Label(type_row, text="When", style="Alt.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, sp("sm")))
        self.type_var = tk.StringVar(value=RULE_TYPES[0][1])
        type_box = ttk.Combobox(
            type_row, textvariable=self.type_var, state="readonly",
            values=[label for _, label in RULE_TYPES], width=20,
        )
        type_box.grid(row=0, column=1, sticky="w")

        self.pattern_field = Field(form, "Value")
        self.pattern_field.grid(row=2, column=0, sticky="ew",
                                pady=(sp("sm"), 0), padx=(0, sp("sm")))
        self.category_field = Field(form, "Destination")
        self.category_field.grid(row=2, column=1, sticky="ew",
                                 pady=(sp("sm"), 0))
        self.subfolder_field = Field(form, "Subfolder (optional)")
        self.subfolder_field.grid(row=3, column=0, sticky="ew",
                                  pady=(sp("sm"), 0), padx=(0, sp("sm")))

        foot = ttk.Frame(rule_card.body, style="Surface.TFrame")
        foot.grid(row=4, column=0, sticky="ew", pady=(sp("sm"), 0))
        ttk.Button(foot, text="Open config folder", style="Small.TButton",
                   command=self.app.open_config_location).pack(side="left")
        ttk.Button(foot, text="Reload from disk", style="Small.TButton",
                   command=self.load_all).pack(side="left", padx=(sp("sm"), 0))

    def _bind_wrap(self, label, container) -> None:
        """Keep helper text wrapped to the card's real width."""
        def fit(event):
            try:
                label.configure(wraplength=max(sp("xxl") * 5,
                                               int(event.width) - sp("xs")))
            except tk.TclError:  # pragma: no cover - destroyed
                pass
        container.bind("<Configure>", fit, add="+")

    def _fit_cat_actions(self, event) -> None:
        compact = int(event.width) < tokens.sc(300)
        if compact == getattr(self, "_cat_compact", None):
            return
        self._cat_compact = compact
        self.add_cat_btn.configure(
            text="Add" if compact else "Add category",
            style="Compact.TButton" if compact else "Small.TButton",
            width=0 if compact else "")
        for button in (self.edit_cat_btn, self.remove_cat_btn):
            button.configure(style="Compact.TButton" if compact
                             else "Small.TButton",
                             width=0 if compact else "")
            button.pack_configure(padx=(sp("xs") if compact else sp("sm"), 0))

    def _fit_form_actions(self, event) -> None:
        compact = int(event.width) < tokens.sc(440)
        if compact == getattr(self, "_form_compact", None):
            return
        self._form_compact = compact
        self.form_title.configure(text="Rule" if compact else "Rule editor")
        self.add_btn.configure(
            text="Add" if compact else "Add rule",
            style="CompactAccent.TButton" if compact
            else "SmallAccent.TButton",
            width=0 if compact else "")
        self.update_btn.configure(
            text="Update" if compact else "Update selected",
            style="Compact.TButton" if compact else "Small.TButton",
            width=0 if compact else "")
        self.clear_btn.configure(
            text="Clear" if compact else "Clear form",
            style="Compact.TButton" if compact else "Small.TButton",
            width=0 if compact else "")

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_all(self) -> None:
        self.app.reload_config()
        self._render_categories()
        self._render_rules()

    def _render_categories(self) -> None:
        self.cat_table.clear()
        categories = self.app.config.get("categories", {})
        order = [c for c in CATEGORY_ORDER if c in categories]
        order += [c for c in categories if c not in order]
        self._cat_order = order
        for i, name in enumerate(order):
            exts = categories[name] or []
            preview = summarize_extensions(exts, max_chars=22)
            self.cat_table.insert_row(
                (middle_ellipsis(name, 26), preview),
                tags=(*self._row_tag(i),),
                iid=name,
                cell_text={"Extensions": ", ".join(exts)},
            )
        self.cat_badge.set(f"{len(order)} categories", "neutral")
        self._apply_cat_filter()
        self._sync_category_actions()

    @staticmethod
    def _row_tag(index: int) -> tuple[str, ...]:
        return ("odd",) if index % 2 else ()

    def _apply_cat_filter(self) -> None:
        query = self.cat_search.value().lower()
        visible = 0
        for name in getattr(self, "_cat_order", []):
            exts = " ".join(self.app.config.get("categories", {}).get(name, []))
            match = not query or query in name.lower() or query in exts.lower()
            try:
                if match:
                    self.cat_tree.reattach(name, "", "end")
                    visible += 1
                else:
                    self.cat_tree.detach(name)
            except tk.TclError:
                pass
        self.cat_badge.set(
            f"{visible} of {len(getattr(self, '_cat_order', []))} categories"
            if query else f"{len(getattr(self, '_cat_order', []))} categories",
            "neutral")

    def _selected_category(self) -> str | None:
        selection = self.cat_tree.selection()
        return str(selection[0]) if selection else None

    def _sync_category_actions(self) -> None:
        selected = self._selected_category()
        for button in (self.edit_cat_btn, self.remove_cat_btn):
            button.state(["!disabled"] if selected else ["disabled"])

    # ------------------------------------------------------------------
    # Category editing
    # ------------------------------------------------------------------

    def _save_categories(self, categories: dict[str, list[str]],
                         message: str) -> None:
        self.app.update_config(categories=categories, quiet=True)
        self._render_categories()
        self.app.log({"type": "info", "message": message})
        self.app.toast(message, "success")
        self._invalidate_plans()

    def add_category(self) -> None:
        existing = list(self.app.config.get("categories", {}))
        dialog = CategoryDialog(self.app, "Add category", existing=existing)
        if not dialog.show() or not dialog.values:
            return
        name, extensions = dialog.values
        categories = dict(self.app.config.get("categories", {}))
        categories[name] = extensions
        self._save_categories(categories, f"Added category {name}.")

    def edit_category(self) -> None:
        name = self._selected_category()
        if not name:
            self.app.toast("Select a category first.", "info")
            return
        categories = dict(self.app.config.get("categories", {}))
        if name not in categories:
            self.app.toast("That category no longer exists - reload the page.",
                           "error")
            return
        dialog = CategoryDialog(
            self.app, f"Edit {name}", name=name,
            extensions=list(categories.get(name, [])),
        )
        if not dialog.show() or not dialog.values:
            return
        _name, extensions = dialog.values
        categories[name] = extensions
        self._save_categories(categories, f"Updated extensions for {name}.")

    def remove_category(self) -> None:
        name = self._selected_category()
        if not name:
            self.app.toast("Select a category first.", "info")
            return
        categories = dict(self.app.config.get("categories", {}))
        if name not in categories:
            self.app.toast("That category no longer exists - reload the page.",
                           "error")
            return
        if len(categories) <= 1:
            self.app.toast("Keep at least one category.", "warning")
            return
        dialog = ConfirmDialog(
            self.app, f"Remove {name}?",
            "Files with these extensions will fall through to the next "
            "matching category (usually Others).",
            details=f"{name}: {len(categories.get(name, []))} extension(s)",
            confirm_label="Remove category", danger=True,
        )
        if not dialog.show():
            return
        categories.pop(name, None)
        self._save_categories(categories, f"Removed category {name}.")

    def _invalidate_plans(self) -> None:
        org = self.app.pages.get("organizer")
        if org is not None:
            org.preview = None
        dash = self.app.pages.get("dashboard")
        if dash is not None:
            dash.preview = None

    # ------------------------------------------------------------------
    # Rule editing
    # ------------------------------------------------------------------

    def _render_rules(self) -> None:
        self.rule_table.clear()
        rules = self.app.config.get("custom_rules", [])
        type_labels = dict(RULE_TYPES)
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            rtype = str(rule.get("type", ""))
            label = type_labels.get(rtype, rtype)
            dest = str(rule.get("category", "Others"))
            if rule.get("subfolder"):
                dest += f"/{rule['subfolder']}"
            self.rule_table.insert_row(
                (str(i + 1), middle_ellipsis(str(rule.get("pattern", "")), 34),
                 middle_ellipsis(label, 24), middle_ellipsis(dest, 34)),
                tags=(*self._row_tag(i),),
                iid=str(i),
            )
        self.rule_badge.set(f"{len(rules)} rule(s)", "neutral")
        self.selected_index = None
        self._sync_rule_actions()

    def _sync_rule_actions(self) -> None:
        index = self.selected_index
        count = len(self.app.config.get("custom_rules", []))
        self.update_btn.state(["!disabled"] if index is not None else ["disabled"])
        self.remove_btn.state(["!disabled"] if index is not None else ["disabled"])
        self.up_btn.state(
            ["!disabled"] if index is not None and index > 0 else ["disabled"])
        self.down_btn.state(
            ["!disabled"] if index is not None and index < count - 1
            else ["disabled"])

    def _on_rule_select(self, _event=None) -> None:
        selection = self.rule_tree.selection()
        if not selection:
            self.selected_index = None
            self._sync_rule_actions()
            return
        try:
            index = int(selection[0])
            rule = self.app.config["custom_rules"][index]
        except (ValueError, IndexError, KeyError):
            return
        self.selected_index = index
        type_labels = dict(RULE_TYPES)
        label = type_labels.get(str(rule.get("type")), str(rule.get("type")))
        self.type_var.set(label)
        self.pattern_field.var.set(str(rule.get("pattern", "")))
        self.category_field.var.set(str(rule.get("category", "")))
        self.subfolder_field.var.set(str(rule.get("subfolder", "")))
        self._clear_field_errors()
        self._sync_rule_actions()

    def clear_form(self) -> None:
        self.pattern_field.var.set("")
        self.category_field.var.set("")
        self.subfolder_field.var.set("")
        self.type_var.set(RULE_TYPES[0][1])
        self._clear_field_errors()
        self.selected_index = None
        self.rule_tree.selection_remove(self.rule_tree.selection())
        self._sync_rule_actions()

    def _clear_field_errors(self) -> None:
        self.pattern_field.clear_state()
        self.category_field.clear_state()
        self.subfolder_field.clear_state()

    def _collect_form(self) -> dict[str, str] | None:
        """Validate the form; return a rule dict or None (errors are inline)."""
        rtype_label = self.type_var.get()
        rtype = next(
            (v for v, t in RULE_TYPES if t == rtype_label), "filename_contains"
        )
        self._clear_field_errors()
        ok = True
        if rtype not in VALID_TYPES:
            self.app.toast("Pick a valid rule type.", "error")
            return None

        pattern = self.pattern_field.var.get().strip()
        if not pattern:
            self.pattern_field.set_error("Enter a value to match.")
            ok = False
        elif rtype == "filename_matches":
            try:
                re.compile(pattern)
            except re.error as e:
                self.pattern_field.set_error(f"Invalid regular expression: {e}")
                ok = False
        elif rtype == "extension":
            exts, error = normalize_extensions(pattern)
            if error:
                self.pattern_field.set_error(error)
                ok = False
            else:
                pattern = exts[0]

        category = self.category_field.var.get().strip()
        if not category:
            self.category_field.set_error("Enter a destination category.")
            ok = False
        else:
            parts = [p for p in category.replace("\\", "/").split("/") if p]
            if not parts:
                self.category_field.set_error("Enter a destination category.")
                ok = False
            else:
                category = parts[0]
                subfolder = self.subfolder_field.var.get().strip()
                if len(parts) > 1 and not subfolder:
                    subfolder = "/".join(parts[1:])
                    self.subfolder_field.var.set(subfolder)
                name_error = ""
                if any(ch in ILLEGAL_PATH_CHARS for ch in category):
                    name_error = "Remove characters such as : * ? \" < > |."
                if name_error:
                    self.category_field.set_error(name_error)
                    ok = False
        if not ok:
            return None
        return {
            "type": rtype,
            "pattern": pattern,
            "category": category,
            "subfolder": self.subfolder_field.var.get().strip(),
        }

    def _save_rules(self, rules: list[dict[str, Any]], message: str) -> None:
        self.app.update_config(custom_rules=rules, quiet=True)
        self._render_rules()
        self.app.log({"type": "info", "message": message})
        self._invalidate_plans()

    def add_rule(self) -> None:
        rule = self._collect_form()
        if rule is None:
            return
        rules = list(self.app.config.get("custom_rules", []))
        rules.append(rule)
        self._save_rules(rules, f"Added rule: {rule['pattern']} -> {rule['category']}")
        self.clear_form()
        self.app.toast("Rule added.", "success")

    def update_rule(self) -> None:
        if self.selected_index is None:
            self.app.toast("Select a rule first.", "info")
            return
        rule = self._collect_form()
        if rule is None:
            return
        rules = list(self.app.config.get("custom_rules", []))
        if not 0 <= self.selected_index < len(rules):
            self.app.toast("That rule no longer exists - reload the page.", "error")
            return
        rules[self.selected_index] = rule
        self._save_rules(rules, f"Updated rule: {rule['pattern']} -> {rule['category']}")
        self.app.toast("Rule updated.", "success")

    def remove_rule(self) -> None:
        if self.selected_index is None:
            self.app.toast("Select a rule first.", "info")
            return
        rules = list(self.app.config.get("custom_rules", []))
        if not 0 <= self.selected_index < len(rules):
            self.app.toast("That rule no longer exists - reload the page.", "error")
            return
        removed = rules[self.selected_index]
        dialog = ConfirmDialog(
            self.app, "Remove this rule?",
            "Files that matched it will be classified by the remaining rules.",
            details=(f"{removed.get('pattern', '')}  →  "
                     f"{removed.get('category', '')}"),
            confirm_label="Remove rule", danger=True,
        )
        if not dialog.show():
            return
        rules.pop(self.selected_index)
        self._save_rules(
            rules,
            f"Removed rule: {removed.get('pattern', '')} -> {removed.get('category', '')}",
        )
        self.clear_form()
        self.app.toast("Rule removed.", "success")

    def move_rule(self, delta: int) -> None:
        if self.selected_index is None:
            self.app.toast("Select a rule first.", "info")
            return
        rules = list(self.app.config.get("custom_rules", []))
        i = self.selected_index
        j = i + delta
        if not (0 <= i < len(rules) and 0 <= j < len(rules)):
            return
        rules[i], rules[j] = rules[j], rules[i]
        self._save_rules(rules, "Rule order changed.")
        # Keep selection on the moved rule
        self.selected_index = j
        iid = str(j)
        if self.rule_tree.exists(iid):
            self.rule_tree.selection_set(iid)
            self.rule_tree.see(iid)
            self._on_rule_select()
        self.app.toast("Rule priority updated.", "success")

    # ------------------------------------------------------------------

    def on_show(self) -> None:
        self.load_all()

    def refresh(self) -> None:
        self.load_all()

    def escape(self) -> None:
        if self.cat_search.value():
            self.cat_search.clear()

    def apply_theme(self) -> None:
        self.cat_table.apply_theme(self.app.palette)
        self.rule_table.apply_theme(self.app.palette)
        super().apply_theme()
