"""
Common utilities shared across cli_audit modules.
"""

from __future__ import annotations

import os
import sys
from typing import Any


def is_ci_environment() -> bool:
    """
    Check if running in a CI/CD environment.

    Returns:
        True if CI indicators are present, False otherwise.
    """
    ci_indicators = [
        "CI",
        "CONTINUOUS_INTEGRATION",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "CIRCLECI",
        "TRAVIS",
        "JENKINS_HOME",
        "BUILDKITE",
        "DRONE",
        "SEMAPHORE",
        "APPVEYOR",
        "CODEBUILD_BUILD_ID",
        "TF_BUILD",  # Azure Pipelines
    ]
    return any(os.environ.get(var) for var in ci_indicators)


def get_active_user_count() -> int:
    """
    Get approximate count of active users on system.

    Returns:
        Number of unique users with active sessions, or -1 if cannot determine.
    """
    try:
        # Try using 'who' command to count unique logged-in users
        import subprocess
        result = subprocess.run(
            ["who"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            # Count unique usernames
            users = set()
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split()
                    if parts:
                        users.add(parts[0])
            return len(users)
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    return -1


def get_system_uptime_days() -> int:
    """
    Get system uptime in days.

    Returns:
        Uptime in days, or -1 if cannot determine.
    """
    try:
        # Try reading /proc/uptime on Linux
        if os.path.exists("/proc/uptime"):
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.read().split()[0])
                return int(uptime_seconds / 86400)  # Convert to days
    except Exception:
        pass

    try:
        # Try using 'uptime' command
        import subprocess
        result = subprocess.run(
            ["uptime", "-s"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            # Parse boot time and calculate days
            from datetime import datetime
            boot_time = datetime.fromisoformat(result.stdout.strip())
            uptime = datetime.now() - boot_time
            return uptime.days
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, Exception):
        pass

    return -1


def vlog(msg: str, verbose: bool = False) -> None:
    """
    Log verbose message using structured logging.

    This function maintains backward compatibility with the old print-based
    vlog while using the new logging framework.

    Args:
        msg: Message to log
        verbose: Whether verbose mode is enabled
    """
    if verbose or os.environ.get("CLI_AUDIT_DEBUG", "0") == "1":
        try:
            # Use new logging framework
            from .logging_config import get_logger
            logger = get_logger()
            logger.info(msg)
        except Exception:
            # Fallback to stderr if logging fails
            try:
                print(f"[cli_audit] {msg}", file=sys.stderr)
            except Exception:
                pass
