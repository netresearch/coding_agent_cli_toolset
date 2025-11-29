"""
Tool definitions and metadata management.

Phase 2.0: Detection and Auditing - Tool Definitions

This module now loads tool definitions from the catalog/ directory.
The catalog is the single source of truth for tool metadata.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    """Tool definition with source and detection metadata."""
    name: str
    candidates: tuple[str, ...]  # Binary names to search for
    source_kind: str  # "gh" | "gitlab" | "pypi" | "crates" | "npm" | "gnu" | "skip"
    source_args: tuple[str, ...]  # Source-specific args (owner, repo) or (package,)
    category: str = "other"
    hint: str = ""


# Load tools from catalog (single source of truth)
from cli_audit.catalog import ToolCatalog  # noqa: E402

_catalog = ToolCatalog()
TOOLS: tuple[Tool, ...] = tuple(_catalog.all_tool_definitions())

# Tool lookup map for fast access
TOOL_MAP: dict[str, Tool] = {t.name: t for t in TOOLS}

# Category order for grouping
CATEGORY_ORDER: tuple[str, ...] = (
    "runtimes",
    "search",
    "editors",
    "json-yaml",
    "http",
    "automation",
    "security",
    "git-helpers",
    "formatters",
    "vcs",
    "cloud-infra",
    "task-runners",
    "data",
    "ai-assistants",
    "other",
)


def get_tool(name: str) -> Tool | None:
    """Get tool definition by name.

    Args:
        name: Tool name

    Returns:
        Tool or None if not found
    """
    return TOOL_MAP.get(name)


def all_tools() -> list[Tool]:
    """Get all tool definitions.

    Returns:
        List of all tools in defined order
    """
    return list(TOOLS)


def filter_tools(names: list[str]) -> list[Tool]:
    """Filter tools by name list.

    Args:
        names: List of tool names (case-insensitive)

    Returns:
        List of matching tools in original order
    """
    name_set = {n.lower() for n in names}
    return [t for t in TOOLS if t.name.lower() in name_set]


def tool_homepage_url(tool: Tool) -> str:
    """Get homepage URL for a tool.

    Args:
        tool: Tool definition

    Returns:
        Homepage URL string
    """
    if tool.source_kind == "gh" and len(tool.source_args) >= 2:
        owner, repo = tool.source_args[0], tool.source_args[1]
        return f"https://github.com/{owner}/{repo}"
    elif tool.source_kind == "gitlab" and len(tool.source_args) >= 2:
        group, project = tool.source_args[0], tool.source_args[1]
        return f"https://gitlab.com/{group}/{project}"
    elif tool.source_kind == "pypi" and tool.source_args:
        package = tool.source_args[0]
        return f"https://pypi.org/project/{package}/"
    elif tool.source_kind == "npm" and tool.source_args:
        package = tool.source_args[0]
        return f"https://www.npmjs.com/package/{package}"
    elif tool.source_kind == "crates" and tool.source_args:
        crate = tool.source_args[0]
        return f"https://crates.io/crates/{crate}"
    return ""


def latest_target_url(tool: Tool, latest_tag: str, latest_num: str) -> str:
    """Get URL for latest release.

    Args:
        tool: Tool definition
        latest_tag: Latest version tag
        latest_num: Latest version number

    Returns:
        Release URL string
    """
    if tool.source_kind == "gh" and len(tool.source_args) >= 2:
        owner, repo = tool.source_args[0], tool.source_args[1]
        if latest_tag:
            return f"https://github.com/{owner}/{repo}/releases/tag/{latest_tag}"
        return f"https://github.com/{owner}/{repo}/releases"
    elif tool.source_kind == "gitlab" and len(tool.source_args) >= 2:
        group, project = tool.source_args[0], tool.source_args[1]
        if latest_tag:
            return f"https://gitlab.com/{group}/{project}/-/releases/{latest_tag}"
        return f"https://gitlab.com/{group}/{project}/-/releases"
    elif tool.source_kind == "pypi" and tool.source_args:
        package = tool.source_args[0]
        return f"https://pypi.org/project/{package}/"
    elif tool.source_kind == "npm" and tool.source_args:
        package = tool.source_args[0]
        return f"https://www.npmjs.com/package/{package}"
    elif tool.source_kind == "crates" and tool.source_args:
        crate = tool.source_args[0]
        return f"https://crates.io/crates/{crate}"
    return ""
