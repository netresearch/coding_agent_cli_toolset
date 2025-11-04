"""
Snapshot management for tool audit results.

Phase 2.0: Detection and Auditing - Snapshot Management
"""

import datetime
import json
import os
from pathlib import Path
from typing import Any

# Default snapshot file location
DEFAULT_SNAPSHOT_FILE = "tools_snapshot.json"


def get_snapshot_path() -> Path:
    """Get snapshot file path from env or default.

    Returns:
        Path to snapshot file
    """
    snapshot_file = os.environ.get("CLI_AUDIT_SNAPSHOT_FILE", DEFAULT_SNAPSHOT_FILE)
    if os.path.isabs(snapshot_file):
        return Path(snapshot_file)
    return Path.cwd() / snapshot_file


def load_snapshot(path: Path | None = None) -> dict[str, Any]:
    """Load snapshot from file.

    Args:
        path: Optional path to snapshot file (uses default if None)

    Returns:
        Snapshot dictionary with __meta__ and tools keys
    """
    if path is None:
        path = get_snapshot_path()

    if not path.exists():
        return {"__meta__": {}, "tools": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"__meta__": {}, "tools": []}
            return data
    except Exception:
        return {"__meta__": {}, "tools": []}


def write_snapshot(
    tools: list[dict[str, Any]],
    path: Path | None = None,
    offline: bool = False,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write snapshot to file.

    Args:
        tools: List of tool dictionaries
        path: Optional path to snapshot file (uses default if None)
        offline: Whether this was collected in offline mode
        extra_meta: Additional metadata to include

    Returns:
        Metadata dictionary
    """
    if path is None:
        path = get_snapshot_path()

    # Create metadata
    meta = {
        "schema_version": 1,
        "created_at": datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "collected_at": datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "offline": offline,
        "count": len(tools),
        "partial_failures": sum(
            1 for t in tools if (t.get("status") == "UNKNOWN" and not t.get("installed"))
        ),
    }

    if extra_meta:
        meta.update(extra_meta)

    # Create snapshot document
    doc = {"__meta__": meta, "tools": tools}

    # Atomic write: write to temp file then rename
    try:
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False, sort_keys=True)
        temp_path.replace(path)
    except Exception as e:
        raise IOError(f"Failed to write snapshot: {e}")

    return meta


def render_from_snapshot(
    snapshot: dict[str, Any], selected: set[str] | None = None
) -> list[dict[str, Any]]:
    """Render tools from snapshot, optionally filtering.

    Args:
        snapshot: Snapshot dictionary
        selected: Optional set of tool names to include (case-insensitive)

    Returns:
        List of tool dictionaries
    """
    tools = snapshot.get("tools", [])
    if not selected:
        return tools

    # Filter by selected names (case-insensitive)
    selected_lower = {n.lower() for n in selected}
    return [t for t in tools if t.get("tool", "").lower() in selected_lower]
