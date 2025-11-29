"""
Environment detection for context-aware installation strategies.

Detects whether running in:
- CI/CD environment (ephemeral, reproducible)
- Server environment (multi-user, system-level)
- Workstation environment (single-user, user-level)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .common import is_ci_environment, get_active_user_count, get_system_uptime_days, vlog


@dataclass(frozen=True)
class Environment:
    """
    Detected environment information.

    Attributes:
        mode: Environment type ('ci', 'server', or 'workstation')
        confidence: Confidence level (0.0-1.0)
        indicators: Evidence for the detection decision
        override: Whether mode was explicitly overridden by user
    """
    mode: str
    confidence: float
    indicators: tuple[str, ...] = ()
    override: bool = False

    def __str__(self) -> str:
        override_str = " (override)" if self.override else ""
        confidence_pct = int(self.confidence * 100)
        return f"{self.mode}{override_str} (confidence: {confidence_pct}%)"


def detect_environment(override: str | None = None, verbose: bool = False) -> Environment:
    """
    Detect the environment type for context-aware installation.

    Detection priority:
    1. Explicit override (if provided)
    2. CI/CD indicators (highest confidence)
    3. Server indicators (medium confidence)
    4. Workstation (default fallback)

    Args:
        override: Explicit environment mode ('ci', 'server', 'workstation', or None)
        verbose: Enable verbose logging

    Returns:
        Environment object with detected or overridden mode

    Raises:
        ValueError: If override value is not valid
    """
    valid_modes = {"ci", "server", "workstation"}

    # Handle explicit override
    if override and override != "auto":
        if override not in valid_modes:
            raise ValueError(
                f"Invalid environment override: {override}. "
                f"Must be one of: {', '.join(sorted(valid_modes))}"
            )
        vlog(f"Environment explicitly set to: {override}", verbose)
        return Environment(
            mode=override,
            confidence=1.0,
            indicators=(f"explicit_override={override}",),
            override=True,
        )

    # Check CI indicators (highest priority, highest confidence)
    if is_ci_environment():
        indicators = []
        ci_env_vars = [
            "CI", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI", "TRAVIS",
            "JENKINS_HOME", "BUILDKITE", "DRONE", "SEMAPHORE"
        ]
        for var in ci_env_vars:
            if os.environ.get(var):
                indicators.append(f"env:{var}={os.environ[var]}")

        vlog(f"CI environment detected: {indicators}", verbose)
        return Environment(
            mode="ci",
            confidence=0.95,
            indicators=tuple(indicators),
        )

    # Check server indicators (medium priority, medium confidence)
    indicators = []
    server_score = 0.0

    # Check for multiple active users
    user_count = get_active_user_count()
    if user_count > 3:
        indicators.append(f"active_users={user_count}")
        server_score += 0.3
    elif user_count > 1:
        indicators.append(f"active_users={user_count}")
        server_score += 0.15

    # Check system uptime (servers typically have high uptime)
    uptime_days = get_system_uptime_days()
    if uptime_days > 30:
        indicators.append(f"uptime_days={uptime_days}")
        server_score += 0.25
    elif uptime_days > 7:
        indicators.append(f"uptime_days={uptime_days}")
        server_score += 0.1

    # Check for server-like paths
    if os.path.exists("/shared") or os.path.exists("/export"):
        indicators.append("shared_filesystem")
        server_score += 0.2

    # Check if running as system service (no DISPLAY, no SSH_CONNECTION)
    if not os.environ.get("DISPLAY") and not os.environ.get("SSH_CONNECTION"):
        if not os.environ.get("WAYLAND_DISPLAY"):
            indicators.append("no_display_environment")
            server_score += 0.1

    if server_score >= 0.5:
        vlog(f"Server environment detected (score: {server_score:.2f}): {indicators}", verbose)
        return Environment(
            mode="server",
            confidence=min(server_score, 0.85),  # Cap at 85% for server heuristics
            indicators=tuple(indicators),
        )

    # Default to workstation (safe fallback)
    workstation_indicators = []

    # Check for desktop environment
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        workstation_indicators.append("display_environment")

    # Check for single user
    if user_count == 1:
        workstation_indicators.append("single_user")
    elif user_count == -1:
        workstation_indicators.append("user_count_unknown")

    # Check for typical workstation paths
    home = os.path.expanduser("~")
    if os.path.exists(os.path.join(home, "Desktop")) or os.path.exists(os.path.join(home, ".config")):
        workstation_indicators.append("workstation_paths")

    vlog(f"Workstation environment detected (default): {workstation_indicators}", verbose)
    return Environment(
        mode="workstation",
        confidence=0.75,  # Medium confidence for default fallback
        indicators=tuple(workstation_indicators),
    )


def get_environment_from_config(config_mode: str | None, verbose: bool = False) -> Environment:
    """
    Get environment from configuration file setting.

    Args:
        config_mode: Mode from config file ('auto', 'ci', 'server', 'workstation', or None)
        verbose: Enable verbose logging

    Returns:
        Environment object (auto triggers detection, others are explicit)
    """
    if not config_mode or config_mode == "auto":
        return detect_environment(override=None, verbose=verbose)
    else:
        return detect_environment(override=config_mode, verbose=verbose)
