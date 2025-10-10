"""
Tests for package manager selection (cli_audit/package_managers.py).

Target coverage: 90%+
"""

import pytest
from unittest.mock import patch, MagicMock
import subprocess

from cli_audit.package_managers import (
    PackageManager,
    PACKAGE_MANAGERS,
    get_package_manager,
    get_available_package_managers,
    get_default_hierarchy,
    select_package_manager,
    clear_cache,
)
from cli_audit.config import Config, ToolConfig, Preferences
from cli_audit.environment import Environment


class TestPackageManager:
    """Tests for PackageManager dataclass."""

    def test_package_manager_creation(self):
        """Test PackageManager object creation."""
        pm = PackageManager(
            name="uv",
            display_name="uv",
            check_command=("uv", "--version"),
            install_command_template=("uv", "tool", "install", "{package}"),
            category="vendor",
            languages=("python",),
        )
        assert pm.name == "uv"
        assert pm.display_name == "uv"
        assert pm.category == "vendor"
        assert "python" in pm.languages

    def test_package_manager_is_available_success(self):
        """Test is_available when command succeeds."""
        pm = PackageManager(
            name="test",
            display_name="Test",
            check_command=("python3", "--version"),  # Should exist
            install_command_template=("test", "install", "{package}"),
            category="test",
        )
        # Clear cache first
        clear_cache()
        assert pm.is_available() is True

    def test_package_manager_is_available_failure(self):
        """Test is_available when command fails."""
        pm = PackageManager(
            name="nonexistent",
            display_name="Nonexistent",
            check_command=("nonexistent_command_12345", "--version"),
            install_command_template=("nonexistent", "install", "{package}"),
            category="test",
        )
        clear_cache()
        assert pm.is_available() is False

    def test_package_manager_is_available_caching(self):
        """Test that availability checks are cached."""
        pm = PackageManager(
            name="cached_test",
            display_name="Cached Test",
            check_command=("python3", "--version"),
            install_command_template=("test", "install", "{package}"),
            category="test",
        )
        clear_cache()

        # First call
        result1 = pm.is_available()
        # Second call should use cache
        with patch("subprocess.run") as mock_run:
            result2 = pm.is_available()
            # subprocess.run should NOT be called (using cache)
            mock_run.assert_not_called()

        assert result1 == result2

    def test_package_manager_get_install_command(self):
        """Test get_install_command method."""
        pm = PackageManager(
            name="uv",
            display_name="uv",
            check_command=("uv", "--version"),
            install_command_template=("uv", "tool", "install", "{package}"),
            category="vendor",
        )
        command = pm.get_install_command("ripgrep")
        assert command == ("uv", "tool", "install", "ripgrep")

    def test_package_manager_get_install_command_with_version(self):
        """Test get_install_command with version."""
        pm = PackageManager(
            name="cargo",
            display_name="cargo",
            check_command=("cargo", "--version"),
            install_command_template=("cargo", "install", "{package}", "--version", "{version}"),
            category="vendor",
        )
        command = pm.get_install_command("ripgrep", "14.1.0")
        assert "ripgrep" in command
        assert "14.1.0" in command


class TestPackageManagerRegistry:
    """Tests for package manager registry."""

    def test_package_managers_registry_not_empty(self):
        """Test that PACKAGE_MANAGERS is not empty."""
        assert len(PACKAGE_MANAGERS) > 0

    def test_package_managers_have_required_fields(self):
        """Test that all package managers have required fields."""
        for pm in PACKAGE_MANAGERS:
            assert pm.name
            assert pm.display_name
            assert pm.check_command
            assert pm.install_command_template
            assert pm.category in {"vendor", "github", "system"}

    def test_get_package_manager_exists(self):
        """Test getting existing package manager."""
        pm = get_package_manager("uv")
        assert pm is not None
        assert pm.name == "uv"

    def test_get_package_manager_not_exists(self):
        """Test getting non-existent package manager."""
        pm = get_package_manager("nonexistent")
        assert pm is None

    def test_python_package_managers_exist(self):
        """Test that Python package managers are defined."""
        assert get_package_manager("uv") is not None
        assert get_package_manager("pipx") is not None
        assert get_package_manager("pip") is not None

    def test_rust_package_managers_exist(self):
        """Test that Rust package managers are defined."""
        assert get_package_manager("cargo") is not None
        assert get_package_manager("rustup") is not None

    def test_node_package_managers_exist(self):
        """Test that Node package managers are defined."""
        assert get_package_manager("npm") is not None
        assert get_package_manager("yarn") is not None
        assert get_package_manager("pnpm") is not None


class TestGetAvailablePackageManagers:
    """Tests for get_available_package_managers function."""

    @patch("cli_audit.package_managers.PackageManager.is_available")
    def test_get_available_all(self, mock_available):
        """Test getting all available package managers."""
        mock_available.return_value = True
        clear_cache()
        available = get_available_package_managers()
        assert len(available) > 0

    @patch("cli_audit.package_managers.PackageManager.is_available")
    def test_get_available_none(self, mock_available):
        """Test when no package managers are available."""
        mock_available.return_value = False
        clear_cache()
        available = get_available_package_managers()
        assert len(available) == 0

    @patch("cli_audit.package_managers.PackageManager.is_available")
    def test_get_available_filtered_by_language(self, mock_available):
        """Test filtering by language."""
        mock_available.return_value = True
        clear_cache()
        available = get_available_package_managers(languages=["python"])
        # Should only include package managers with python in languages
        for pm in available:
            if pm.languages:  # Some may have empty languages tuple
                assert "python" in pm.languages or not pm.languages


