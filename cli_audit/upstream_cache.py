"""
Upstream version cache management.

Phase 2.1: Split snapshot into upstream cache (committed) and local state (gitignored).
This module manages the upstream_versions.json file - a cached baseline of latest
upstream versions that can be committed to the repository.
"""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Default upstream cache file location
DEFAULT_UPSTREAM_FILE = "upstream_versions.json"

# Cache staleness threshold (7 days)
DEFAULT_MAX_AGE_HOURS = 168


@dataclass
class UpstreamVersion:
    """Upstream version information for a tool."""

    latest_tag: str = ""
    latest_version: str = ""
    latest_url: str = ""
    tool_url: str = ""
    upstream_method: str = ""

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for JSON serialization."""
        return {
            "latest_tag": self.latest_tag,
            "latest_version": self.latest_version,
            "latest_url": self.latest_url,
            "tool_url": self.tool_url,
            "upstream_method": self.upstream_method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpstreamVersion":
        """Create from dictionary."""
        return cls(
            latest_tag=data.get("latest_tag", ""),
            latest_version=data.get("latest_version", ""),
            latest_url=data.get("latest_url", ""),
            tool_url=data.get("tool_url", ""),
            upstream_method=data.get("upstream_method", ""),
        )


@dataclass
class UpstreamCache:
    """Container for upstream version cache with metadata."""

    versions: dict[str, UpstreamVersion] = field(default_factory=dict)
    schema_version: int = 2
    baseline_updated_at: str = ""
    source: str = "github/pypi/npm/crates API"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "__meta__": {
                "schema_version": self.schema_version,
                "baseline_updated_at": self.baseline_updated_at,
                "source": self.source,
            },
            "versions": {
                name: ver.to_dict() for name, ver in self.versions.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpstreamCache":
        """Create from dictionary."""
        meta = data.get("__meta__", {})
        versions_raw = data.get("versions", {})

        versions = {
            name: UpstreamVersion.from_dict(ver_data)
            for name, ver_data in versions_raw.items()
        }

        return cls(
            versions=versions,
            schema_version=meta.get("schema_version", 2),
            baseline_updated_at=meta.get("baseline_updated_at", ""),
            source=meta.get("source", ""),
        )


def get_upstream_cache_path() -> Path:
    """Get upstream cache file path from env or default.

    Returns:
        Path to upstream cache file
    """
    cache_file = os.environ.get("CLI_AUDIT_UPSTREAM_FILE", DEFAULT_UPSTREAM_FILE)
    if os.path.isabs(cache_file):
        return Path(cache_file)
    return Path.cwd() / cache_file


def load_upstream_cache(path: Path | None = None) -> UpstreamCache:
    """Load upstream cache from file.

    Args:
        path: Optional path to cache file (uses default if None)

    Returns:
        UpstreamCache instance
    """
    if path is None:
        path = get_upstream_cache_path()

    if not path.exists():
        return UpstreamCache()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return UpstreamCache()
            return UpstreamCache.from_dict(data)
    except Exception:
        return UpstreamCache()


def write_upstream_cache(
    cache: UpstreamCache,
    path: Path | None = None,
) -> None:
    """Write upstream cache to file.

    Args:
        cache: UpstreamCache instance to write
        path: Optional path to cache file (uses default if None)
    """
    if path is None:
        path = get_upstream_cache_path()

    # Update timestamp
    cache.baseline_updated_at = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    # Atomic write: write to temp file then rename
    try:
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(cache.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)
        temp_path.replace(path)
    except Exception as e:
        raise IOError(f"Failed to write upstream cache: {e}")


def get_cached_upstream(tool_name: str, cache: UpstreamCache) -> UpstreamVersion | None:
    """Get cached upstream version for a tool.

    Args:
        tool_name: Tool name
        cache: UpstreamCache instance

    Returns:
        UpstreamVersion or None if not found
    """
    return cache.versions.get(tool_name)


def update_cached_upstream(
    tool_name: str,
    version: UpstreamVersion,
    cache: UpstreamCache,
) -> None:
    """Update cached upstream version for a tool.

    Args:
        tool_name: Tool name
        version: UpstreamVersion to cache
        cache: UpstreamCache instance to update
    """
    cache.versions[tool_name] = version


def is_cache_stale(cache: UpstreamCache, max_age_hours: int = DEFAULT_MAX_AGE_HOURS) -> bool:
    """Check if cache is stale (older than max_age_hours).

    Args:
        cache: UpstreamCache instance
        max_age_hours: Maximum age in hours before cache is considered stale

    Returns:
        True if cache is stale or has no timestamp
    """
    if not cache.baseline_updated_at:
        return True

    try:
        # Parse ISO timestamp
        updated_at = datetime.datetime.fromisoformat(
            cache.baseline_updated_at.replace("Z", "+00:00")
        )
        now = datetime.datetime.now(datetime.timezone.utc)
        age = now - updated_at
        return age.total_seconds() > (max_age_hours * 3600)
    except Exception:
        return True


def migrate_from_snapshot(snapshot: dict[str, Any]) -> UpstreamCache:
    """Migrate upstream data from old tools_snapshot.json format.

    Args:
        snapshot: Old snapshot dictionary with __meta__ and tools keys

    Returns:
        UpstreamCache with migrated data
    """
    cache = UpstreamCache()

    tools = snapshot.get("tools", [])
    for tool in tools:
        tool_name = tool.get("tool", "")
        if not tool_name:
            continue

        version = UpstreamVersion(
            latest_tag=tool.get("latest_upstream", ""),
            latest_version=tool.get("latest_version", ""),
            latest_url=tool.get("latest_url", ""),
            tool_url=tool.get("tool_url", ""),
            upstream_method=tool.get("upstream_method", ""),
        )
        cache.versions[tool_name] = version

    # Preserve timestamp from old snapshot if available
    meta = snapshot.get("__meta__", {})
    if meta.get("collected_at"):
        cache.baseline_updated_at = meta["collected_at"]

    return cache
