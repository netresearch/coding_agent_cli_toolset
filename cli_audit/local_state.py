"""
Local installation state management.

Phase 2.1: Split snapshot into upstream cache (committed) and local state (gitignored).
This module manages the local_state.json file - machine-specific installation state
that should NOT be committed to the repository.
"""

from __future__ import annotations

import datetime
import json
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .upstream_cache import UpstreamCache, UpstreamVersion

# Default local state file location
DEFAULT_LOCAL_STATE_FILE = "local_state.json"


@dataclass
class LocalInstallation:
    """Local installation information for a tool."""

    installed_version: str = ""
    installed_path: str = ""
    installed_method: str = ""
    status: str = "UNKNOWN"
    classification_reason: str = ""
    category: str = "other"
    hint: str = ""

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for JSON serialization."""
        return {
            "installed_version": self.installed_version,
            "installed_path": self.installed_path,
            "installed_method": self.installed_method,
            "status": self.status,
            "classification_reason": self.classification_reason,
            "category": self.category,
            "hint": self.hint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocalInstallation":
        """Create from dictionary."""
        return cls(
            installed_version=data.get("installed_version", ""),
            installed_path=data.get("installed_path", ""),
            installed_method=data.get("installed_method", ""),
            status=data.get("status", "UNKNOWN"),
            classification_reason=data.get("classification_reason", ""),
            category=data.get("category", "other"),
            hint=data.get("hint", ""),
        )


@dataclass
class LocalState:
    """Container for local installation state with metadata."""

    tools: dict[str, LocalInstallation] = field(default_factory=dict)
    schema_version: int = 2
    collected_at: str = ""
    hostname: str = ""
    offline: bool = False
    count: int = 0
    partial_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "__meta__": {
                "schema_version": self.schema_version,
                "collected_at": self.collected_at,
                "hostname": self.hostname,
                "offline": self.offline,
                "count": self.count,
                "partial_failures": self.partial_failures,
            },
            "tools": {
                name: tool.to_dict() for name, tool in self.tools.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocalState":
        """Create from dictionary."""
        meta = data.get("__meta__", {})
        tools_raw = data.get("tools", {})

        tools = {
            name: LocalInstallation.from_dict(tool_data)
            for name, tool_data in tools_raw.items()
        }

        return cls(
            tools=tools,
            schema_version=meta.get("schema_version", 2),
            collected_at=meta.get("collected_at", ""),
            hostname=meta.get("hostname", ""),
            offline=meta.get("offline", False),
            count=meta.get("count", 0),
            partial_failures=meta.get("partial_failures", 0),
        )


def get_local_state_path() -> Path:
    """Get local state file path from env or default.

    Returns:
        Path to local state file
    """
    state_file = os.environ.get("CLI_AUDIT_LOCAL_FILE", DEFAULT_LOCAL_STATE_FILE)
    if os.path.isabs(state_file):
        return Path(state_file)
    return Path.cwd() / state_file


def load_local_state(path: Path | None = None) -> LocalState:
    """Load local state from file.

    Args:
        path: Optional path to state file (uses default if None)

    Returns:
        LocalState instance
    """
    if path is None:
        path = get_local_state_path()

    if not path.exists():
        return LocalState()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return LocalState()
            return LocalState.from_dict(data)
    except Exception:
        return LocalState()


def write_local_state(
    state: LocalState,
    path: Path | None = None,
    offline: bool = False,
) -> None:
    """Write local state to file.

    Args:
        state: LocalState instance to write
        path: Optional path to state file (uses default if None)
        offline: Whether this was collected in offline mode
    """
    if path is None:
        path = get_local_state_path()

    # Update metadata
    state.collected_at = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    state.hostname = socket.gethostname()
    state.offline = offline
    state.count = len(state.tools)
    state.partial_failures = sum(
        1 for t in state.tools.values()
        if t.status == "UNKNOWN" and not t.installed_version
    )

    # Atomic write: write to temp file then rename
    try:
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)
        temp_path.replace(path)
    except Exception as e:
        raise IOError(f"Failed to write local state: {e}")


def get_local_installation(tool_name: str, state: LocalState) -> LocalInstallation | None:
    """Get local installation info for a tool.

    Args:
        tool_name: Tool name
        state: LocalState instance

    Returns:
        LocalInstallation or None if not found
    """
    return state.tools.get(tool_name)


def update_local_installation(
    tool_name: str,
    installation: LocalInstallation,
    state: LocalState,
) -> None:
    """Update local installation info for a tool.

    Args:
        tool_name: Tool name
        installation: LocalInstallation to store
        state: LocalState instance to update
    """
    state.tools[tool_name] = installation


def migrate_from_snapshot(snapshot: dict[str, Any]) -> LocalState:
    """Migrate local state data from old tools_snapshot.json format.

    Args:
        snapshot: Old snapshot dictionary with __meta__ and tools keys

    Returns:
        LocalState with migrated data
    """
    state = LocalState()

    tools = snapshot.get("tools", [])
    for tool in tools:
        tool_name = tool.get("tool", "")
        if not tool_name:
            continue

        installation = LocalInstallation(
            installed_version=tool.get("installed_version", ""),
            installed_path=tool.get("installed_path_selected", ""),
            installed_method=tool.get("installed_method", ""),
            status=tool.get("status", "UNKNOWN"),
            classification_reason=tool.get("classification_reason_selected", ""),
            category=tool.get("category", "other"),
            hint=tool.get("hint", ""),
        )
        state.tools[tool_name] = installation

    # Preserve metadata from old snapshot
    meta = snapshot.get("__meta__", {})
    state.collected_at = meta.get("collected_at", "")
    state.offline = meta.get("offline", False)

    return state


def merge_for_display(
    upstream: UpstreamCache,
    local: LocalState,
) -> list[dict[str, Any]]:
    """Merge upstream cache and local state for display/rendering.

    Combines data from both sources into a list format compatible with
    the existing render functions.

    Args:
        upstream: UpstreamCache instance
        local: LocalState instance

    Returns:
        List of tool dictionaries in the legacy snapshot format
    """
    # Get all tool names from both sources
    all_tools = set(upstream.versions.keys()) | set(local.tools.keys())

    result = []
    for tool_name in sorted(all_tools):
        up = upstream.versions.get(tool_name, UpstreamVersion())
        loc = local.tools.get(tool_name, LocalInstallation())

        # Build legacy-compatible dictionary
        tool_dict = {
            "tool": tool_name,
            "category": loc.category,
            "hint": loc.hint,
            # Installed info (from local state)
            "installed": loc.installed_version,
            "installed_version": loc.installed_version,
            "installed_method": loc.installed_method,
            "installed_path_selected": loc.installed_path,
            "classification_reason_selected": loc.classification_reason,
            "status": loc.status,
            # Upstream info (from upstream cache)
            "latest_upstream": up.latest_tag,
            "latest_version": up.latest_version,
            "latest_url": up.latest_url,
            "tool_url": up.tool_url,
            "upstream_method": up.upstream_method,
        }
        result.append(tool_dict)

    return result


def build_legacy_snapshot(
    upstream: UpstreamCache,
    local: LocalState,
) -> dict[str, Any]:
    """Build a legacy snapshot format from split files.

    For backward compatibility with code that expects the old format.

    Args:
        upstream: UpstreamCache instance
        local: LocalState instance

    Returns:
        Dictionary in legacy tools_snapshot.json format
    """
    tools = merge_for_display(upstream, local)

    return {
        "__meta__": {
            "schema_version": 1,
            "created_at": local.collected_at or upstream.baseline_updated_at,
            "collected_at": local.collected_at,
            "offline": local.offline,
            "count": len(tools),
            "partial_failures": local.partial_failures,
        },
        "tools": tools,
    }
