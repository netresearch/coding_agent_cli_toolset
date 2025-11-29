"""
Installation execution and validation.

Executes installation plans with retry logic, checksum verification,
and post-install validation.
"""

from __future__ import annotations

import hashlib
import random
import shutil
import subprocess
import time
from dataclasses import dataclass

from .common import vlog
from .config import Config
from .environment import Environment
from .install_plan import InstallStep, generate_install_plan
from .package_managers import select_package_manager


@dataclass(frozen=True)
class StepResult:
    """
    Result of executing a single installation step.

    Attributes:
        step: The installation step that was executed
        success: Whether the step succeeded
        stdout: Standard output from command execution
        stderr: Standard error from command execution
        exit_code: Process exit code
        duration_seconds: Time taken to execute step
        error_message: Human-readable error message if failed
        attempt_number: Which retry attempt this was (1-indexed)
    """
    step: InstallStep
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    error_message: str | None = None
    attempt_number: int = 1

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "step": self.step.to_dict(),
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "attempt_number": self.attempt_number,
        }


@dataclass(frozen=True)
class InstallResult:
    """
    Complete result of tool installation.

    Attributes:
        tool_name: Name of the tool that was installed
        success: Whether installation succeeded
        installed_version: Actual version installed (may differ from target)
        package_manager_used: Package manager that performed installation
        steps_completed: Steps that completed successfully
        duration_seconds: Total installation time
        checksum_verified: Whether checksum was verified (if applicable)
        validation_passed: Whether post-install validation succeeded
        error_message: Human-readable error message if failed
        binary_path: Path to installed binary (if validation passed)
    """
    tool_name: str
    success: bool
    installed_version: str | None
    package_manager_used: str
    steps_completed: tuple[StepResult, ...]
    duration_seconds: float
    checksum_verified: bool = False
    validation_passed: bool = False
    error_message: str | None = None
    binary_path: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "installed_version": self.installed_version,
            "package_manager_used": self.package_manager_used,
            "steps_completed": [step.to_dict() for step in self.steps_completed],
            "duration_seconds": self.duration_seconds,
            "checksum_verified": self.checksum_verified,
            "validation_passed": self.validation_passed,
            "error_message": self.error_message,
            "binary_path": self.binary_path,
        }


class InstallError(Exception):
    """
    Base exception for installation errors.

    Attributes:
        message: Human-readable error message
        retryable: Whether this error can be retried
        remediation: Suggested fix for the error
    """
    def __init__(
        self,
        message: str,
        retryable: bool = False,
        remediation: str | None = None,
    ):
        self.message = message
        self.retryable = retryable
        self.remediation = remediation
        super().__init__(message)


def is_retryable_error(exit_code: int, stderr: str) -> bool:
    """
    Determine if an error is retryable.

    Args:
        exit_code: Process exit code
        stderr: Standard error output

    Returns:
        True if error is transient and should be retried
    """
    # Network-related errors
    if any(indicator in stderr.lower() for indicator in [
        "connection refused",
        "connection timed out",
        "connection reset",
        "temporary failure",
        "network unreachable",
        "could not resolve host",
    ]):
        return True

    # Package manager lock contention
    if any(indicator in stderr.lower() for indicator in [
        "could not get lock",
        "lock file exists",
        "waiting for cache lock",
        "dpkg frontend lock",
    ]):
        return True

    # Temporary failure exit codes
    if exit_code in {75, 111, 128}:  # EAGAIN, connection refused, git error
        return True

    return False


def calculate_backoff_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    """
    Calculate exponential backoff delay with jitter.

    Args:
        attempt: Retry attempt number (0-indexed)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds with jitter applied
    """
    # Exponential backoff: base * 2^attempt
    delay = base_delay * (2 ** attempt)
    delay = min(delay, max_delay)

    # Add jitter (±20%)
    jitter = delay * 0.2 * (random.random() * 2 - 1)
    return max(0.1, delay + jitter)  # type: ignore[no-any-return]


