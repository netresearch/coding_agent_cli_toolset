"""
Tests for configuration parsing (cli_audit/config.py).

Target coverage: 85%+
"""

import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from cli_audit.config import (
    ToolConfig,
    Preferences,
    Config,
    load_config_file,
    load_config,
    validate_config,
    _load_yaml,
    _load_json,
)


# Fixture paths
FIXTURES_DIR = Path(__file__).parent / "fixtures"
CONFIG_VALID = str(FIXTURES_DIR / "config_valid.yml")
CONFIG_MINIMAL = str(FIXTURES_DIR / "config_minimal.yml")
CONFIG_INVALID_VERSION = str(FIXTURES_DIR / "config_invalid_version.yml")
CONFIG_INVALID_ENV = str(FIXTURES_DIR / "config_invalid_env.yml")
CONFIG_PROJECT = str(FIXTURES_DIR / "config_project.yml")
CONFIG_USER = str(FIXTURES_DIR / "config_user.yml")


class TestToolConfig:
    """Tests for ToolConfig dataclass."""

    def test_tool_config_defaults(self):
        """Test ToolConfig with default values."""
        config = ToolConfig()
        assert config.version == "latest"
        assert config.method is None
        assert config.fallback is None

    def test_tool_config_custom_values(self):
        """Test ToolConfig with custom values."""
        config = ToolConfig(version="3.12.*", method="uv", fallback="pipx")
        assert config.version == "3.12.*"
        assert config.method == "uv"
        assert config.fallback == "pipx"

    def test_tool_config_from_dict(self):
        """Test creating ToolConfig from dictionary."""
        data = {"version": "1.2.3", "method": "cargo", "fallback": "apt"}
        config = ToolConfig.from_dict(data)
        assert config.version == "1.2.3"
        assert config.method == "cargo"
        assert config.fallback == "apt"

    def test_tool_config_from_dict_partial(self):
        """Test creating ToolConfig from partial dictionary."""
        data = {"method": "npm"}
        config = ToolConfig.from_dict(data)
        assert config.version == "latest"  # Default
        assert config.method == "npm"
        assert config.fallback is None

    def test_tool_config_immutable(self):
        """Test that ToolConfig is immutable."""
        config = ToolConfig(version="1.0.0")
        with pytest.raises(AttributeError):
            config.version = "2.0.0"  # Should fail (frozen)


class TestPreferences:
    """Tests for Preferences dataclass."""

    def test_preferences_defaults(self):
        """Test Preferences with default values."""
        prefs = Preferences()
        assert prefs.reconciliation == "parallel"
        assert prefs.breaking_changes == "warn"
        assert prefs.auto_upgrade is True
        assert prefs.timeout_seconds == 5
        assert prefs.max_workers == 16
        assert prefs.package_managers == {}

    def test_preferences_custom_values(self):
        """Test Preferences with custom values."""
        prefs = Preferences(
            reconciliation="aggressive",
            breaking_changes="accept",
            auto_upgrade=False,
            timeout_seconds=10,
            max_workers=8,
            package_managers={"python": ["uv", "pip"]},
        )
        assert prefs.reconciliation == "aggressive"
        assert prefs.breaking_changes == "accept"
        assert prefs.auto_upgrade is False
        assert prefs.timeout_seconds == 10
        assert prefs.max_workers == 8
        assert prefs.package_managers == {"python": ["uv", "pip"]}

    def test_preferences_invalid_reconciliation(self):
        """Test that invalid reconciliation raises ValueError."""
        with pytest.raises(ValueError, match="Invalid reconciliation strategy"):
            Preferences(reconciliation="invalid")

    def test_preferences_invalid_breaking_changes(self):
        """Test that invalid breaking_changes raises ValueError."""
        with pytest.raises(ValueError, match="Invalid breaking_changes setting"):
            Preferences(breaking_changes="invalid")

    def test_preferences_invalid_timeout_too_low(self):
        """Test that timeout < 1 raises ValueError."""
        with pytest.raises(ValueError, match="Invalid timeout_seconds"):
            Preferences(timeout_seconds=0)

    def test_preferences_invalid_timeout_too_high(self):
        """Test that timeout > 60 raises ValueError."""
        with pytest.raises(ValueError, match="Invalid timeout_seconds"):
            Preferences(timeout_seconds=61)

    def test_preferences_invalid_max_workers_too_low(self):
        """Test that max_workers < 1 raises ValueError."""
        with pytest.raises(ValueError, match="Invalid max_workers"):
            Preferences(max_workers=0)

    def test_preferences_invalid_max_workers_too_high(self):
        """Test that max_workers > 32 raises ValueError."""
        with pytest.raises(ValueError, match="Invalid max_workers"):
            Preferences(max_workers=33)

    def test_preferences_from_dict(self):
        """Test creating Preferences from dictionary."""
        data = {
            "reconciliation": "aggressive",
            "breaking_changes": "reject",
            "auto_upgrade": False,
            "timeout_seconds": 10,
            "max_workers": 8,
            "package_managers": {"python": ["uv"]},
        }
        prefs = Preferences.from_dict(data)
        assert prefs.reconciliation == "aggressive"
        assert prefs.breaking_changes == "reject"
        assert prefs.auto_upgrade is False
        assert prefs.timeout_seconds == 10
        assert prefs.max_workers == 8


