"""Tests for prerequisite resolution."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from cli_audit.prerequisites import (
    INSTALL_METHOD_PREREQUISITES,
    RUNTIME_PREREQUISITES,
    RUNTIME_BINARIES,
    is_tool_installed,
    resolve_prerequisites,
    check_prerequisites,
    ensure_prerequisites,
    format_prerequisite_error,
    PrerequisiteResult,
)


class TestInstallMethodPrerequisites:
    """Test install method prerequisite mapping."""

    def test_uv_tool_requires_uv(self):
        """uv_tool install method should require uv."""
        assert "uv" in INSTALL_METHOD_PREREQUISITES["uv_tool"]

    def test_npm_global_requires_node(self):
        """npm_global install method should require node."""
        assert "node" in INSTALL_METHOD_PREREQUISITES["npm_global"]

    def test_pip_requires_python(self):
        """pip install method should require python."""
        assert "python" in INSTALL_METHOD_PREREQUISITES["pip"]

    def test_cargo_requires_rust(self):
        """cargo install method should require rust."""
        assert "rust" in INSTALL_METHOD_PREREQUISITES["cargo"]


class TestRuntimePrerequisites:
    """Test runtime prerequisite chains."""

    def test_uv_requires_python(self):
        """uv runtime should require python."""
        assert "python" in RUNTIME_PREREQUISITES["uv"]

    def test_pipx_requires_python(self):
        """pipx runtime should require python."""
        assert "python" in RUNTIME_PREREQUISITES["pipx"]

    def test_composer_requires_php(self):
        """composer runtime should require php."""
        assert "php" in RUNTIME_PREREQUISITES["composer"]


class TestIsToolInstalled:
    """Test tool installation detection."""

    def test_tool_found_in_path(self):
        """Tool found in PATH should return True."""
        with patch("shutil.which", return_value="/usr/bin/python3"):
            assert is_tool_installed("python") is True

    def test_tool_not_found(self):
        """Tool not in PATH should return False."""
        with patch("shutil.which", return_value=None):
            assert is_tool_installed("nonexistent_tool") is False

    def test_python_fallback_to_python(self):
        """Python should check both python3 and python."""
        call_count = 0
        def mock_which(binary):
            nonlocal call_count
            call_count += 1
            if binary == "python3":
                return None
            elif binary == "python":
                return "/usr/bin/python"
            return None

        with patch("shutil.which", side_effect=mock_which):
            assert is_tool_installed("python") is True


class TestResolvePrerequisites:
    """Test prerequisite resolution."""

    def test_tool_with_no_prerequisites(self):
        """Tool with no prerequisites returns empty list."""
        mock_catalog = MagicMock()
        mock_catalog.get.return_value = None

        result = resolve_prerequisites("some_tool", mock_catalog)
        assert result == []

    def test_uv_tool_resolves_chain(self):
        """uv_tool method should resolve to [python, uv]."""
        mock_catalog = MagicMock()
        mock_entry = MagicMock()
        mock_entry.install_method = "uv_tool"

        def mock_get(name):
            if name == "ruff":
                return mock_entry
            return None

        mock_catalog.get.side_effect = mock_get

        result = resolve_prerequisites("ruff", mock_catalog)
        # Should include python (uv's prereq) and uv
        assert "python" in result
        assert "uv" in result
        # python should come before uv
        assert result.index("python") < result.index("uv")

    def test_npm_global_resolves_to_node(self):
        """npm_global method should resolve to [node]."""
        mock_catalog = MagicMock()
        mock_entry = MagicMock()
        mock_entry.install_method = "npm_global"

        def mock_get(name):
            if name == "prettier":
                return mock_entry
            return None

        mock_catalog.get.side_effect = mock_get

        result = resolve_prerequisites("prettier", mock_catalog)
        assert "node" in result

    def test_cycle_detection(self):
        """Cyclic dependencies should not cause infinite loop."""
        mock_catalog = MagicMock()

        # Both tools reference each other
        entry_a = MagicMock()
        entry_a.install_method = "custom"
        entry_b = MagicMock()
        entry_b.install_method = "custom"

        def mock_get(name):
            if name == "tool_a":
                return entry_a
            elif name == "tool_b":
                return entry_b
            return None

        mock_catalog.get.side_effect = mock_get

        # This should not raise or hang
        result = resolve_prerequisites("tool_a", mock_catalog)
        # Just verify it completes without error
        assert isinstance(result, list)


class TestCheckPrerequisites:
    """Test prerequisite checking."""

    def test_all_installed(self):
        """All installed prerequisites should be in installed list."""
        with patch("cli_audit.prerequisites.is_tool_installed", return_value=True):
            installed, missing = check_prerequisites(["python", "uv"])
            assert installed == ["python", "uv"]
            assert missing == []

    def test_all_missing(self):
        """All missing prerequisites should be in missing list."""
        with patch("cli_audit.prerequisites.is_tool_installed", return_value=False):
            installed, missing = check_prerequisites(["python", "uv"])
            assert installed == []
            assert missing == ["python", "uv"]

    def test_mixed_installed_and_missing(self):
        """Mixed prerequisites should be correctly categorized."""
        def mock_is_installed(tool, verbose=False):
            return tool == "python"

        with patch("cli_audit.prerequisites.is_tool_installed", side_effect=mock_is_installed):
            installed, missing = check_prerequisites(["python", "uv"])
            assert installed == ["python"]
            assert missing == ["uv"]


class TestEnsurePrerequisites:
    """Test ensure_prerequisites function."""

    def test_no_prerequisites_needed(self):
        """Tool with no prerequisites should return approved result."""
        mock_catalog = MagicMock()
        mock_catalog.get.return_value = None

        result = ensure_prerequisites("some_tool", mock_catalog, interactive=False)

        assert result.tool_name == "some_tool"
        assert result.prerequisites == []
        assert result.missing == []
        assert result.user_approved is True

    def test_all_prerequisites_installed(self):
        """All installed prerequisites should return approved result."""
        mock_catalog = MagicMock()
        mock_entry = MagicMock()
        mock_entry.install_method = "uv_tool"

        def mock_get(name):
            if name == "ruff":
                return mock_entry
            return None

        mock_catalog.get.side_effect = mock_get

        with patch("cli_audit.prerequisites.is_tool_installed", return_value=True):
            result = ensure_prerequisites("ruff", mock_catalog, interactive=False)

            assert result.user_approved is True
            assert result.missing == []

    def test_missing_prerequisites_non_interactive(self):
        """Missing prerequisites in non-interactive mode should not be approved."""
        mock_catalog = MagicMock()
        mock_entry = MagicMock()
        mock_entry.install_method = "uv_tool"

        def mock_get(name):
            if name == "ruff":
                return mock_entry
            return None

        mock_catalog.get.side_effect = mock_get

        with patch("cli_audit.prerequisites.is_tool_installed", return_value=False):
            result = ensure_prerequisites("ruff", mock_catalog, interactive=False)

            assert result.user_approved is False
            assert len(result.missing) > 0


class TestFormatPrerequisiteError:
    """Test error message formatting."""

    def test_user_declined_message(self):
        """User declined should produce appropriate message."""
        result = PrerequisiteResult(
            tool_name="ruff",
            prerequisites=["python", "uv"],
            missing=["python", "uv"],
            installed=[],
            user_approved=False,
            user_declined=["python", "uv"],
        )

        error = format_prerequisite_error(result)
        assert "user declined" in error.lower()
        assert "python" in error
        assert "uv" in error

    def test_missing_prerequisites_message(self):
        """Missing prerequisites should list what's missing."""
        result = PrerequisiteResult(
            tool_name="ruff",
            prerequisites=["python", "uv"],
            missing=["python"],
            installed=["uv"],
            user_approved=False,
            user_declined=[],
        )

        error = format_prerequisite_error(result)
        assert "missing" in error.lower()
        assert "python" in error

    def test_successful_result_empty_message(self):
        """Successful result should produce empty message."""
        result = PrerequisiteResult(
            tool_name="ruff",
            prerequisites=["python", "uv"],
            missing=[],
            installed=["python", "uv"],
            user_approved=True,
            user_declined=[],
        )

        error = format_prerequisite_error(result)
        assert error == ""