def execute_step(
    step: InstallStep,
    timeout: int | None = None,
    verbose: bool = False,
) -> StepResult:
    """
    Execute a single installation step.

    Args:
        step: Installation step to execute
        timeout: Command timeout in seconds
        verbose: Enable verbose logging

    Returns:
        StepResult with execution outcome
    """
    start_time = time.time()

    # Build command with sudo if needed
    command = list(step.command)
    if step.requires_sudo:
        command = ["sudo"] + command

    vlog(f"Executing: {' '.join(command)}", verbose)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        duration = time.time() - start_time
        success = result.returncode == 0

        error_msg = None
        if not success:
            error_msg = f"Command failed with exit code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr[:200]}"

        return StepResult(
            step=step,
            success=success,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            duration_seconds=duration,
            error_message=error_msg,
        )

    except subprocess.TimeoutExpired as e:
        duration = time.time() - start_time
        return StepResult(
            step=step,
            success=False,
            stdout=e.stdout.decode() if e.stdout else "",
            stderr=e.stderr.decode() if e.stderr else "",
            exit_code=-1,
            duration_seconds=duration,
            error_message=f"Command timed out after {timeout}s",
        )
    except FileNotFoundError:
        duration = time.time() - start_time
        return StepResult(
            step=step,
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            duration_seconds=duration,
            error_message=f"Command not found: {command[0]}",
        )
    except Exception as e:
        duration = time.time() - start_time
        return StepResult(
            step=step,
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            duration_seconds=duration,
            error_message=f"Unexpected error: {str(e)}",
        )


def execute_step_with_retry(
    step: InstallStep,
    max_retries: int = 3,
    timeout: int | None = None,
    verbose: bool = False,
) -> StepResult:
    """
    Execute step with retry logic for transient failures.

    Args:
        step: Installation step to execute
        max_retries: Maximum number of retry attempts
        timeout: Command timeout in seconds
        verbose: Enable verbose logging

    Returns:
        StepResult with final outcome
    """
    for attempt in range(max_retries):
        vlog(f"Attempt {attempt + 1}/{max_retries} for: {step.description}", verbose)

        result = execute_step(step, timeout, verbose)

        if result.success:
            # Update attempt number in result
            return StepResult(
                step=result.step,
                success=result.success,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                duration_seconds=result.duration_seconds,
                error_message=result.error_message,
                attempt_number=attempt + 1,
            )

        # Check if error is retryable
        if not is_retryable_error(result.exit_code, result.stderr):
            vlog(f"Non-retryable error: {result.error_message}", verbose)
            return result

        # Last attempt failed
        if attempt == max_retries - 1:
            vlog(f"Max retries reached: {result.error_message}", verbose)
            return result

        # Wait before retry
        delay = calculate_backoff_delay(attempt)
        vlog(f"Retrying after {delay:.1f}s delay...", verbose)
        time.sleep(delay)

    return result  # Should never reach here, but satisfy type checker


def verify_checksum(
    file_path: str,
    expected_checksum: str,
    algorithm: str = "sha256",
) -> bool:
    """
    Verify file checksum matches expected value.

    Args:
        file_path: Path to file to verify
        expected_checksum: Expected checksum value
        algorithm: Hash algorithm (sha256, sha512, md5)

    Returns:
        True if checksum matches, False otherwise
    """
    try:
        hasher = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)

        actual_checksum = hasher.hexdigest()
        return actual_checksum.lower() == expected_checksum.lower()

    except Exception:
        return False


def validate_installation(
    tool_name: str,
    expected_version: str | None = None,
    verbose: bool = False,
) -> tuple[bool, str | None, str | None]:
    """
    Validate that tool is correctly installed and accessible.

    Args:
        tool_name: Name of tool to validate
        expected_version: Expected version (optional)
        verbose: Enable verbose logging

    Returns:
        Tuple of (success, binary_path, actual_version)
    """
    # Check if binary exists in PATH
    binary_path = shutil.which(tool_name)
    if not binary_path:
        vlog(f"Binary not found in PATH: {tool_name}", verbose)
        return (False, None, None)

    vlog(f"Found binary at: {binary_path}", verbose)

    # Try to get version
    version_commands = [
        (tool_name, "--version"),
        (tool_name, "-V"),
        (tool_name, "version"),
    ]

    actual_version = None
    for cmd in version_commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                # Extract version from output (first line, first version-like pattern)
                import re
                version_pattern = r'\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?'
                match = re.search(version_pattern, result.stdout)
                if match:
                    actual_version = match.group(0)
                    vlog(f"Detected version: {actual_version}", verbose)
                    break
        except Exception:
            continue

    if not actual_version:
        vlog(f"Could not determine version for {tool_name}", verbose)

    # Validation succeeds if binary exists, regardless of version detection
    return (True, binary_path, actual_version)


