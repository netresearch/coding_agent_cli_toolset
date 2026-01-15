"""
Tests for catalog entries and version collectors.

Covers:
- Claude Code catalog: version detection, install script, multi-method support
- PHP catalog: PPA support, package manager integration
- Composer: PHP dependency handling
- GitHub rate limit: authentication helpers, gh CLI integration
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent


class TestClaudeVersionDetection:
    """Tests for Claude Code version detection fix."""

    def test_claude_catalog_has_version_command(self):
        """Test that claude.json has a version_command field."""
        catalog_path = PROJECT_ROOT / "catalog" / "claude.json"
        assert catalog_path.exists(), "claude.json catalog file should exist"

        with open(catalog_path) as f:
            data = json.load(f)

        assert "version_command" in data, "claude.json should have version_command field"
        assert data["version_command"], "version_command should not be empty"

    def test_claude_catalog_version_command_format(self):
        """Test that claude.json version_command runs claude --version."""
        catalog_path = PROJECT_ROOT / "catalog" / "claude.json"

        with open(catalog_path) as f:
            data = json.load(f)

        version_cmd = data.get("version_command", "")
        # Should run claude --version directly for accurate detection
        # (package.json was unreliable - returned stale/incorrect versions)
        assert "claude" in version_cmd, "version_command should run claude binary"
        assert "--version" in version_cmd, "version_command should use --version flag"

    def test_claude_catalog_structure(self):
        """Test that claude.json has valid catalog structure."""
        catalog_path = PROJECT_ROOT / "catalog" / "claude.json"

        with open(catalog_path) as f:
            data = json.load(f)

        # Required fields for dedicated_script tools
        assert data.get("name") == "claude"
        assert data.get("install_method") == "dedicated_script"
        assert data.get("script") == "install_claude.sh"
        assert data.get("binary_name") == "claude"
        assert data.get("github_repo") == "anthropics/claude-code"

    def test_claude_catalog_has_notes_about_install_methods(self):
        """Test that claude.json documents installation methods."""
        catalog_path = PROJECT_ROOT / "catalog" / "claude.json"

        with open(catalog_path) as f:
            data = json.load(f)

        notes = data.get("notes", "")
        # Should mention native installer
        assert "native" in notes.lower() or "curl" in notes.lower()
        # Should mention Node.js version limitation
        assert "Node.js" in notes or "node" in notes.lower()


class TestClaudeInstallScript:
    """Tests for Claude Code install script."""

    def test_install_script_exists(self):
        """Test that install_claude.sh exists."""
        script_path = PROJECT_ROOT / "scripts" / "install_claude.sh"
        assert script_path.exists(), "install_claude.sh should exist"

    def test_install_script_is_executable(self):
        """Test that install_claude.sh is executable."""
        script_path = PROJECT_ROOT / "scripts" / "install_claude.sh"
        assert os.access(script_path, os.X_OK), "install_claude.sh should be executable"

    def test_install_script_uses_native_installer(self):
        """Test that install_claude.sh uses native installer as primary method."""
        script_path = PROJECT_ROOT / "scripts" / "install_claude.sh"
        content = script_path.read_text()

        # Should use official native installer
        assert "claude.ai/install.sh" in content
        # Should have fallbacks
        assert "homebrew" in content.lower() or "brew" in content
        assert "npm" in content

    def test_install_script_handles_node_version(self):
        """Test that install_claude.sh checks Node.js version for npm fallback."""
        script_path = PROJECT_ROOT / "scripts" / "install_claude.sh"
        content = script_path.read_text()

        # Should check Node.js version before npm install
        assert "node" in content.lower()
        assert "25" in content  # v25+ warning


class TestPHPCatalog:
    """Tests for PHP catalog entry."""

    def test_php_catalog_exists(self):
        """Test that php.json catalog file exists."""
        catalog_path = PROJECT_ROOT / "catalog" / "php.json"
        assert catalog_path.exists(), "php.json catalog file should exist"

    def test_php_catalog_valid_json(self):
        """Test that php.json is valid JSON."""
        catalog_path = PROJECT_ROOT / "catalog" / "php.json"

        with open(catalog_path) as f:
            data = json.load(f)  # Should not raise

        assert isinstance(data, dict)

    def test_php_catalog_required_fields(self):
        """Test that php.json has all required fields."""
        catalog_path = PROJECT_ROOT / "catalog" / "php.json"

        with open(catalog_path) as f:
            data = json.load(f)

        # Required fields
        assert data.get("name") == "php"
        assert data.get("category") == "php"
        assert data.get("install_method") == "package_manager"
        assert data.get("binary_name") == "php"

    def test_php_catalog_has_ppa(self):
        """Test that php.json has PPA for latest PHP on Ubuntu."""
        catalog_path = PROJECT_ROOT / "catalog" / "php.json"

        with open(catalog_path) as f:
            data = json.load(f)

        assert "ppa" in data, "php.json should have PPA field"
        assert "ondrej" in data["ppa"], "PHP PPA should be ondrej/php"

    def test_php_catalog_has_packages(self):
        """Test that php.json has package definitions for package managers."""
        catalog_path = PROJECT_ROOT / "catalog" / "php.json"

        with open(catalog_path) as f:
            data = json.load(f)

        assert "packages" in data, "php.json should have packages field"
        packages = data["packages"]

        # Should support common package managers
        assert "apt" in packages, "Should have apt package"
        assert "brew" in packages, "Should have brew package"

    def test_php_catalog_guide_order(self):
        """Test that PHP has guide section with proper order."""
        catalog_path = PROJECT_ROOT / "catalog" / "php.json"

        with open(catalog_path) as f:
            data = json.load(f)

        assert "guide" in data, "php.json should have guide section"
        guide = data["guide"]
        assert "order" in guide, "guide should have order field"
        # PHP should come before Composer (260)
        assert guide["order"] < 260, "PHP should have lower order than Composer"


class TestComposerRequiresPHP:
    """Tests for Composer's PHP dependency."""

    def test_composer_has_requires_field(self):
        """Test that composer.json has requires field with PHP."""
        catalog_path = PROJECT_ROOT / "catalog" / "composer.json"

        with open(catalog_path) as f:
            data = json.load(f)

        assert "requires" in data, "composer.json should have requires field"
        assert "php" in data["requires"], "Composer should require PHP"

    def test_composer_guide_order_after_php(self):
        """Test that Composer's guide order is after PHP."""
        php_path = PROJECT_ROOT / "catalog" / "php.json"
        composer_path = PROJECT_ROOT / "catalog" / "composer.json"

        with open(php_path) as f:
            php_data = json.load(f)
        with open(composer_path) as f:
            composer_data = json.load(f)

        php_order = php_data.get("guide", {}).get("order", 0)
        composer_order = composer_data.get("guide", {}).get("order", 999)

        assert composer_order > php_order, "Composer should be installed after PHP"


