"""
Tool catalog management and pin/skip functionality.

Phase 2.0: Detection and Auditing - Catalog Management
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolCatalogEntry:
    """Tool catalog entry from catalog/*.json file."""

    name: str
    description: str = ""
    homepage: str = ""
    github_repo: str = ""
    binary_name: str = ""
    install_method: str = ""
    package_name: str = ""
    script: str = ""
    pinned_version: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCatalogEntry":
        """Create from catalog JSON data."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            homepage=data.get("homepage", ""),
            github_repo=data.get("github_repo", ""),
            binary_name=data.get("binary_name", ""),
            install_method=data.get("install_method", ""),
            package_name=data.get("package_name", ""),
            script=data.get("script", ""),
            pinned_version=data.get("pinned_version", ""),
            notes=data.get("notes", ""),
        )


class ToolCatalog:
    """Manages tool catalog entries from catalog/ directory."""

    def __init__(self, catalog_dir: str | Path | None = None):
        """Initialize catalog manager.

        Args:
            catalog_dir: Path to catalog directory (defaults to ./catalog)
        """
        if catalog_dir is None:
            # Default to catalog/ next to this file's parent
            self.catalog_dir = Path(__file__).parent.parent / "catalog"
        else:
            self.catalog_dir = Path(catalog_dir)

        self._entries: dict[str, ToolCatalogEntry] = {}
        self._raw_data: dict[str, dict[str, Any]] = {}
        self._load_catalog()

    def _load_catalog(self) -> None:
        """Load all catalog/*.json files."""
        if not self.catalog_dir.exists():
            logger.warning(f"Catalog directory not found: {self.catalog_dir}")
            return

        for json_file in self.catalog_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    entry = ToolCatalogEntry.from_dict(data)
                    self._entries[entry.name] = entry
                    self._raw_data[entry.name] = data  # Store raw JSON
                    logger.debug(f"Loaded catalog entry: {entry.name}")
            except Exception as e:
                logger.error(f"Failed to load {json_file}: {e}")

        logger.info(f"Loaded {len(self._entries)} catalog entries")

    def get(self, tool_name: str) -> ToolCatalogEntry | None:
        """Get catalog entry for a tool.

        Args:
            tool_name: Tool name

        Returns:
            ToolCatalogEntry or None if not found
        """
        return self._entries.get(tool_name)

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool exists in the catalog.

        Args:
            tool_name: Tool name

        Returns:
            True if tool exists in catalog
        """
        return tool_name in self._entries

    def get_raw_data(self, tool_name: str) -> dict[str, Any]:
        """Get raw JSON data for a tool.

        Args:
            tool_name: Tool name

        Returns:
            Raw catalog JSON data or empty dict if not found
        """
        return self._raw_data.get(tool_name, {})

    def is_pinned(self, tool_name: str) -> bool:
        """Check if a tool has a pinned version.

        Args:
            tool_name: Tool name

        Returns:
            True if tool has pinned version (not empty and not "never")
        """
        entry = self.get(tool_name)
        if not entry:
            return False

        pinned = entry.pinned_version
        return bool(pinned and pinned != "never")

    def get_pinned_version(self, tool_name: str) -> str:
        """Get pinned version for a tool.

        Args:
            tool_name: Tool name

        Returns:
            Pinned version string or empty string if not pinned
        """
        entry = self.get(tool_name)
        if not entry:
            return ""

        pinned = entry.pinned_version
        if pinned and pinned != "never":
            return pinned
        return ""

    def should_skip(self, tool_name: str, latest_version: str) -> bool:
        """Check if tool should be skipped (pinned and already at pinned version).

        Args:
            tool_name: Tool name
            latest_version: Latest available version

        Returns:
            True if tool should be skipped
        """
        pinned = self.get_pinned_version(tool_name)
        if not pinned:
            return False

        # Simple version comparison - if pinned matches latest, skip
        return pinned == latest_version

    def all_tools(self) -> list[str]:
        """Get list of all tool names in catalog.

        Returns:
            List of tool names
        """
        return list(self._entries.keys())
