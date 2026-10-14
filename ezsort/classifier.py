"""File classifier - determines file categories."""

from __future__ import annotations

import logging
import re
from typing import Any

from ezsort.config import get_categories
from ezsort.models import FileItem

logger = logging.getLogger(__name__)


def _build_extension_index(categories: dict[str, list[str]]) -> dict[str, str]:
    """Flatten category -> extensions into one extension -> category map.

    The first category that claims an extension wins, which mirrors the
    order categories are defined in.
    """
    index: dict[str, str] = {}
    for category, extensions in categories.items():
        for ext in extensions:
            index.setdefault(str(ext).lower(), category)
    return index


def _candidate_suffixes(filename: str) -> list[str]:
    """All dot-based suffixes of *filename*, longest first.

    ``backup.tar.gz`` -> ``[".tar.gz", ".gz"]`` so compound extensions
    configured as ``.tar.gz`` actually match.
    """
    name = filename.lower()
    # "backup.tar.gz" -> parts ["backup", "tar", "gz"] -> ".tar.gz", ".gz"
    results: list[str] = []
    parts = name.split(".")
    for i in range(1, len(parts)):
        if parts[i]:
            results.append("." + ".".join(parts[i:]))
    return results


def classify_file(
    file_item: FileItem,
    config: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Classify a file into a category.

    Args:
        file_item: The file to classify.
        config: Optional configuration dictionary.

    Returns:
        Tuple of (category, reason).
    """
    categories = get_categories(config)
    custom_rules = (config or {}).get("custom_rules", [])
    if not isinstance(custom_rules, list):
        custom_rules = []

    # Check custom rules first (highest priority)
    for rule in custom_rules:
        if not isinstance(rule, dict):
            continue
        match_result = _match_custom_rule(file_item, rule)
        if match_result:
            reason = f'Custom rule matched: {rule.get("pattern", "")}'
            return match_result, reason

    # Check by extension (compound suffixes such as ".tar.gz" first)
    index = _build_extension_index(categories)
    filename = file_item.path.name
    ext = file_item.extension.lower() or (filename.rsplit(".", 1)[-1].lower()
                                          if "." in filename else "")

    for suffix in _candidate_suffixes(filename):
        if suffix in index:
            return index[suffix], f'Extension "{suffix}" matched {index[suffix]}'

    # Single-extension fallback (covers weird names without extra dots)
    if ext and f".{ext}" in index:
        category = index[f".{ext}"]
        return category, f'Extension ".{ext}" matched {category}'

    # Fallback
    display = file_item.extension or (f".{ext}" if ext else "(none)")
    return "Others", f'No category matched for extension "{display}"'


def _match_custom_rule(file_item: FileItem, rule: dict[str, Any]) -> str | None:
    """Check if a file matches a custom rule.

    Returns the target category + subfolder path, or None.
    """
    rule_type = rule.get("type", "")
    pattern = rule.get("pattern", "")
    category = rule.get("category", "Others")
    subfolder = rule.get("subfolder", "")

    if not pattern or not category:
        return None

    filename = file_item.path.name.lower()

    if rule_type == "extension":
        wanted = str(pattern).lower()
        if not wanted.startswith("."):
            wanted = f".{wanted}"
        # Compare against every suffix so ".gz" rules match "x.tar.gz" too.
        if any(wanted == s for s in _candidate_suffixes(filename)):
            return f"{category}/{subfolder}" if subfolder else category
        if file_item.extension.lower() == wanted:
            return f"{category}/{subfolder}" if subfolder else category

    elif rule_type == "filename_contains":
        if str(pattern).lower() in filename:
            return f"{category}/{subfolder}" if subfolder else category

    elif rule_type == "filename_matches":
        try:
            if re.search(str(pattern), filename, re.IGNORECASE):
                return f"{category}/{subfolder}" if subfolder else category
        except re.error:
            logger.warning("Invalid regex pattern in custom rule: %s", pattern)

    elif rule_type == "filename_starts":
        if filename.startswith(str(pattern).lower()):
            return f"{category}/{subfolder}" if subfolder else category

    elif rule_type == "filename_ends":
        if filename.endswith(str(pattern).lower()):
            return f"{category}/{subfolder}" if subfolder else category

    return None


def classify_batch(
    files: list[FileItem],
    config: dict[str, Any] | None = None,
) -> list[tuple[FileItem, str, str]]:
    """Classify a batch of files.

    Returns:
        List of (file_item, category, reason) tuples.
    """
    results = []
    for item in files:
        category, reason = classify_file(item, config)
        results.append((item, category, reason))
        logger.debug("Classified %s as %s: %s", item.path.name, category, reason)
    return results