class TestInstallComposerPHPCheck:
    """Tests for install_composer.sh PHP dependency check."""

    def test_install_composer_checks_php(self):
        """Test that install_composer.sh checks for PHP."""
        script_path = PROJECT_ROOT / "scripts" / "install_composer.sh"
        assert script_path.exists(), "install_composer.sh should exist"

        content = script_path.read_text()

        # Should check for PHP
        assert "command -v php" in content, "Script should check for PHP"
        assert "Error: PHP is required" in content or "PHP is required" in content, \
            "Script should mention PHP requirement"


class TestGitHubRateLimitHelpers:
    """Tests for GitHub rate limit helper functions."""

    def test_get_github_rate_limit_help_exists(self):
        """Test that get_github_rate_limit_help function exists."""
        from cli_audit.collectors import get_github_rate_limit_help
        assert callable(get_github_rate_limit_help)

    def test_get_github_rate_limit_help_content(self):
        """Test that help message contains useful instructions."""
        from cli_audit.collectors import get_github_rate_limit_help

        help_text = get_github_rate_limit_help()

        # Should mention GITHUB_TOKEN
        assert "GITHUB_TOKEN" in help_text
        # Should mention gh CLI
        assert "gh auth" in help_text
        # Should include PAT creation URL
        assert "github.com/settings/tokens" in help_text
        # Should mention rate limits
        assert "5,000" in help_text or "5000" in help_text

    def test_get_gh_cli_token_exists(self):
        """Test that get_gh_cli_token function exists."""
        from cli_audit.collectors import get_gh_cli_token
        assert callable(get_gh_cli_token)

    @patch("shutil.which")
    def test_get_gh_cli_token_no_gh(self, mock_which):
        """Test get_gh_cli_token returns None when gh not installed."""
        from cli_audit.collectors import get_gh_cli_token

        mock_which.return_value = None
        result = get_gh_cli_token()
        assert result is None

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_get_gh_cli_token_not_authenticated(self, mock_which, mock_run):
        """Test get_gh_cli_token returns None when gh not authenticated."""
        from cli_audit.collectors import get_gh_cli_token

        mock_which.return_value = "/usr/bin/gh"
        mock_run.return_value = MagicMock(returncode=1)

        result = get_gh_cli_token()
        assert result is None

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_get_gh_cli_token_authenticated(self, mock_which, mock_run):
        """Test get_gh_cli_token returns token when gh is authenticated."""
        from cli_audit.collectors import get_gh_cli_token

        mock_which.return_value = "/usr/bin/gh"

        # First call: gh auth status (success)
        # Second call: gh auth token (returns token)
        mock_run.side_effect = [
            MagicMock(returncode=0),  # auth status
            MagicMock(returncode=0, stdout="ghp_testtoken123\n"),  # auth token
        ]

        result = get_gh_cli_token()
        assert result == "ghp_testtoken123"

    def test_get_github_rate_limit_returns_authenticated_field(self):
        """Test that get_github_rate_limit returns authenticated field."""
        from cli_audit.collectors import get_github_rate_limit

        # This is an integration test - it makes a real API call
        # We just check the structure is correct
        result = get_github_rate_limit()

        if result:  # May fail if network is unavailable
            assert "authenticated" in result
            assert "limit" in result
            assert "remaining" in result


