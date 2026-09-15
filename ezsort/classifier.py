"""File classifier - determines file categories."""

from __future__ import annotations

import logging
import re
from typing import Any

from ezsort.config import get_categories
from ezsort.models import FileItem

logger = logging.getLogger(__name__)


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

    # Check custom rules first (highest priority)
    for rule in custom_rules:
        match_result = _match_custom_rule(file_item, rule)
        if match_result:
            reason = f'Custom rule matched: {rule.get("pattern", "")}'
            return match_result, reason

    # Check by extension
    ext = file_item.extension.lower()
    for category, extensions in categories.items():
        if ext in extensions:
            return category, f'Extension "{ext}" matched {category}'

    # Fallback
    return "Others", f'No category matched for extension "{ext}"'


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
        if file_item.extension.lower() == pattern.lower():
            return f"{category}/{subfolder}" if subfolder else category

    elif rule_type == "filename_contains":
        if pattern.lower() in filename:
            return f"{category}/{subfolder}" if subfolder else category

    elif rule_type == "filename_matches":
        try:
            if re.search(pattern, filename, re.IGNORECASE):
                return f"{category}/{subfolder}" if subfolder else category
        except re.error:
            logger.warning("Invalid regex pattern in custom rule: %s", pattern)

    elif rule_type == "filename_starts":
        if filename.startswith(pattern.lower()):
            return f"{category}/{subfolder}" if subfolder else category

    elif rule_type == "filename_ends":
        if filename.endswith(pattern.lower()):
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
