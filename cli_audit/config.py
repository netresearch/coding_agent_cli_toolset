"""
Configuration file parsing and management.

Supports YAML configuration files with JSON fallback.
Merges configurations from multiple sources (project → user → system → defaults).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .common import vlog


# Configuration file locations (in priority order)
CONFIG_LOCATIONS = [
    ".cli-audit.yml",                              # Project root (highest priority)
    ".cli-audit.yaml",                             # Alternative extension
    os.path.expanduser("~/.config/cli-audit/config.yml"),  # User global
    os.path.expanduser("~/.config/cli-audit/config.yaml"),
    "/etc/cli-audit/config.yml",                   # System global
    "/etc/cli-audit/config.yaml",
]


@dataclass(frozen=True)
class ToolConfig:
    """
    Configuration for a specific tool.

    Attributes:
        version: Target version (e.g., "latest", "3.12.*", "1.2.3")
        method: Preferred installation method (e.g., "uv", "cargo", "npm")
        fallback: Fallback installation method if primary fails
    """
    version: str = "latest"
    method: str | None = None
    fallback: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ToolConfig:
        """Create ToolConfig from dictionary."""
        return ToolConfig(
            version=data.get("version", "latest"),
            method=data.get("method"),
            fallback=data.get("fallback"),
        )


@dataclass(frozen=True)
class BulkPreferences:
    """
    Preferences for bulk installation operations.

    Attributes:
        fail_fast: Stop immediately on first failure
        auto_rollback: Automatically rollback on any failure
        generate_rollback_script: Generate rollback script for successful installations
    """
    fail_fast: bool = False
    auto_rollback: bool = False
    generate_rollback_script: bool = True

    @staticmethod
    def from_dict(data: dict[str, Any]) -> BulkPreferences:
        """Create BulkPreferences from dictionary."""
        return BulkPreferences(
            fail_fast=data.get("fail_fast", False),
            auto_rollback=data.get("auto_rollback", False),
            generate_rollback_script=data.get("generate_rollback_script", True),
        )


@dataclass(frozen=True)
class Preferences:
    """
    User preferences for installation behavior.

    Attributes:
        reconciliation: Strategy for multiple installations ('parallel' or 'aggressive')
        breaking_changes: How to handle major version upgrades ('accept', 'warn', or 'reject')
        auto_upgrade: Whether to automatically upgrade minor/patch versions
        timeout_seconds: Timeout for network operations
        max_workers: Maximum number of parallel workers
        cache_ttl_seconds: Version cache time-to-live in seconds
        package_managers: Custom package manager hierarchy per language
        bulk: Bulk installation preferences
    """
    reconciliation: str = "parallel"
    breaking_changes: str = "warn"
    auto_upgrade: bool = True
    timeout_seconds: int = 5
    max_workers: int = 16
    cache_ttl_seconds: int = 3600
    package_managers: dict[str, list[str]] = field(default_factory=dict)
    bulk: BulkPreferences = field(default_factory=BulkPreferences)

    def __post_init__(self):
        """Validate preferences after initialization."""
        # Validate reconciliation
        if self.reconciliation not in {"parallel", "aggressive"}:
            raise ValueError(
                f"Invalid reconciliation strategy: {self.reconciliation}. "
                "Must be 'parallel' or 'aggressive'"
            )

        # Validate breaking_changes
        if self.breaking_changes not in {"accept", "warn", "reject"}:
            raise ValueError(
                f"Invalid breaking_changes setting: {self.breaking_changes}. "
                "Must be 'accept', 'warn', or 'reject'"
            )

        # Validate timeout_seconds
        if self.timeout_seconds < 1 or self.timeout_seconds > 60:
            raise ValueError(
                f"Invalid timeout_seconds: {self.timeout_seconds}. "
                "Must be between 1 and 60"
            )

        # Validate max_workers
        if self.max_workers < 1 or self.max_workers > 32:
            raise ValueError(
                f"Invalid max_workers: {self.max_workers}. "
                "Must be between 1 and 32"
            )

        # Validate cache_ttl_seconds
        if self.cache_ttl_seconds < 60 or self.cache_ttl_seconds > 86400:
            raise ValueError(
                f"Invalid cache_ttl_seconds: {self.cache_ttl_seconds}. "
                "Must be between 60 and 86400 (1 minute to 1 day)"
            )

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Preferences:
        """Create Preferences from dictionary."""
        # Parse bulk preferences
        bulk_data = data.get("bulk", {})
        bulk = BulkPreferences.from_dict(bulk_data)

        return Preferences(
            reconciliation=data.get("reconciliation", "parallel"),
            breaking_changes=data.get("breaking_changes", "warn"),
            auto_upgrade=data.get("auto_upgrade", True),
            timeout_seconds=data.get("timeout_seconds", 5),
            max_workers=data.get("max_workers", 16),
            cache_ttl_seconds=data.get("cache_ttl_seconds", 3600),
            package_managers=data.get("package_managers", {}),
            bulk=bulk,
        )


@dataclass(frozen=True)
class Config:
    """
    Complete configuration for CLI audit tool.

    Attributes:
        version: Config schema version
        environment_mode: Environment detection mode ('auto', 'ci', 'server', 'workstation')
        tools: Per-tool configuration overrides
        preferences: Global preferences
        presets: Predefined sets of tools for bulk installation
        source: Path to the configuration file that was loaded
    """
    version: int = 1
    environment_mode: str = "auto"
    tools: dict[str, ToolConfig] = field(default_factory=dict)
    preferences: Preferences = field(default_factory=Preferences)
    presets: dict[str, list[str]] = field(default_factory=dict)
    source: str = ""

    def __post_init__(self):
        """Validate config after initialization."""
        # Validate version
        if self.version != 1:
            raise ValueError(f"Unsupported config version: {self.version}. Expected version 1")

        # Validate environment_mode
        valid_modes = {"auto", "ci", "server", "workstation"}
        if self.environment_mode not in valid_modes:
            raise ValueError(
                f"Invalid environment_mode: {self.environment_mode}. "
                f"Must be one of: {', '.join(sorted(valid_modes))}"
            )

    @staticmethod
    def from_dict(data: dict[str, Any], source: str = "") -> Config:
        """Create Config from dictionary."""
        # Parse tools
        tools_data = data.get("tools", {})
        tools = {
            tool_name: ToolConfig.from_dict(tool_config)
            for tool_name, tool_config in tools_data.items()
        }

        # Parse preferences
        preferences_data = data.get("preferences", {})
        preferences = Preferences.from_dict(preferences_data)

        # Parse presets
        presets_data = data.get("presets", {})
        presets = {
            preset_name: list(tool_list)
            for preset_name, tool_list in presets_data.items()
        }

        # Parse environment
        environment_data = data.get("environment", {})
        environment_mode = environment_data.get("mode", "auto")

        return Config(
            version=data.get("version", 1),
            environment_mode=environment_mode,
            tools=tools,
            preferences=preferences,
            presets=presets,
            source=source,
        )

    def get_tool_config(self, tool_name: str) -> ToolConfig:
        """
        Get configuration for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolConfig for the tool, or default ToolConfig if not configured
        """
        return self.tools.get(tool_name, ToolConfig())

    def merge_with(self, other: Config) -> Config:
        """
        Merge this config with another, preferring values from this config.

        Args:
            other: Other config to merge (lower priority)

        Returns:
            New merged Config object
        """
        # Merge tools (this config takes priority)
        merged_tools = dict(other.tools)
        merged_tools.update(self.tools)

        # Merge package_managers preferences
        merged_pkg_mgrs = dict(other.preferences.package_managers)
        merged_pkg_mgrs.update(self.preferences.package_managers)

        # Merge bulk preferences (prefer this config's values if non-default)
        merged_bulk = BulkPreferences(
            fail_fast=self.preferences.bulk.fail_fast if self.preferences.bulk.fail_fast else other.preferences.bulk.fail_fast,
            auto_rollback=self.preferences.bulk.auto_rollback if self.preferences.bulk.auto_rollback else other.preferences.bulk.auto_rollback,
            generate_rollback_script=self.preferences.bulk.generate_rollback_script,
        )

        # Create merged preferences (prefer this config's values)
        merged_preferences = Preferences(
            reconciliation=self.preferences.reconciliation if self.preferences.reconciliation != "parallel" else other.preferences.reconciliation,
            breaking_changes=self.preferences.breaking_changes if self.preferences.breaking_changes != "warn" else other.preferences.breaking_changes,
            auto_upgrade=self.preferences.auto_upgrade,
            timeout_seconds=self.preferences.timeout_seconds if self.preferences.timeout_seconds != 5 else other.preferences.timeout_seconds,
            max_workers=self.preferences.max_workers if self.preferences.max_workers != 16 else other.preferences.max_workers,
            package_managers=merged_pkg_mgrs,
            bulk=merged_bulk,
        )

        # Merge presets (this config takes priority)
        merged_presets = dict(other.presets)
        merged_presets.update(self.presets)

        # Prefer this config's environment mode if not auto
        merged_env_mode = self.environment_mode if self.environment_mode != "auto" else other.environment_mode

        return Config(
            version=self.version,
            environment_mode=merged_env_mode,
            tools=merged_tools,
            preferences=merged_preferences,
            presets=merged_presets,
            source=self.source or other.source,
        )


def _load_yaml(file_path: str) -> dict[str, Any] | None:
    """
    Load YAML configuration file.

    Args:
        file_path: Path to YAML file

    Returns:
        Parsed configuration dictionary, or None if YAML not available or file invalid
    """
    try:
        import yaml
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except ImportError:
        return None  # PyYAML not installed
    except (OSError, yaml.YAMLError):
        return None  # File not found or invalid YAML


def _load_json(file_path: str) -> dict[str, Any] | None:
    """
    Load JSON configuration file.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed configuration dictionary, or None if file invalid
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return None