class TestGitHubRateLimitDisplay:
    """Tests for rate limit display in audit.py."""

    def test_audit_imports_help_function(self):
        """Test that audit.py imports get_github_rate_limit_help."""
        import audit
        assert hasattr(audit, 'get_github_rate_limit_help') or \
               'get_github_rate_limit_help' in dir(audit)


class TestCatalogIntegrity:
    """Tests for overall catalog integrity."""

    def test_all_catalog_files_valid_json(self):
        """Test that all catalog files are valid JSON."""
        catalog_dir = PROJECT_ROOT / "catalog"

        for json_file in catalog_dir.glob("*.json"):
            with open(json_file) as f:
                try:
                    data = json.load(f)
                    assert isinstance(data, dict), f"{json_file.name} should contain a dict"
                except json.JSONDecodeError as e:
                    pytest.fail(f"{json_file.name} is not valid JSON: {e}")

    def test_all_catalog_files_have_name(self):
        """Test that all catalog files have a name field."""
        catalog_dir = PROJECT_ROOT / "catalog"

        for json_file in catalog_dir.glob("*.json"):
            with open(json_file) as f:
                data = json.load(f)
            assert "name" in data, f"{json_file.name} should have 'name' field"

    def test_all_catalog_files_have_install_method(self):
        """Test that all catalog files have an install_method field."""
        catalog_dir = PROJECT_ROOT / "catalog"

        for json_file in catalog_dir.glob("*.json"):
            with open(json_file) as f:
                data = json.load(f)
            assert "install_method" in data, f"{json_file.name} should have 'install_method' field"
