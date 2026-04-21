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
    # Status takes precedence: a PIN:never row that is correctly absent
    # has ``UP-TO-DATE`` status with empty ``installed`` and should render
    # green, not red-X.
    if not USE_EMOJI:
        if status == "UP-TO-DATE":
            return "✓"
        if status == "OUTDATED":
            return "↑"
        if status == "CONFLICT":
            return "⚠"
        if installed == "X" or installed == "" or status == "NOT INSTALLED":
            return "x"
        return "?"

    # Emoji icons (using consistent single-width Unicode)
    if status == "UP-TO-DATE":
        return "✅"
    if status == "OUTDATED":
        return "⬆"  # Single-width arrow without variation selector
    if status == "CONFLICT":
        return "⚠️"
    if installed == "X" or installed == "" or status == "NOT INSTALLED":
        return "❌"
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


def render_table(tools: list[dict[str, Any]]) -> None:
    """Render tools as pipe-delimited table, optionally grouped by category."""
    from .config import load_config
    from .pins import load_pins

    # Header — 5 columns. Pin info lives next to the ``installed`` value
    # it constrains; ``notes`` carries install method and auto-update flag.
    headers = ("state", "tool", "installed", "latest_upstream", "notes")
    print("|".join(headers))

    # Load once so each row render is cheap.
    pins = load_pins()
    try:
        config = load_config()
    except Exception:
        config = None

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
                _render_tool_row(tool, pins, config)
    else:
        for tool in tools:
            _render_tool_row(tool, pins, config)


def _pin_suffix(pin: str) -> str:
    """Format a pin value as an appendable suffix (empty if no pin)."""
    if not pin:
        return ""
    if pin == "never":
        return " [PIN:never]"
    return f" [PIN:{pin}]"


def _apply_pin_to_status(status: str, installed: str, latest: str, pin: str) -> str:
    """Adjust the snapshot status using the user's pin as the target.

    The snapshot's ``status`` was computed against ``latest_upstream`` with
    no knowledge of pins. A pin is the user's stated target — rendering
    must respect it so ``✅`` never appears on a row whose installed
    version diverges from the pin.

    Rules (``pin == "never"`` is effectively ``installed must stay empty``):

    - ``pin`` empty          → pass through, pin doesn't apply
    - ``pin == "never"``
        - nothing installed  → ``UP-TO-DATE`` (the pin is honored)
        - something installed→ ``CONFLICT`` (user said never, but it's here)
    - specific version pin
        - nothing installed  → ``NOT INSTALLED`` (unchanged)
        - installed == pin   → ``UP-TO-DATE`` (regardless of latest)
        - installed != pin   → ``CONFLICT`` (pin is being violated)
    """
    if not pin:
        return status
    if pin == "never":
        if not installed:
            return "UP-TO-DATE"
        return "CONFLICT"
    # Specific-version pin.
    if not installed:
        return "NOT INSTALLED"
    if installed == pin:
        return "UP-TO-DATE"
    return "CONFLICT"


def _build_notes(tool: dict[str, Any], config: Any) -> str:
    """Compose the ``notes`` cell: ``method · auto``.

    Pin info is rendered in the ``installed`` column, not here.
    """
    parts: list[str] = []
    method = tool.get("installed_method") or ""
    if method:
        parts.append(method)

    if config is not None:
        name = tool.get("tool", "")
        base = name.split("@", 1)[0] if "@" in name else name
        tool_cfg = config.tools.get(name) or config.tools.get(base)
        if tool_cfg is not None and tool_cfg.auto_update is True:
            parts.append("auto")

    return " · ".join(parts)


def _render_tool_row(
    tool: dict[str, Any],
    pins: dict[str, Any],
    config: Any,
) -> None:
    """Render a single tool row."""
    from .pins import lookup_pin

    name = tool.get("tool", "")
    installed = tool.get("installed", "")
    latest = tool.get("latest_upstream", "")
    raw_status = tool.get("status", "UNKNOWN")
    tool_url = tool.get("tool_url", "")
    latest_url = tool.get("latest_url", "")

    # A pin overrides the "upgrade target" for display purposes. The
    # snapshot's ``status`` is computed against latest_upstream and does
    # not know about pins, so fix it up here before choosing icon/colors.
    pin_value = lookup_pin(name, pins)
    status = _apply_pin_to_status(raw_status, installed, latest, pin_value)

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

    # Apply colors to installed and latest
    installed_display = colorize(installed, inst_color)
    latest_display = colorize(latest, latest_color)

    # Apply hyperlinks (after colorization, hyperlinks wrap the colored text)
    if latest_url:
        latest_display = osc8(latest_url, latest_display)

    # Attach pin marker to the version it constrains (installed column).
    # The suffix renders outside the hyperlink so it stays readable when
    # nothing is installed.
    installed_display = f"{installed_display}{_pin_suffix(pin_value)}"

    notes = _build_notes(tool, config)

    # Add CONFLICT message to installed display
    if status == "CONFLICT" and installed_display.startswith("CONFLICT:"):
        installed_display = installed_display.replace("CONFLICT: ", "")  # Show clean message

    print("|".join((icon, name_display, installed_display, latest_display, notes)))


def print_summary(snapshot: dict[str, Any], tools: list[dict[str, Any]]) -> None:
    """Print summary line.

    Args:
        snapshot: Snapshot metadata
        tools: List of tool dictionaries
    """
    from .pins import load_pins, lookup_pin

    meta = snapshot.get("__meta__", {})
    total = meta.get("count", len(tools))

    pins = load_pins()

    def _effective(t: dict[str, Any]) -> str:
        return _apply_pin_to_status(
            t.get("status", "UNKNOWN"),
            t.get("installed", ""),
            t.get("latest_upstream", ""),
            lookup_pin(t.get("tool", ""), pins),
        )

    effective = [_effective(t) for t in tools]
    missing = sum(1 for s in effective if s == "NOT INSTALLED")
    outdated = sum(1 for s in effective if s == "OUTDATED")
    conflicts = sum(1 for s in effective if s == "CONFLICT")
    unknown = sum(1 for s in effective if s == "UNKNOWN")
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