def load_config_file(file_path: str, verbose: bool = False) -> Config | None:
    """
    Load configuration from a single file.

    Tries YAML first, falls back to JSON if YAML not available.

    Args:
        file_path: Path to configuration file
        verbose: Enable verbose logging

    Returns:
        Config object, or None if file cannot be loaded
    """
    if not os.path.exists(file_path):
        return None

    vlog(f"Loading config from: {file_path}", verbose)

    # Try YAML first
    data = _load_yaml(file_path)
    if data is None:
        # Try JSON fallback
        json_path = file_path.replace(".yml", ".json").replace(".yaml", ".json")
        if os.path.exists(json_path):
            vlog(f"YAML not available, trying JSON: {json_path}", verbose)
            data = _load_json(json_path)
        else:
            vlog(f"Could not load config from {file_path} (YAML parser not available)", verbose)
            return None

    if data is None:
        vlog(f"Invalid config file: {file_path}", verbose)
        return None

    try:
        config = Config.from_dict(data, source=file_path)
        vlog(f"Loaded config successfully: {file_path}", verbose)
        return config
    except (ValueError, TypeError) as e:
        vlog(f"Config validation failed for {file_path}: {e}", verbose)
        return None


def load_config(
    custom_path: str | None = None,
    verbose: bool = False,
) -> Config:
    """
    Load and merge configuration from all sources.

    Configuration precedence (highest to lowest):
    1. Custom path (if provided)
    2. Project .cli-audit.yml
    3. User ~/.config/cli-audit/config.yml
    4. System /etc/cli-audit/config.yml
    5. Default configuration

    Args:
        custom_path: Optional path to custom configuration file
        verbose: Enable verbose logging

    Returns:
        Merged Config object (never None, returns defaults if no config found)

    Raises:
        ValueError: If custom_path is provided but file cannot be loaded
    """
    configs: list[Config] = []

    # Try custom path first (highest priority)
    if custom_path:
        config = load_config_file(custom_path, verbose)
        if config is None:
            raise ValueError(f"Could not load config from specified path: {custom_path}")
        configs.append(config)
        vlog(f"Using custom config: {custom_path}", verbose)

    # Try standard locations
    for location in CONFIG_LOCATIONS:
        config = load_config_file(location, verbose)
        if config is not None:
            configs.append(config)
            vlog(f"Found config at: {location}", verbose)

    # If no configs found, return default
    if not configs:
        vlog("No config files found, using defaults", verbose)
        return Config()

    # Merge configs (first config has highest priority)
    merged = configs[0]
    for config in configs[1:]:
        merged = merged.merge_with(config)

    vlog(f"Merged {len(configs)} config files", verbose)
    return merged


def validate_config(config: Config) -> list[str]:
    """
    Validate configuration and return list of warnings/errors.

    Args:
        config: Config object to validate

    Returns:
        List of validation warning messages (empty if valid)
    """
    warnings = []

    # Check for unknown tools in config (informational only)
    # This would require importing TOOLS from core, so skip for now

    # Validate package manager hierarchies
    for lang, managers in config.preferences.package_managers.items():
        if not managers:
            warnings.append(f"Empty package manager list for {lang}")
        if len(managers) != len(set(managers)):
            warnings.append(f"Duplicate package managers in {lang} hierarchy")

    # Validate tool version specifications
    for tool_name, tool_config in config.tools.items():
        if tool_config.method == tool_config.fallback:
            warnings.append(
                f"Tool '{tool_name}': method and fallback are the same ({tool_config.method})"
            )

    return warnings
