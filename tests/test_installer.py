"""
Tests for installation execution (cli_audit/installer.py).

Target coverage: 85%+
"""

import hashlib
import pytest
import tempfile
from unittest.mock import patch, MagicMock, call
from pathlib import Path

from cli_audit.installer import (
    StepResult,
    InstallResult,
    InstallError,
    is_retryable_error,
    calculate_backoff_delay,
    execute_step,
    execute_step_with_retry,
    verify_checksum,
    validate_installation,
    install_tool,
)
from cli_audit.install_plan import InstallStep
from cli_audit.config import Config
from cli_audit.environment import Environment


class TestStepResult:
    """Tests for StepResult dataclass."""

    def test_step_result_creation(self):
        """Test StepResult object creation."""
        step = InstallStep("Test step", ("test", "command"), estimated_time_seconds=10)
        result = StepResult(
            step=step,
            success=True,
            stdout="Success output",
            stderr="",
            exit_code=0,
            duration_seconds=5.2,
        )
        assert result.success is True
        assert result.stdout == "Success output"
        assert result.exit_code == 0
        assert result.duration_seconds == 5.2
        assert result.attempt_number == 1  # Default

    def test_step_result_failure(self):
        """Test StepResult for failed step."""
        step = InstallStep("Failing step", ("false",))
        result = StepResult(
            step=step,
            success=False,
            stdout="",
            stderr="Command failed",
            exit_code=1,
            duration_seconds=0.1,
            error_message="Command failed with exit code 1",
        )
        assert result.success is False
        assert result.exit_code == 1
        assert result.error_message is not None

    def test_step_result_to_dict(self):
        """Test StepResult to_dict method."""
        step = InstallStep("Test", ("echo", "hello"))
        result = StepResult(
            step=step,
            success=True,
            stdout="hello",
            stderr="",
            exit_code=0,
            duration_seconds=0.5,
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["exit_code"] == 0
        assert "step" in data

    def test_step_result_immutable(self):
        """Test that StepResult is immutable."""
        step = InstallStep("Test", ("test",))
        result = StepResult(
            step=step,
            success=True,
            stdout="",
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
        )
        with pytest.raises(AttributeError):
            result.success = False  # Should fail (frozen)


class TestInstallResult:
    """Tests for InstallResult dataclass."""

    def test_install_result_success(self):
        """Test InstallResult for successful installation."""
        step = InstallStep("Install", ("cargo", "install", "ripgrep"))
        step_result = StepResult(
            step=step,
            success=True,
            stdout="Installed",
            stderr="",
            exit_code=0,
            duration_seconds=60.0,
        )
        result = InstallResult(
            tool_name="ripgrep",
            success=True,
            installed_version="14.1.1",
            package_manager_used="cargo",
            steps_completed=(step_result,),
            duration_seconds=65.0,
            validation_passed=True,
            binary_path="/usr/local/bin/ripgrep",
        )
        assert result.success is True
        assert result.installed_version == "14.1.1"
        assert result.validation_passed is True
        assert result.binary_path is not None

    def test_install_result_failure(self):
        """Test InstallResult for failed installation."""
        result = InstallResult(
            tool_name="nonexistent",
            success=False,
            installed_version=None,
            package_manager_used="cargo",
            steps_completed=(),
            duration_seconds=5.0,
            error_message="Package not found",
        )
        assert result.success is False
        assert result.installed_version is None
        assert result.error_message is not None

    def test_install_result_to_dict(self):
        """Test InstallResult to_dict method."""
        result = InstallResult(
            tool_name="test",
            success=True,
            installed_version="1.0.0",
            package_manager_used="pip",
            steps_completed=(),
            duration_seconds=10.0,
        )
        data = result.to_dict()
        assert data["tool_name"] == "test"
        assert data["success"] is True
        assert data["installed_version"] == "1.0.0"


class TestInstallError:
    """Tests for InstallError exception."""

    def test_install_error_creation(self):
        """Test InstallError creation."""
        error = InstallError("Test error", retryable=True, remediation="Try again")
        assert error.message == "Test error"
        assert error.retryable is True
        assert error.remediation == "Try again"

    def test_install_error_raising(self):
        """Test raising InstallError."""
        with pytest.raises(InstallError) as exc_info:
            raise InstallError("Something failed")
        assert "Something failed" in str(exc_info.value)


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_network_errors_are_retryable(self):
        """Test that network errors are retryable."""
        assert is_retryable_error(1, "connection refused") is True
        assert is_retryable_error(1, "connection timed out") is True
        assert is_retryable_error(1, "network unreachable") is True
        assert is_retryable_error(1, "could not resolve host") is True

    def test_lock_errors_are_retryable(self):
        """Test that lock errors are retryable."""
        assert is_retryable_error(1, "could not get lock") is True
        assert is_retryable_error(1, "lock file exists") is True
        assert is_retryable_error(1, "waiting for cache lock") is True

    def test_retryable_exit_codes(self):
        """Test that certain exit codes are retryable."""
        assert is_retryable_error(75, "") is True  # EAGAIN
        assert is_retryable_error(111, "") is True  # Connection refused
        assert is_retryable_error(128, "") is True  # Git error

    def test_non_retryable_errors(self):
        """Test that other errors are not retryable."""
        assert is_retryable_error(1, "permission denied") is False
        assert is_retryable_error(2, "command not found") is False
        assert is_retryable_error(127, "package not found") is False


class TestCalculateBackoffDelay:
    """Tests for calculate_backoff_delay function."""

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        delay0 = calculate_backoff_delay(0, base_delay=1.0, max_delay=30.0)
        delay1 = calculate_backoff_delay(1, base_delay=1.0, max_delay=30.0)
        delay2 = calculate_backoff_delay(2, base_delay=1.0, max_delay=30.0)

        # Delays should generally increase (accounting for jitter)
        assert 0.8 <= delay0 <= 1.5  # 1.0 ± 20%
        assert 1.6 <= delay1 <= 3.0  # 2.0 ± 20%
        assert 3.2 <= delay2 <= 6.0  # 4.0 ± 20%

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        delay = calculate_backoff_delay(10, base_delay=1.0, max_delay=10.0)
        assert delay <= 12.0  # Max delay + jitter

    def test_minimum_delay(self):
        """Test that delay is always positive."""
        delay = calculate_backoff_delay(0, base_delay=0.0, max_delay=1.0)
        assert delay >= 0.1  # Minimum delay


class TestExecuteStep:
    """Tests for execute_step function."""

    @patch("subprocess.run")
    def test_execute_step_success(self, mock_run):
        """Test successful step execution."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Success",
            stderr="",
        )

        step = InstallStep("Test step", ("echo", "hello"))
        result = execute_step(step)

        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "Success"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_execute_step_failure(self, mock_run):
        """Test failed step execution."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error occurred",
        )

        step = InstallStep("Failing step", ("false",))
        result = execute_step(step)

        assert result.success is False
        assert result.exit_code == 1
        assert result.error_message is not None
        assert "exit code 1" in result.error_message

    @patch("subprocess.run")
    def test_execute_step_with_sudo(self, mock_run):
        """Test step execution with sudo."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        step = InstallStep("Install", ("apt", "install", "tool"), requires_sudo=True)
        execute_step(step)

        # Should call with sudo prepended
        called_command = mock_run.call_args[0][0]
        assert called_command[0] == "sudo"
        assert "apt" in called_command

    @patch("subprocess.run")
    def test_execute_step_timeout(self, mock_run):
        """Test step execution timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["sleep", "100"],
            timeout=5,
        )

        step = InstallStep("Long running", ("sleep", "100"))
        result = execute_step(step, timeout=5)

        assert result.success is False
        assert "timed out" in result.error_message.lower()

    @patch("subprocess.run")
    def test_execute_step_command_not_found(self, mock_run):
        """Test step execution with command not found."""
        mock_run.side_effect = FileNotFoundError()

        step = InstallStep("Missing command", ("nonexistent_command",))
        result = execute_step(step)

        assert result.success is False
        assert "not found" in result.error_message.lower()