def install_tool(
    tool_name: str,
    package_name: str,
    target_version: str = "latest",
    config: Config | None = None,
    env: Environment | None = None,
    language: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> InstallResult:
    """
    Install a single tool.

    Args:
        tool_name: Display name of the tool
        package_name: Package name for installation
        target_version: Target version to install
        config: Configuration object (loads defaults if None)
        env: Environment object (detects if None)
        language: Tool language/ecosystem (e.g., "python", "rust")
        dry_run: If True, only generate plan without executing
        verbose: Enable verbose logging

    Returns:
        InstallResult with installation outcome

    Raises:
        InstallError: If installation fails critically
    """
    from .config import load_config
    from .environment import detect_environment

    # Load config and environment if not provided
    if config is None:
        config = load_config(verbose=verbose)
    if env is None:
        env = detect_environment(verbose=verbose)

    start_time = time.time()

    try:
        # Select package manager
        pm_name, reason = select_package_manager(
            tool_name=tool_name,
            language=language,
            config=config,
            env=env,
            verbose=verbose,
        )
        vlog(f"Selected package manager: {pm_name} (reason: {reason})", verbose)

        # Generate installation plan
        plan = generate_install_plan(
            tool_name=tool_name,
            package_name=package_name,
            target_version=target_version,
            package_manager_name=pm_name,
        )

        if dry_run:
            vlog("Dry-run mode: Not executing installation", verbose)
            return InstallResult(
                tool_name=tool_name,
                success=True,
                installed_version=target_version,
                package_manager_used=pm_name,
                steps_completed=(),
                duration_seconds=0.0,
            )

        # Execute installation steps
        steps_completed: list[StepResult] = []
        timeout = config.preferences.timeout_seconds

        for step in plan.steps:
            vlog(f"Executing step: {step.description}", verbose)

            result = execute_step_with_retry(
                step=step,
                max_retries=3,
                timeout=timeout,
                verbose=verbose,
            )

            steps_completed.append(result)

            if not result.success:
                # Installation failed
                duration = time.time() - start_time
                error_msg = f"Installation failed at step: {step.description}"
                if result.error_message:
                    error_msg += f"\n{result.error_message}"

                return InstallResult(
                    tool_name=tool_name,
                    success=False,
                    installed_version=None,
                    package_manager_used=pm_name,
                    steps_completed=tuple(steps_completed),
                    duration_seconds=duration,
                    error_message=error_msg,
                )

        # All steps completed successfully
        vlog("All installation steps completed", verbose)

        # Validate installation
        validation_success, binary_path, actual_version = validate_installation(
            tool_name=tool_name.lower(),
            expected_version=target_version,
            verbose=verbose,
        )

        duration = time.time() - start_time

        if not validation_success:
            vlog(f"Post-install validation failed for {tool_name}", verbose)

        return InstallResult(
            tool_name=tool_name,
            success=validation_success,
            installed_version=actual_version or target_version,
            package_manager_used=pm_name,
            steps_completed=tuple(steps_completed),
            duration_seconds=duration,
            validation_passed=validation_success,
            binary_path=binary_path,
        )

    except Exception as e:
        duration = time.time() - start_time
        vlog(f"Installation error: {str(e)}", verbose)
        return InstallResult(
            tool_name=tool_name,
            success=False,
            installed_version=None,
            package_manager_used="unknown",
            steps_completed=(),
            duration_seconds=duration,
            error_message=f"Installation error: {str(e)}",
        )