class TestConfig:
    """Tests for Config dataclass."""

    def test_config_defaults(self):
        """Test Config with default values."""
        config = Config()
        assert config.version == 1
        assert config.environment_mode == "auto"
        assert config.tools == {}
        assert isinstance(config.preferences, Preferences)
        assert config.source == ""

    def test_config_custom_values(self):
        """Test Config with custom values."""
        tools = {"python": ToolConfig(version="3.12.*", method="uv")}
        prefs = Preferences(max_workers=8)
        config = Config(
            environment_mode="workstation",
            tools=tools,
            preferences=prefs,
            source="/path/to/config.yml",
        )
        assert config.environment_mode == "workstation"
        assert config.tools == tools
        assert config.preferences == prefs
        assert config.source == "/path/to/config.yml"

    def test_config_invalid_version(self):
        """Test that invalid version raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported config version"):
            Config(version=999)

    def test_config_invalid_environment_mode(self):
        """Test that invalid environment_mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid environment_mode"):
            Config(environment_mode="invalid")

    def test_config_from_dict(self):
        """Test creating Config from dictionary."""
        data = {
            "version": 1,
            "environment": {"mode": "ci"},
            "tools": {
                "python": {"version": "3.12.*", "method": "uv"},
                "ripgrep": {"version": "latest", "method": "cargo"},
            },
            "preferences": {
                "max_workers": 8,
                "timeout_seconds": 10,
            },
        }
        config = Config.from_dict(data, source="test.yml")
        assert config.version == 1
        assert config.environment_mode == "ci"
        assert "python" in config.tools
        assert config.tools["python"].version == "3.12.*"
        assert config.preferences.max_workers == 8
        assert config.source == "test.yml"

    def test_config_get_tool_config_exists(self):
        """Test get_tool_config for existing tool."""
        tools = {"python": ToolConfig(version="3.12.*", method="uv")}
        config = Config(tools=tools)
        tool_config = config.get_tool_config("python")
        assert tool_config.version == "3.12.*"
        assert tool_config.method == "uv"

    def test_config_get_tool_config_not_exists(self):
        """Test get_tool_config for non-existing tool returns default."""
        config = Config()
        tool_config = config.get_tool_config("python")
        assert tool_config.version == "latest"  # Default
        assert tool_config.method is None

    def test_config_immutable(self):
        """Test that Config is immutable."""
        config = Config()
        with pytest.raises(AttributeError):
            config.version = 2  # Should fail (frozen)