class TestExecuteStepWithRetry:
    """Tests for execute_step_with_retry function."""

    @patch("cli_audit.installer.execute_step")
    @patch("cli_audit.installer.time.sleep")
    def test_retry_on_transient_failure(self, mock_sleep, mock_execute):
        """Test retry logic for transient failures."""
        # First two attempts fail (retryable), third succeeds
        mock_execute.side_effect = [
            StepResult(
                step=InstallStep("Test", ("test",)),
                success=False,
                stdout="",
                stderr="connection refused",
                exit_code=1,
                duration_seconds=1.0,
            ),
            StepResult(
                step=InstallStep("Test", ("test",)),
                success=False,
                stdout="",
                stderr="connection refused",
                exit_code=1,
                duration_seconds=1.0,
            ),
            StepResult(
                step=InstallStep("Test", ("test",)),
                success=True,
                stdout="Success",
                stderr="",
                exit_code=0,
                duration_seconds=1.0,
            ),
        ]

        step = InstallStep("Test", ("test",))
        result = execute_step_with_retry(step, max_retries=3)

        assert result.success is True
        assert mock_execute.call_count == 3
        assert mock_sleep.call_count == 2  # Two retries with sleep

    @patch("cli_audit.installer.execute_step")
    def test_no_retry_on_non_retryable_failure(self, mock_execute):
        """Test that non-retryable errors are not retried."""
        mock_execute.return_value = StepResult(
            step=InstallStep("Test", ("test",)),
            success=False,
            stdout="",
            stderr="permission denied",
            exit_code=1,
            duration_seconds=1.0,
        )

        step = InstallStep("Test", ("test",))
        result = execute_step_with_retry(step, max_retries=3)

        assert result.success is False
        assert mock_execute.call_count == 1  # No retries

    @patch("cli_audit.installer.execute_step")
    @patch("cli_audit.installer.time.sleep")
    def test_max_retries_reached(self, mock_sleep, mock_execute):
        """Test that retries stop at max_retries."""
        mock_execute.return_value = StepResult(
            step=InstallStep("Test", ("test",)),
            success=False,
            stdout="",
            stderr="connection refused",
            exit_code=1,
            duration_seconds=1.0,
        )

        step = InstallStep("Test", ("test",))
        result = execute_step_with_retry(step, max_retries=3)

        assert result.success is False
        assert mock_execute.call_count == 3  # All retries exhausted


