"""Categories and custom classification rules - editable without JSON."""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from ezsort.gui.pages import Page
from ezsort.gui.widgets import Card, ToolTip, clear_tree, set_tree_columns

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
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        # ---- built-in categories -------------------------------------
        cat_card = Card(body, title="Built-in categories")
        cat_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        cat_card.rowconfigure(2, weight=1)
        cat_card.columnconfigure(0, weight=1)

        ttk.Label(
            cat_card, style="SurfaceMuted.TLabel", wraplength=330, justify="left",
            text="Files are matched by extension, top to bottom. "
                 "Custom rules below always win.",
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))

        tree_frame = ttk.Frame(cat_card, style="Surface.TFrame")
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.cat_tree = ttk.Treeview(
            tree_frame, columns=("Category", "Extensions"), show="headings",
            selectmode="browse", height=16,
        )
        set_tree_columns(self.cat_tree, [("Category", 120, "w"), ("Extensions", 240, "w")])
        sb = ttk.Scrollbar(tree_frame, orient="vertical",
                           command=self.cat_tree.yview, style="Vertical.TScrollbar")
        self.cat_tree.configure(yscrollcommand=sb.set)
        self.cat_tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.cat_tree.bind(
            "<<TreeviewSelect>>",
            lambda e: self._cat_tooltip(),
        )
        self._cat_tip = ToolTip(self.cat_tree, lambda: self._cat_full_text())

        # ---- custom rules ----------------------------------------------
        rule_card = Card(body, title="Custom rules")
        rule_card.grid(row=0, column=1, sticky="nsew")
        rule_card.columnconfigure(0, weight=1)
        rule_card.rowconfigure(1, weight=1)

        rule_wrap = ttk.Frame(rule_card, style="Surface.TFrame")
        rule_wrap.grid(row=1, column=0, sticky="nsew", pady=(4, 8))
        rule_wrap.columnconfigure(0, weight=1)
        rule_wrap.rowconfigure(0, weight=1)
        self.rule_tree = ttk.Treeview(
            rule_wrap, columns=("Pattern", "Type", "Destination"),
            show="headings", selectmode="browse", height=7,
        )
        set_tree_columns(self.rule_tree, [
            ("Pattern", 150, "w"), ("Type", 120, "w"), ("Destination", 160, "w"),
        ])
        rsb = ttk.Scrollbar(rule_wrap, orient="vertical",
                            command=self.rule_tree.yview, style="Vertical.TScrollbar")
        self.rule_tree.configure(yscrollcommand=rsb.set)
        self.rule_tree.grid(row=0, column=0, sticky="nsew")
        rsb.grid(row=0, column=1, sticky="ns")
        self.rule_tree.bind("<<TreeviewSelect>>", self._on_rule_select)

        # reorder / remove buttons
        actions = ttk.Frame(rule_card, style="Surface.TFrame")
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(actions, text="Remove", style="Small.TButton",
                   command=self.remove_rule).pack(side="left")
        ttk.Button(actions, text="Move up", style="Small.TButton",
                   command=lambda: self.move_rule(-1)).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Move down", style="Small.TButton",
                   command=lambda: self.move_rule(1)).pack(side="left", padx=(8, 0))

        # form
        form = ttk.Frame(rule_card, style="Surface.TFrame")
        form.grid(row=3, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="When", style="Surface.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.type_var = tk.StringVar(value=RULE_TYPES[0][1])
        type_box = ttk.Combobox(
            form, textvariable=self.type_var, state="readonly",
            values=[label for _, label in RULE_TYPES], width=18,
        )
        type_box.grid(row=0, column=1, sticky="ew", pady=3)
        type_box.current(0)

        ttk.Label(form, text="Value", style="Surface.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        self.pattern_var = tk.StringVar()
        pattern_entry = ttk.Entry(form, textvariable=self.pattern_var)
        pattern_entry.grid(row=1, column=1, sticky="ew", pady=3)

        ttk.Label(form, text="Put in", style="Surface.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=3)
        cat_row = ttk.Frame(form, style="Surface.TFrame")
        cat_row.grid(row=2, column=1, sticky="ew", pady=3)
        cat_row.columnconfigure(0, weight=1)
        self.category_var = tk.StringVar()
        ttk.Entry(cat_row, textvariable=self.category_var).grid(
            row=0, column=0, sticky="ew")
        self.subfolder_var = tk.StringVar()
        sub = ttk.Entry(cat_row, textvariable=self.subfolder_var, width=14)
        sub.grid(row=0, column=1, padx=(8, 0))
        ToolTip(sub, "Optional subfolder inside the category (e.g. Invoices)")

        btns = ttk.Frame(rule_card, style="Surface.TFrame")
        btns.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(btns, text="Add rule", style="Accent.TButton",
                   command=self.add_rule).pack(side="left")
        self.update_btn = ttk.Button(btns, text="Update selected",
                                     command=self.update_rule, state="disabled")
        self.update_btn.pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Clear form", style="Small.TButton",
                   command=self.clear_form).pack(side="left", padx=(8, 0))

        foot = ttk.Frame(rule_card, style="Surface.TFrame")
        foot.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(foot, text="Open config file", style="Small.TButton",
                   command=self.app.open_config_location).pack(side="left")
        ttk.Button(foot, text="Reload from disk", style="Small.TButton",
                   command=self.load_all).pack(side="left", padx=(8, 0))

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_all(self) -> None:
        self.app.reload_config()
        self._render_categories()
        self._render_rules()

    def _render_categories(self) -> None:
        clear_tree(self.cat_tree)
        categories = self.app.config.get("categories", {})
        from ezsort.constants import CATEGORY_ORDER

        order = [c for c in CATEGORY_ORDER if c in categories]
        order += [c for c in categories if c not in order]
        for name in order:
            exts = categories[name] or []
            preview = ", ".join(exts[:12]) + (" …" if len(exts) > 12 else "")
            self.cat_tree.insert("", "end", values=(name, preview))

    def _cat_full_text(self) -> str:
        selection = self.cat_tree.selection()
        if not selection:
            return "Select a category to see every supported extension."
        name = self.cat_tree.item(selection[0], "values")[0]
        exts = self.app.config.get("categories", {}).get(name, [])
        return f"{name} ({len(exts)} extensions):\n" + "  ".join(exts)

    def _cat_tooltip(self) -> None:
        pass  # ToolTip pulls text lazily via _cat_full_text

    # ------------------------------------------------------------------
    # Rule editing
    # ------------------------------------------------------------------

    def _render_rules(self) -> None:
        clear_tree(self.rule_tree)
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
            self.rule_tree.insert(
                "", "end", iid=str(i),
                values=(rule.get("pattern", ""), label, dest),
            )
        self.selected_index = None
        self.update_btn.state(["disabled"])

    def _on_rule_select(self, _event=None) -> None:
        selection = self.rule_tree.selection()
        if not selection:
            return
        try:
            index = int(selection[0])
            rule = self.app.config["custom_rules"][index]
        except (ValueError, IndexError, KeyError):
            return
        self.selected_index = index
        type_labels = dict(RULE_TYPES)
        label = type_labels.get(str(rule.get("type")), str(rule.get("type")))
        # Map label back to value
        for value, text in RULE_TYPES:
            if text == label:
                self.type_var.set(text)
                break
        self.pattern_var.set(str(rule.get("pattern", "")))
        self.category_var.set(str(rule.get("category", "")))
        self.subfolder_var.set(str(rule.get("subfolder", "")))
        self.update_btn.state(["!disabled"])

    def clear_form(self) -> None:
        self.pattern_var.set("")
        self.category_var.set("")
        self.subfolder_var.set("")
        self.type_var.set(RULE_TYPES[0][1])
        self.selected_index = None
        self.rule_tree.selection_remove(self.rule_tree.selection())
        self.update_btn.state(["disabled"])

    def _collect_form(self) -> dict[str, str] | None:
        """Validate the form; return a rule dict or None (toast explains)."""
        rtype_label = self.type_var.get()
        rtype = next(
            (v for v, t in RULE_TYPES if t == rtype_label), "filename_contains"
        )
        if rtype not in VALID_TYPES:
            self.app.toast("Pick a valid rule type.", "error")
            return None
        pattern = self.pattern_var.get().strip()
        if not pattern:
            self.app.toast("Enter a value to match (the 'When' field).", "warning")
            return None
        category = self.category_var.get().strip()
        if not category:
            self.app.toast("Enter a destination category (the 'Put in' field).", "warning")
            return None
        if rtype == "filename_matches":
            try:
                re.compile(pattern)
            except re.error as e:
                self.app.toast(f"Invalid regular expression: {e}", "error")
                return None
        subfolder = self.subfolder_var.get().strip()
        if "/" in category or "\\" in category:
            # Allow "Documents/Invoices" shorthand in the category field.
            parts = [p for p in category.replace("\\", "/").split("/") if p]
            category = parts[0]
            if len(parts) > 1 and not subfolder:
                subfolder = "/".join(parts[1:])
        return {
            "type": rtype,
            "pattern": pattern,
            "category": category,
            "subfolder": subfolder,
        }

    def _save_rules(self, rules: list[dict[str, Any]], message: str) -> None:
        self.app.update_config(custom_rules=rules)
        self._render_rules()
        self.app.log({"type": "info", "message": message})
        org = self.app.pages.get("organizer")
        if org is not None:
            org.preview = None  # plan may change with new rules

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
        removed = rules.pop(self.selected_index)
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

    # ------------------------------------------------------------------

    def on_show(self) -> None:
        self.load_all()

    def refresh(self) -> None:
        self.load_all()
