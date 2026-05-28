"""Validate that every SKILL_GROUP has corresponding Tips popup content.

Prevents blank tips sections when new skill groups are added to SKILL_GROUPS
but their tips content is forgotten in the Tips popup rendering.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = (
    PROJECT_ROOT / "apps" / "web" / "src" / "components" / "UARPanel.tsx"
)


def _read_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_skill_groups(src: str) -> set[str]:
    """Extract all skill group names from the SKILL_GROUPS array."""
    pattern = r'name:\s*[\'"]([^\'"]+)[\'"]'
    # Only match names inside SKILL_GROUPS array block
    start = src.find("const SKILL_GROUPS = [")
    if start == -1:
        raise RuntimeError("Could not find SKILL_GROUPS array start")
    # Find the end: first ']' that is followed by a newline and then
    # another statement (not inside a nested object)
    bracket_depth = 0
    end = start
    for i, ch in enumerate(src[start:], start=start):
        if ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth -= 1
            if bracket_depth == 0:
                end = i
                break
    block = src[start:end]
    return set(re.findall(pattern, block))


def _extract_tips_group_names(src: str) -> set[str]:
    """Extract all group names that have tips content in the popup."""
    # Match: {group.name === 'Some Name' && (
    pattern = r"\{group\.name === ['\"]([^'\"]+)['\"] && \("
    return set(re.findall(pattern, src))


class TestTipsAlignment:
    """Every skill group must have Tips popup content."""

    def test_all_skill_groups_have_tips_content(self) -> None:
        """SKILL_GROUPS names must all appear in tips popup conditions."""
        panel_src = _read_file(PANEL_PATH)

        group_names = _extract_skill_groups(panel_src)
        tips_names = _extract_tips_group_names(panel_src)

        missing = group_names - tips_names
        assert not missing, (
            f"Skill groups missing Tips popup content: {sorted(missing)}\n"
            f"Add {group_name} tips in {PANEL_PATH}"
            for group_name in sorted(missing)
        )