class TestVerifyChecksum:
    """Tests for verify_checksum function."""

    def test_verify_checksum_success(self, tmp_path):
        """Test successful checksum verification."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        # Calculate expected checksum
        hasher = hashlib.sha256()
        hasher.update(b"Hello, World!")
        expected = hasher.hexdigest()

        result = verify_checksum(str(test_file), expected, algorithm="sha256")
        assert result is True

    def test_verify_checksum_mismatch(self, tmp_path):
        """Test checksum mismatch."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        wrong_checksum = "0" * 64  # Wrong checksum
        result = verify_checksum(str(test_file), wrong_checksum, algorithm="sha256")
        assert result is False

    def test_verify_checksum_file_not_found(self):
        """Test checksum verification with non-existent file."""
        result = verify_checksum("/nonexistent/file.txt", "abc123")
        assert result is False

    def test_verify_checksum_case_insensitive(self, tmp_path):
        """Test that checksum comparison is case-insensitive."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        hasher = hashlib.sha256()
        hasher.update(b"test")
        expected_lower = hasher.hexdigest().lower()
        expected_upper = hasher.hexdigest().upper()

        assert verify_checksum(str(test_file), expected_lower) is True
        assert verify_checksum(str(test_file), expected_upper) is True


class TestValidateInstallation:
    """Tests for validate_installation function."""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_validate_installation_success(self, mock_run, mock_which):
        """Test successful installation validation."""
        mock_which.return_value = "/usr/bin/ripgrep"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ripgrep 14.1.1",
            stderr="",
        )

        success, path, version = validate_installation("ripgrep")

        assert success is True
        assert path == "/usr/bin/ripgrep"
        assert version == "14.1.1"

    @patch("shutil.which")
    def test_validate_installation_binary_not_found(self, mock_which):
        """Test validation when binary not in PATH."""
        mock_which.return_value = None

        success, path, version = validate_installation("nonexistent")

        assert success is False
        assert path is None
        assert version is None

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_validate_installation_version_detection_fails(self, mock_run, mock_which):
        """Test validation when version cannot be determined."""
        mock_which.return_value = "/usr/bin/tool"
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

        success, path, version = validate_installation("tool")

        # Should still succeed if binary exists, even without version
        assert success is True
        assert path == "/usr/bin/tool"
        assert version is None

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_validate_installation_multiple_version_formats(self, mock_run, mock_which):
        """Test version extraction from various formats."""
        mock_which.return_value = "/usr/bin/tool"

        # Test different version output formats
        test_cases = [
            ("tool 1.2.3", "1.2.3"),
            ("version 2.0.0-alpha", "2.0.0"),
            ("v3.4.5", "3.4.5"),
            ("10.11.12", "10.11.12"),
        ]

        for stdout, expected_version in test_cases:
            mock_run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
            success, path, version = validate_installation("tool")
            assert success is True
            assert version is not None


class TestInstallTool:
    """Tests for install_tool function."""

    @patch("cli_audit.installer.select_package_manager")
    @patch("cli_audit.installer.generate_install_plan")
    @patch("cli_audit.installer.execute_step_with_retry")
    @patch("cli_audit.installer.validate_installation")
    def test_install_tool_success(
        self,
        mock_validate,
        mock_execute,
        mock_generate_plan,
        mock_select_pm,
    ):
        """Test successful tool installation."""
        from cli_audit.install_plan import InstallPlan

        # Setup mocks
        mock_select_pm.return_value = ("cargo", "hierarchy")
        steps = (
            InstallStep("Check cargo", ("cargo", "--version")),
            InstallStep("Install ripgrep", ("cargo", "install", "ripgrep")),
        )
        mock_generate_plan.return_value = InstallPlan(
            tool_name="ripgrep",
            target_version="14.1.1",
            package_manager="cargo",
            steps=steps,
        )
        mock_execute.return_value = StepResult(
            step=steps[0],
            success=True,
            stdout="cargo 1.70.0",
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
        )
        mock_validate.return_value = (True, "/usr/bin/ripgrep", "14.1.1")

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = install_tool(
            tool_name="ripgrep",
            package_name="ripgrep",
            target_version="14.1.1",
            config=config,
            env=env,
            language="rust",
        )

        assert result.success is True
        assert result.tool_name == "ripgrep"
        assert result.installed_version == "14.1.1"
        assert result.validation_passed is True

    @patch("cli_audit.installer.select_package_manager")
    @patch("cli_audit.installer.generate_install_plan")
    def test_install_tool_dry_run(self, mock_generate_plan, mock_select_pm):
        """Test dry-run mode."""
        from cli_audit.install_plan import InstallPlan

        mock_select_pm.return_value = ("cargo", "hierarchy")
        mock_generate_plan.return_value = InstallPlan(
            tool_name="ripgrep",
            target_version="14.1.1",
            package_manager="cargo",
            steps=(),
        )

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = install_tool(
            tool_name="ripgrep",
            package_name="ripgrep",
            config=config,
            env=env,
            dry_run=True,
        )

        assert result.success is True
        assert len(result.steps_completed) == 0  # No steps executed

    @patch("cli_audit.installer.select_package_manager")
    @patch("cli_audit.installer.generate_install_plan")
    @patch("cli_audit.installer.execute_step_with_retry")
    def test_install_tool_step_failure(
        self,
        mock_execute,
        mock_generate_plan,
        mock_select_pm,
    ):
        """Test installation with step failure."""
        from cli_audit.install_plan import InstallPlan

        mock_select_pm.return_value = ("cargo", "hierarchy")
        steps = (InstallStep("Install", ("cargo", "install", "nonexistent")),)
        mock_generate_plan.return_value = InstallPlan(
            tool_name="nonexistent",
            target_version="1.0.0",
            package_manager="cargo",
            steps=steps,
        )
        mock_execute.return_value = StepResult(
            step=steps[0],
            success=False,
            stdout="",
            stderr="package not found",
            exit_code=1,
            duration_seconds=5.0,
            error_message="Package not found",
        )

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = install_tool(
            tool_name="nonexistent",
            package_name="nonexistent",
            config=config,
            env=env,
        )

        assert result.success is False
        assert result.error_message is not None
        assert "not found" in result.error_message.lower()

    @patch("cli_audit.installer.select_package_manager")
    @patch("cli_audit.installer.generate_install_plan")
    @patch("cli_audit.installer.execute_step_with_retry")
    @patch("cli_audit.installer.validate_installation")
    def test_install_tool_validation_failure(
        self,
        mock_validate,
        mock_execute,
        mock_generate_plan,
        mock_select_pm,
    ):
        """Test installation with post-install validation failure."""
        from cli_audit.install_plan import InstallPlan

        mock_select_pm.return_value = ("cargo", "hierarchy")
        steps = (InstallStep("Install", ("cargo", "install", "tool")),)
        mock_generate_plan.return_value = InstallPlan(
            tool_name="tool",
            target_version="1.0.0",
            package_manager="cargo",
            steps=steps,
        )
        mock_execute.return_value = StepResult(
            step=steps[0],
            success=True,
            stdout="Installed",
            stderr="",
            exit_code=0,
            duration_seconds=30.0,
        )
        # Validation fails (binary not in PATH)
        mock_validate.return_value = (False, None, None)

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = install_tool(
            tool_name="tool",
            package_name="tool",
            config=config,
            env=env,
        )

        # Installation steps succeeded but validation failed
        assert result.success is False
        assert result.validation_passed is False
        assert len(result.steps_completed) > 0
