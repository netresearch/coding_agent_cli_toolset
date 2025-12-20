"""
Output rendering and formatting.

Phase 2.0: Detection and Auditing - Rendering
"""

import os
import sys
from typing import Any


# Environment options
USE_EMOJI = os.environ.get("CLI_AUDIT_EMOJI", "1") == "1"
ENABLE_LINKS = os.environ.get("CLI_AUDIT_LINKS", "1") == "1"
USE_COLOR = os.environ.get("CLI_AUDIT_COLOR", "1") == "1"

# ANSI color codes
GREEN = "\033[32m"
BOLD_GREEN = "\033[1;32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RED = "\033[31m"
RESET = "\033[0m"


def status_icon(status: str, installed: str) -> str:
    """Get status icon for a tool.

    Args:
        status: Status string (UP-TO-DATE, OUTDATED, NOT INSTALLED, UNKNOWN, CONFLICT)
        installed: Installed version string

    Returns:
        Status icon string
    """
    if not USE_EMOJI:
        if installed == "X" or installed == "" or status == "NOT INSTALLED":
            return "x"
        if status == "UP-TO-DATE":
            return "✓"
        if status == "OUTDATED":
            return "↑"
        if status == "CONFLICT":
            return "⚠"
        return "?"

    # Emoji icons (using consistent single-width Unicode)
    if installed == "X" or installed == "" or status == "NOT INSTALLED":
        return "❌"
    if status == "UP-TO-DATE":
        return "✅"
    if status == "OUTDATED":
        return "⬆"  # Single-width arrow without variation selector
    if status == "CONFLICT":
        return "⚠️"
    return "❓"


def colorize(text: str, color: str) -> str:
    """Apply color to text.

    Args:
        text: Text to colorize
        color: ANSI color code

    Returns:
        Colored text or plain text if colors disabled
    """
    if not USE_COLOR or not text:
        return text
    return f"{color}{text}{RESET}"


def osc8(url: str, text: str) -> str:
    """Create OSC8 hyperlink.

    Args:
        url: Link URL
        text: Display text

    Returns:
        Hyperlinked text or plain text if links disabled
    """
    if not ENABLE_LINKS or not url:
        return text

    # OSC 8 hyperlink format
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


GROUP_BY_CATEGORY = os.environ.get("CLI_AUDIT_GROUP", "1") == "1"

# Category display info
CATEGORY_ORDER = {
    "python": 1, "node": 2, "go": 3, "rust": 4, "ruby": 5, "php": 6, "shell": 7,
    "git": 10, "devops": 11, "platform": 12, "ai": 13, "general": 20,
}
CATEGORY_ICON = {
    "python": "🐍", "node": "📦", "go": "🔵", "rust": "🦀", "ruby": "💎", "php": "🐘", "shell": "🐚",
    "git": "📝", "devops": "🔧", "platform": "☁️", "ai": "🤖", "general": "🔨",
}
CATEGORY_DESC = {
    "python": "Python Development",
    "node": "Node.js Development",
    "go": "Go Development",
    "rust": "Rust Development",
    "ruby": "Ruby Development",
    "php": "PHP Development",
    "shell": "Shell Scripting",
    "git": "Git & Version Control",
    "devops": "DevOps & Infrastructure",
    "platform": "Platform CLIs",
    "ai": "AI & LLM Tools",
    "general": "General CLI Utilities",
}


def render_table(tools: list[dict[str, Any]], show_hints: bool = False) -> None:
    """Render tools as pipe-delimited table, optionally grouped by category.

    Args:
        tools: List of tool dictionaries
        show_hints: Whether to show installation hints
    """
    from .catalog import ToolCatalog

    # Header
    headers = ("state", "tool", "installed", "latest_upstream")
    print("|".join(headers))

    # Load catalog for pinned versions
    catalog = ToolCatalog()

    # Group tools by category if enabled
    if GROUP_BY_CATEGORY:
        categorized: dict[str, list[dict[str, Any]]] = {}
        for tool in tools:
            cat = tool.get("category", "general")
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(tool)

        # Sort categories by order
        sorted_cats = sorted(categorized.keys(), key=lambda c: CATEGORY_ORDER.get(c, 99))

        for cat in sorted_cats:
            cat_tools = categorized[cat]
            icon = CATEGORY_ICON.get(cat, "📦")
            desc = CATEGORY_DESC.get(cat, cat)
            print(f"# {icon} {desc} ({len(cat_tools)} tools)", file=sys.stderr)
            for tool in cat_tools:
                _render_tool_row(tool, catalog, show_hints)
    else:
        for tool in tools:
            _render_tool_row(tool, catalog, show_hints)


def _render_tool_row(tool: dict[str, Any], catalog: Any, show_hints: bool) -> None:
    """Render a single tool row."""
    name = tool.get("tool", "")
    installed = tool.get("installed", "")
    latest = tool.get("latest_upstream", "")
    status = tool.get("status", "UNKNOWN")
    tool_url = tool.get("tool_url", "")
    latest_url = tool.get("latest_url", "")

    # Icon
    icon = status_icon(status, installed)

    # Determine colors based on status
    if status == "UP-TO-DATE":
        inst_color = GREEN
        latest_color = GREEN
    elif status == "OUTDATED":
        inst_color = YELLOW
        latest_color = BOLD_GREEN  # Latest is newer, make it bold green
    elif status == "CONFLICT":
        inst_color = YELLOW
        latest_color = BOLD_GREEN
    else:  # NOT INSTALLED, UNKNOWN
        inst_color = BLUE
        latest_color = BLUE

    # Hyperlinks
    name_display = osc8(tool_url, name) if tool_url else name

    # Apply colors to installed and latest (before adding markers/hints)
    installed_display = colorize(installed, inst_color)
    latest_display = colorize(latest, latest_color)

    # Apply hyperlinks (after colorization, hyperlinks wrap the colored text)
    if latest_url:
        latest_display = osc8(latest_url, latest_display)

    # Add pinned/skip markers
    markers = []
    if catalog.is_pinned(name):
        markers.append("PINNED")
    if catalog.should_skip(name, latest):
        markers.append("SKIP")

    if markers:
        latest_display = f"{latest_display}  [{' '.join(markers)}]"

    # Hint
    if show_hints and status in ("NOT INSTALLED", "OUTDATED", "CONFLICT"):
        hint = tool.get("hint", "")
        if hint:
            latest_display = f"{latest_display}  [{hint}]"

    # Add CONFLICT message to installed display
    if status == "CONFLICT" and installed_display.startswith("CONFLICT:"):
        installed_display = installed_display.replace("CONFLICT: ", "")  # Show clean message

    print("|".join((icon, name_display, installed_display, latest_display)))


def print_summary(snapshot: dict[str, Any], tools: list[dict[str, Any]]) -> None:
    """Print summary line.

    Args:
        snapshot: Snapshot metadata
        tools: List of tool dictionaries
    """
    meta = snapshot.get("__meta__", {})
    total = meta.get("count", len(tools))
    missing = sum(1 for t in tools if t.get("status") == "NOT INSTALLED")
    outdated = sum(1 for t in tools if t.get("status") == "OUTDATED")
    conflicts = sum(1 for t in tools if t.get("status") == "CONFLICT")
    unknown = sum(1 for t in tools if t.get("status") == "UNKNOWN")
    offline_tag = " (offline)" if meta.get("offline") else ""

    # Build summary message
    parts = [f"{total} tools", f"{outdated} outdated", f"{missing} missing"]
    if conflicts > 0:
        parts.append(f"{conflicts} conflicts")
    parts.append(f"{unknown} unknown")

    print(
        f"\nReadiness{offline_tag}: {', '.join(parts)}",
        file=sys.stderr,
    )