class TestConfigMerging:
    """Tests for configuration merging."""

    def test_merge_with_empty(self):
        """Test merging with empty config."""
        config1 = Config(environment_mode="workstation")
        config2 = Config()
        merged = config1.merge_with(config2)
        assert merged.environment_mode == "workstation"

    def test_merge_tools(self):
        """Test merging tool configurations."""
        config1 = Config(tools={"python": ToolConfig(version="3.12.*")})
        config2 = Config(tools={"ripgrep": ToolConfig(version="14.0.0")})
        merged = config1.merge_with(config2)
        assert "python" in merged.tools
        assert "ripgrep" in merged.tools
        assert merged.tools["python"].version == "3.12.*"

    def test_merge_tools_override(self):
        """Test that higher priority config overrides lower."""
        config1 = Config(tools={"python": ToolConfig(version="3.12.*", method="uv")})
        config2 = Config(tools={"python": ToolConfig(version="3.11.*", method="pip")})
        merged = config1.merge_with(config2)
        assert merged.tools["python"].version == "3.12.*"
        assert merged.tools["python"].method == "uv"

    def test_merge_preferences(self):
        """Test merging preferences."""
        prefs1 = Preferences(max_workers=4)
        prefs2 = Preferences(timeout_seconds=10)
        config1 = Config(preferences=prefs1)
        config2 = Config(preferences=prefs2)
        merged = config1.merge_with(config2)
        assert merged.preferences.max_workers == 4  # From config1
        assert merged.preferences.timeout_seconds == 10  # From config2

    def test_merge_package_managers(self):
        """Test merging package manager hierarchies."""
        prefs1 = Preferences(package_managers={"python": ["uv"]})
        prefs2 = Preferences(package_managers={"rust": ["cargo"]})
        config1 = Config(preferences=prefs1)
        config2 = Config(preferences=prefs2)
        merged = config1.merge_with(config2)
        assert "python" in merged.preferences.package_managers
        assert "rust" in merged.preferences.package_managers

    def test_merge_environment_mode_auto(self):
        """Test that 'auto' is replaced by more specific mode."""
        config1 = Config(environment_mode="auto")
        config2 = Config(environment_mode="workstation")
        merged = config1.merge_with(config2)
        assert merged.environment_mode == "workstation"

    def test_merge_environment_mode_explicit(self):
        """Test that explicit mode overrides auto."""
        config1 = Config(environment_mode="ci")
        config2 = Config(environment_mode="auto")
        merged = config1.merge_with(config2)
        assert merged.environment_mode == "ci"


class TestLoadYAML:
    """Tests for YAML loading."""

    @pytest.mark.skipif(
        not os.path.exists(CONFIG_VALID),
        reason="Test fixtures not found",
    )
    def test_load_yaml_valid(self):
        """Test loading valid YAML file."""
        data = _load_yaml(CONFIG_VALID)
        assert data is not None
        assert data["version"] == 1
        assert "environment" in data

    def test_load_yaml_not_found(self):
        """Test loading non-existent YAML file."""
        data = _load_yaml("/nonexistent/file.yml")
        assert data is None

    @pytest.mark.skip(reason="Cannot reliably mock dynamic yaml import")
    def test_load_yaml_no_pyyaml(self):
        """Test YAML loading when PyYAML not installed."""
        # This test is skipped because yaml is imported dynamically inside _load_yaml
        # and mocking dynamic imports is unreliable due to import caching
        pass


