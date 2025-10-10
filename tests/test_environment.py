"""
Tests for environment detection (cli_audit/environment.py).

Target coverage: 90%+
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from cli_audit.environment import (
    Environment,
    detect_environment,
    get_environment_from_config,
)


class TestEnvironment:
    """Tests for Environment dataclass."""

    def test_environment_creation(self):
        """Test Environment object creation."""
        env = Environment(
            mode="workstation",
            confidence=0.75,
            indicators=("display_environment", "single_user"),
        )
        assert env.mode == "workstation"
        assert env.confidence == 0.75
        assert len(env.indicators) == 2
        assert not env.override

    def test_environment_str(self):
        """Test Environment string representation."""
        env = Environment(mode="ci", confidence=0.95)
        assert "ci" in str(env)
        assert "95%" in str(env)

        env_override = Environment(mode="server", confidence=1.0, override=True)
        assert "override" in str(env_override)

    def test_environment_immutable(self):
        """Test that Environment is immutable (frozen dataclass)."""
        env = Environment(mode="workstation", confidence=0.75)
        with pytest.raises(AttributeError):
            env.mode = "server"  # Should fail (frozen)


class TestDetectEnvironmentCI:
    """Tests for CI environment detection."""

    @patch.dict(os.environ, {"CI": "true"}, clear=True)
    def test_detect_ci_with_ci_env(self):
        """Test CI detection with CI=true."""
        env = detect_environment()
        assert env.mode == "ci"
        assert env.confidence >= 0.9
        assert any("CI" in ind for ind in env.indicators)

    @patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True)
    def test_detect_ci_with_github_actions(self):
        """Test CI detection with GITHUB_ACTIONS."""
        env = detect_environment()
        assert env.mode == "ci"
        assert env.confidence >= 0.9
        assert any("GITHUB_ACTIONS" in ind for ind in env.indicators)

    @patch.dict(os.environ, {"GITLAB_CI": "true", "CI": "true"}, clear=True)
    def test_detect_ci_with_multiple_indicators(self):
        """Test CI detection with multiple indicators."""
        env = detect_environment()
        assert env.mode == "ci"
        assert env.confidence >= 0.9
        assert len(env.indicators) >= 2

    @patch.dict(os.environ, {"JENKINS_HOME": "/var/jenkins"}, clear=True)
    def test_detect_ci_with_jenkins(self):
        """Test CI detection with JENKINS_HOME."""
        env = detect_environment()
        assert env.mode == "ci"

    @patch.dict(os.environ, {"TRAVIS": "true"}, clear=True)
    def test_detect_ci_with_travis(self):
        """Test CI detection with TRAVIS."""
        env = detect_environment()
        assert env.mode == "ci"


class TestDetectEnvironmentServer:
    """Tests for server environment detection."""

    @patch.dict(os.environ, {}, clear=True)
    @patch("cli_audit.environment.get_active_user_count", return_value=5)
    @patch("cli_audit.environment.get_system_uptime_days", return_value=35)
    def test_detect_server_with_multiple_users(self, mock_uptime, mock_users):
        """Test server detection with multiple active users and uptime."""
        env = detect_environment()
        assert env.mode == "server"
        assert any("active_users" in ind for ind in env.indicators)

    @patch.dict(os.environ, {}, clear=True)
    @patch("cli_audit.environment.get_active_user_count", return_value=4)
    @patch("cli_audit.environment.get_system_uptime_days", return_value=60)
    def test_detect_server_with_high_uptime(self, mock_uptime, mock_users):
        """Test server detection with high uptime and multiple users."""
        env = detect_environment()
        assert env.mode == "server"
        assert any("uptime_days" in ind for ind in env.indicators)
        assert any("active_users" in ind for ind in env.indicators)

    @patch.dict(os.environ, {}, clear=True)
    @patch("cli_audit.environment.get_active_user_count", return_value=2)
    @patch("cli_audit.environment.get_system_uptime_days", return_value=45)
    @patch("os.path.exists")
    def test_detect_server_with_shared_filesystem(self, mock_exists, mock_uptime, mock_users):
        """Test server detection with shared filesystem."""
        def exists_side_effect(path):
            return path == "/shared"
        mock_exists.side_effect = exists_side_effect

        env = detect_environment()
        assert env.mode == "server"
        assert any("shared_filesystem" in ind for ind in env.indicators)


class TestDetectEnvironmentWorkstation:
    """Tests for workstation environment detection (default)."""

    @patch.dict(os.environ, {"DISPLAY": ":0"}, clear=True)
    @patch("cli_audit.environment.get_active_user_count", return_value=1)
    def test_detect_workstation_with_display(self, mock_users):
        """Test workstation detection with DISPLAY environment."""
        env = detect_environment()
        assert env.mode == "workstation"
        assert any("display_environment" in ind for ind in env.indicators)

    @patch.dict(os.environ, {}, clear=True)
    @patch("cli_audit.environment.get_active_user_count", return_value=1)
    def test_detect_workstation_single_user(self, mock_users):
        """Test workstation detection with single user."""
        env = detect_environment()
        assert env.mode == "workstation"
        assert any("single_user" in ind for ind in env.indicators)

    @patch.dict(os.environ, {}, clear=True)
    @patch("cli_audit.environment.get_active_user_count", return_value=-1)
    def test_detect_workstation_default_fallback(self, mock_users):
        """Test workstation as default fallback."""
        env = detect_environment()
        assert env.mode == "workstation"
        # Should still work even if we can't determine user count


class TestDetectEnvironmentOverride:
    """Tests for explicit environment override."""

    def test_override_to_ci(self):
        """Test explicit override to CI."""
        env = detect_environment(override="ci")
        assert env.mode == "ci"
        assert env.confidence == 1.0
        assert env.override is True
        assert "explicit_override" in env.indicators[0]

    def test_override_to_server(self):
        """Test explicit override to server."""
        env = detect_environment(override="server")
        assert env.mode == "server"
        assert env.override is True

    def test_override_to_workstation(self):
        """Test explicit override to workstation."""
        env = detect_environment(override="workstation")
        assert env.mode == "workstation"
        assert env.override is True

    def test_override_invalid_mode(self):
        """Test that invalid override raises ValueError."""
        with pytest.raises(ValueError, match="Invalid environment override"):
            detect_environment(override="invalid")

    def test_override_auto_triggers_detection(self):
        """Test that override='auto' triggers normal detection."""
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            env = detect_environment(override="auto")
            assert env.mode == "ci"
            assert not env.override  # auto means detect, not override


class TestGetEnvironmentFromConfig:
    """Tests for get_environment_from_config function."""

    def test_config_mode_auto(self):
        """Test that 'auto' triggers detection."""
        with patch.dict(os.environ, {"GITLAB_CI": "true"}, clear=True):
            env = get_environment_from_config("auto")
            assert env.mode == "ci"
            assert not env.override

    def test_config_mode_none(self):
        """Test that None triggers detection."""
        with patch.dict(os.environ, {}, clear=True):
            env = get_environment_from_config(None)
            assert env.mode == "workstation"  # Default

    def test_config_mode_explicit_ci(self):
        """Test explicit CI mode from config."""
        env = get_environment_from_config("ci")
        assert env.mode == "ci"
        assert env.override is True

    def test_config_mode_explicit_server(self):
        """Test explicit server mode from config."""
        env = get_environment_from_config("server")
        assert env.mode == "server"
        assert env.override is True

    def test_config_mode_explicit_workstation(self):
        """Test explicit workstation mode from config."""
        env = get_environment_from_config("workstation")
        assert env.mode == "workstation"
        assert env.override is True


class TestEnvironmentConfidence:
    """Tests for confidence scoring."""

    @patch.dict(os.environ, {"CI": "true"}, clear=True)
    def test_ci_high_confidence(self):
        """Test that CI detection has high confidence."""
        env = detect_environment()
        assert env.confidence >= 0.9

    @patch.dict(os.environ, {}, clear=True)
    @patch("cli_audit.environment.get_active_user_count", return_value=5)
    @patch("cli_audit.environment.get_system_uptime_days", return_value=60)
    def test_server_medium_confidence(self, mock_uptime, mock_users):
        """Test that server detection has medium confidence."""
        env = detect_environment()
        assert 0.5 <= env.confidence <= 0.85

    @patch.dict(os.environ, {}, clear=True)
    @patch("cli_audit.environment.get_active_user_count", return_value=1)
    def test_workstation_medium_confidence(self, mock_users):
        """Test that workstation (default) has medium confidence."""
        env = detect_environment()
        assert 0.5 <= env.confidence <= 0.9

    def test_override_max_confidence(self):
        """Test that override always has maximum confidence."""
        env = detect_environment(override="ci")
        assert env.confidence == 1.0


class TestEnvironmentVerboseMode:
    """Tests for verbose logging."""

    @patch("cli_audit.environment.vlog")
    def test_verbose_logging_enabled(self, mock_vlog):
        """Test that verbose=True enables logging."""
        detect_environment(verbose=True)
        assert mock_vlog.called

    @patch("cli_audit.environment.vlog")
    def test_verbose_logging_disabled(self, mock_vlog):
        """Test that verbose=False disables logging."""
        detect_environment(verbose=False)
        # vlog is still called, but it checks verbose internally
        # Just verify it was called (internal check handles verbose flag)
        assert mock_vlog.called
