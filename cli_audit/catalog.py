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
    candidates: list[str] | None = None  # NEW: Binary names to search for (defaults to [binary_name])
    category: str = ""  # NEW: Tool category (runtimes, search, editors, etc.)
    hint: str = ""  # NEW: Installation hint (e.g., "make install-core")
    _raw_data: dict[str, Any] | None = None  # NEW: Raw catalog JSON for extended fields

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
            candidates=data.get("candidates"),  # NEW
            category=data.get("category", ""),  # NEW
            hint=data.get("hint", ""),  # NEW
            _raw_data=data,  # NEW: Store raw data
        )

    def _derive_source(self) -> tuple[str, tuple[str, ...]]:
        """Derive source_kind and source_args from catalog metadata.

        Returns:
            Tuple of (source_kind, source_args)
        """
        # Priority 0: Skip version checking for pure package_manager tools
        # These are OS-managed and can't be manually upgraded
        if self.install_method == "package_manager" and not self.github_repo and not self.package_name:
            return ("skip", ())

        # Priority 1: GitHub repo
        if self.github_repo:
            parts = self.github_repo.split("/", 1)
            if len(parts) == 2:
                # Check if it's GitLab
                if "gitlab" in self.homepage.lower():
                    return ("gitlab", (parts[0], parts[1]))
                return ("gh", (parts[0], parts[1]))

        # Priority 2: Package name + homepage hints
        if self.package_name:
            homepage_lower = self.homepage.lower()
            # Check homepage for package source hints
            if "npmjs.com" in homepage_lower or "yarnpkg.com" in homepage_lower or "pnpm.io" in homepage_lower:
                return ("npm", (self.package_name,))
            elif "pypi.org" in homepage_lower or "python.org" in homepage_lower or "pypa.io" in homepage_lower:
                return ("pypi", (self.package_name,))
            elif "crates.io" in homepage_lower:
                return ("crates", (self.package_name,))
            # Fallback: check install_method
            elif "npm" in self.install_method:
                return ("npm", (self.package_name,))
            elif "pip" in self.install_method or "pipx" in self.install_method or "uv_tool" in self.install_method:
                return ("pypi", (self.package_name,))
            elif "cargo" in self.install_method or "crates" in self.install_method:
                return ("crates", (self.package_name,))

        # Priority 3: GNU FTP releases (check raw data for ftp_url field)
        if self._raw_data and self._raw_data.get("ftp_url"):
            return ("gnu", (self.name, self._raw_data["ftp_url"]))

        # Priority 4: Detect GNU tools from homepage
        if "gnu.org" in self.homepage:
            # Construct default FTP URL
            return ("gnu", (self.name, f"https://ftp.gnu.org/gnu/{self.name}/"))

        # Default: skip (no version collection)
        return ("skip", ())

    def to_tool(self) -> "Tool":
        """Convert catalog entry to Tool instance.

        Returns:
            Tool instance
        """
        from cli_audit.tools import Tool

        # Derive source information
        source_kind, source_args = self._derive_source()

        # Determine candidates: use candidates field, or binary_name, or tool name as fallback
        if self.candidates:
            candidates = tuple(self.candidates)
        elif self.binary_name:
            candidates = (self.binary_name,)
        else:
            # Fallback: use tool name as binary name
            candidates = (self.name,)

        return Tool(
            name=self.name,
            candidates=candidates,
            source_kind=source_kind,
            source_args=source_args,
            category=self.category or "other",
            hint=self.hint or "",
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

        logger.debug(f"Loaded {len(self._entries)} catalog entries")

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

    def all_tool_definitions(self) -> list["Tool"]:
        """Get all tools as Tool instances.

        Returns:
            List of Tool instances generated from catalog
        """
        from cli_audit.tools import Tool

        return [entry.to_tool() for entry in self._entries.values()]

    def get_package_manager_tools(self) -> list[ToolCatalogEntry]:
        """Get tools that use package_manager install method.

        Returns:
            List of ToolCatalogEntry instances with install_method=package_manager
        """
        return [
            entry
            for entry in self._entries.values()
            if entry.install_method == "package_manager"
        ]


def detect_package_manager() -> tuple[str, str] | None:
    """Detect the current OS package manager and upgrade command.

    Returns:
        Tuple of (package_manager_name, upgrade_command) or None if not detected
    """
    import platform
    import shutil

    # Check for package managers in order of preference
    if shutil.which("apt"):
        return ("apt", "sudo apt update && sudo apt upgrade")
    elif shutil.which("dnf"):
        return ("dnf", "sudo dnf upgrade")
    elif shutil.which("yum"):
        return ("yum", "sudo yum update")
    elif shutil.which("pacman"):
        return ("pacman", "sudo pacman -Syu")
    elif shutil.which("zypper"):
        return ("zypper", "sudo zypper update")
    elif shutil.which("brew"):
        return ("brew", "brew upgrade")
    elif shutil.which("apk"):
        return ("apk", "sudo apk upgrade")

    return None


def suggest_package_manager_upgrades(catalog: ToolCatalog | None = None) -> None:
    """Print package manager upgrade suggestions.

    Args:
        catalog: ToolCatalog instance (creates new one if None)
    """
    import sys

    if catalog is None:
        catalog = ToolCatalog()

    # Detect package manager
    pm_info = detect_package_manager()
    if not pm_info:
        return  # No package manager detected, silently skip

    pm_name, upgrade_cmd = pm_info

    # Get tools managed by package managers
    pm_tools = catalog.get_package_manager_tools()
    if not pm_tools:
        return  # No package-manager tools in catalog

    # Check which tools have package_name or github_repo (these check upstream separately)
    os_only_tools = [
        t.name
        for t in pm_tools
        if not t.github_repo and not t.package_name
    ]

    if not os_only_tools:
        return  # All package_manager tools check upstream separately

    print("", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print("📦 Package Manager Updates", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"Some tools are OS-managed and updated via {pm_name}:", file=sys.stderr)
    print(f"  {', '.join(sorted(os_only_tools))}", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"To update OS-managed packages, run:", file=sys.stderr)
    print(f"  {upgrade_cmd}", file=sys.stderr)
    print("", file=sys.stderr)