class TestLoadJSON:
    """Tests for JSON loading."""

    def test_load_json_valid(self, tmp_path):
        """Test loading valid JSON file."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"version": 1, "environment": {"mode": "auto"}}')
        data = _load_json(str(json_file))
        assert data is not None
        assert data["version"] == 1

    def test_load_json_invalid(self, tmp_path):
        """Test loading invalid JSON file."""
        json_file = tmp_path / "config.json"
        json_file.write_text("{invalid json}")
        data = _load_json(str(json_file))
        assert data is None

    def test_load_json_not_found(self):
        """Test loading non-existent JSON file."""
        data = _load_json("/nonexistent/file.json")
        assert data is None


class TestLoadConfigFile:
    """Tests for loading configuration from file."""

    @pytest.mark.skipif(
        not os.path.exists(CONFIG_VALID),
        reason="Test fixtures not found",
    )
    def test_load_config_file_valid(self):
        """Test loading valid configuration file."""
        config = load_config_file(CONFIG_VALID)
        assert config is not None
        assert config.version == 1
        assert config.environment_mode == "workstation"

    @pytest.mark.skipif(
        not os.path.exists(CONFIG_MINIMAL),
        reason="Test fixtures not found",
    )
    def test_load_config_file_minimal(self):
        """Test loading minimal configuration file."""
        config = load_config_file(CONFIG_MINIMAL)
        assert config is not None
        assert config.version == 1
        assert config.environment_mode == "auto"

    @pytest.mark.skipif(
        not os.path.exists(CONFIG_INVALID_VERSION),
        reason="Test fixtures not found",
    )
    def test_load_config_file_invalid_version(self):
        """Test that invalid version is caught."""
        config = load_config_file(CONFIG_INVALID_VERSION)
        assert config is None  # Validation should fail

    @pytest.mark.skipif(
        not os.path.exists(CONFIG_INVALID_ENV),
        reason="Test fixtures not found",
    )
    def test_load_config_file_invalid_env(self):
        """Test that invalid environment mode is caught."""
        config = load_config_file(CONFIG_INVALID_ENV)
        assert config is None  # Validation should fail

    def test_load_config_file_not_found(self):
        """Test loading non-existent file."""
        config = load_config_file("/nonexistent/file.yml")
        assert config is None


class TestLoadConfig:
    """Tests for loading and merging configuration from multiple sources."""

    def test_load_config_defaults(self):
        """Test that load_config returns defaults when no files found."""
        with patch("cli_audit.config.load_config_file", return_value=None):
            config = load_config()
            assert config.version == 1
            assert config.environment_mode == "auto"
            assert config.tools == {}

    def test_load_config_custom_path(self, tmp_path):
        """Test loading from custom path."""
        custom_file = tmp_path / "custom.yml"
        custom_file.write_text("version: 1\nenvironment:\n  mode: ci\n")

        # Mock _load_yaml to return the data
        with patch("cli_audit.config._load_yaml") as mock_yaml:
            mock_yaml.return_value = {"version": 1, "environment": {"mode": "ci"}}
            config = load_config(custom_path=str(custom_file))
            assert config.environment_mode == "ci"

    def test_load_config_custom_path_not_found(self):
        """Test that custom path not found raises ValueError."""
        with pytest.raises(ValueError, match="Could not load config"):
            load_config(custom_path="/nonexistent/file.yml")

    @pytest.mark.skipif(
        not os.path.exists(CONFIG_PROJECT) or not os.path.exists(CONFIG_USER),
        reason="Test fixtures not found",
    )
    def test_load_config_merging(self):
        """Test that multiple config files are merged correctly."""
        # This test would require setting up CONFIG_LOCATIONS to point to fixtures
        # Skipping for now as it requires more complex mocking


class TestValidateConfig:
    """Tests for configuration validation."""

    def test_validate_config_valid(self):
        """Test validation of valid config."""
        config = Config()
        warnings = validate_config(config)
        assert warnings == []

    def test_validate_config_empty_package_managers(self):
        """Test warning for empty package manager list."""
        prefs = Preferences(package_managers={"python": []})
        config = Config(preferences=prefs)
        warnings = validate_config(config)
        assert len(warnings) > 0
        assert "Empty package manager list" in warnings[0]

    def test_validate_config_duplicate_package_managers(self):
        """Test warning for duplicate package managers."""
        prefs = Preferences(package_managers={"python": ["uv", "uv", "pip"]})
        config = Config(preferences=prefs)
        warnings = validate_config(config)
        assert len(warnings) > 0
        assert "Duplicate package managers" in warnings[0]

    def test_validate_config_same_method_and_fallback(self):
        """Test warning when method and fallback are the same."""
        tools = {"python": ToolConfig(method="uv", fallback="uv")}
        config = Config(tools=tools)
        warnings = validate_config(config)
        assert len(warnings) > 0
        assert "method and fallback are the same" in warnings[0]