class TestGetDefaultHierarchy:
    """Tests for get_default_hierarchy function."""

    def test_get_default_hierarchy_python(self):
        """Test default hierarchy for Python."""
        hierarchy = get_default_hierarchy("python")
        assert "uv" in hierarchy
        assert "pipx" in hierarchy
        assert "pip" in hierarchy
        # uv should come before pip (preferred)
        assert hierarchy.index("uv") < hierarchy.index("pip")

    def test_get_default_hierarchy_rust(self):
        """Test default hierarchy for Rust."""
        hierarchy = get_default_hierarchy("rust")
        assert "rustup" in hierarchy or "cargo" in hierarchy

    def test_get_default_hierarchy_node(self):
        """Test default hierarchy for Node."""
        hierarchy = get_default_hierarchy("node")
        assert "nvm" in hierarchy or "npm" in hierarchy

    def test_get_default_hierarchy_unknown(self):
        """Test default hierarchy for unknown language."""
        hierarchy = get_default_hierarchy("unknown_lang")
        assert hierarchy == []


class TestSelectPackageManager:
    """Tests for select_package_manager function."""

    def setUp(self):
        """Clear cache before each test."""
        clear_cache()

    def test_select_with_config_override(self):
        """Test selection with explicit config override."""
        config = Config(tools={"python": ToolConfig(method="uv")})
        env = Environment(mode="workstation", confidence=1.0)

        with patch("cli_audit.package_managers.PackageManager.is_available", return_value=True):
            clear_cache()
            pm_name, reason = select_package_manager("python", "python", config, env)
            assert pm_name == "uv"
            assert reason == "config_override"

    def test_select_with_language_hierarchy(self):
        """Test selection using language hierarchy."""
        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        # Mock: uv available, pipx not
        def mock_is_available(self):
            return self.name == "uv"

        with patch("cli_audit.package_managers.PackageManager.is_available", mock_is_available):
            clear_cache()
            pm_name, reason = select_package_manager("black", "python", config, env)
            assert pm_name == "uv"
            assert "hierarchy" in reason

    def test_select_with_custom_hierarchy(self):
        """Test selection with custom package manager hierarchy."""
        prefs = Preferences(package_managers={"python": ["pip", "uv"]})
        config = Config(preferences=prefs)
        env = Environment(mode="workstation", confidence=1.0)

        # Mock: both available
        with patch("cli_audit.package_managers.PackageManager.is_available", return_value=True):
            clear_cache()
            pm_name, reason = select_package_manager("black", "python", config, env)
            # Should use custom hierarchy (pip first)
            assert pm_name == "pip"

    def test_select_server_environment_prefers_system(self):
        """Test that server environment prefers system packages."""
        config = Config()
        env = Environment(mode="server", confidence=0.8)

        # Mock: apt available, uv not
        def mock_is_available(self):
            return self.name == "apt"

        with patch("cli_audit.package_managers.PackageManager.is_available", mock_is_available):
            with patch("cli_audit.package_managers.get_default_hierarchy", return_value=["uv", "apt"]):
                clear_cache()
                pm_name, reason = select_package_manager("tool", "python", config, env)
                assert pm_name == "apt"
                assert "server" in reason

    def test_select_with_fallback(self):
        """Test selection using fallback method."""
        config = Config(tools={"python": ToolConfig(method="nonexistent", fallback="pip")})
        env = Environment(mode="workstation", confidence=1.0)

        def mock_is_available(self):
            return self.name == "pip"

        # Mock hierarchy to not include pip, so fallback is actually used
        with patch("cli_audit.package_managers.PackageManager.is_available", mock_is_available):
            with patch("cli_audit.package_managers.get_default_hierarchy", return_value=["uv", "pipx"]):
                clear_cache()
                pm_name, reason = select_package_manager("python", "python", config, env)
                assert pm_name == "pip"
                assert reason == "config_fallback"

    def test_select_no_language_specified(self):
        """Test selection when no language specified."""
        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        with patch("cli_audit.package_managers.get_available_package_managers") as mock_get:
            mock_pm = MagicMock()
            mock_pm.name = "cargo"
            mock_pm.category = "vendor"
            mock_get.return_value = [mock_pm]
            clear_cache()

            pm_name, reason = select_package_manager("tool", None, config, env)
            assert pm_name == "cargo"
            assert "first_available" in reason

    def test_select_no_package_managers_available(self):
        """Test that ValueError is raised when no package managers available."""
        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        with patch("cli_audit.package_managers.PackageManager.is_available", return_value=False):
            with patch("cli_audit.package_managers.get_available_package_managers", return_value=[]):
                clear_cache()
                with pytest.raises(ValueError, match="No suitable package manager found"):
                    select_package_manager("tool", "python", config, env)


class TestCacheClear:
    """Tests for cache management."""

    def test_clear_cache(self):
        """Test that clear_cache actually clears the cache."""
        pm = PackageManager(
            name="test_cache",
            display_name="Test Cache",
            check_command=("python3", "--version"),
            install_command_template=("test", "install", "{package}"),
            category="test",
        )

        # Prime the cache
        clear_cache()
        pm.is_available()

        # Clear cache
        clear_cache()

        # Next call should hit subprocess again
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            pm.is_available()
            # Should be called because cache was cleared
            mock_run.assert_called_once()
