"""
Breaking change detection and user confirmation handling.

Provides functionality for detecting major version upgrades, policy enforcement,
and interactive confirmation workflows.
"""

from __future__ import annotations

import sys
from typing import Sequence

from .config import Config


def is_major_upgrade(v1: str, v2: str) -> bool:
    """
    Check if upgrade from v1 to v2 is a major version bump.

    Args:
        v1: Current version
        v2: Target version

    Returns:
        True if v2 is a major version ahead of v1
    """
    try:
        from packaging import version
        ver1 = version.parse(v1)
        ver2 = version.parse(v2)

        # For PEP 440 versions with major attribute
        if hasattr(ver1, 'major') and hasattr(ver2, 'major'):
            return ver2.major > ver1.major

        # Fallback: parse major from string
        parts1 = str(ver1.base_version if hasattr(ver1, 'base_version') else ver1).split('.')
        parts2 = str(ver2.base_version if hasattr(ver2, 'base_version') else ver2).split('.')

        if parts1 and parts2:
            major1 = int(parts1[0]) if parts1[0].isdigit() else 0
            major2 = int(parts2[0]) if parts2[0].isdigit() else 0
            return major2 > major1

        return False
    except Exception:
        # Conservative: treat as non-breaking if can't determine
        return False


def check_breaking_change_policy(
    config: Config,
    current_version: str,
    target_version: str,
) -> tuple[bool, str]:
    """
    Check if upgrade is allowed under breaking change policy.

    Args:
        config: Configuration object
        current_version: Current version
        target_version: Target version

    Returns:
        (allowed, reason)
    """
    policy = config.preferences.breaking_changes

    if not is_major_upgrade(current_version, target_version):
        return (True, "not_breaking")

    # Major version upgrade detected
    if policy == "accept":
        return (True, "breaking_accepted")
    elif policy == "warn":
        return (True, "breaking_warning")
    elif policy == "reject":
        return (False, "breaking_rejected")

    return (True, "breaking_default")


def format_breaking_change_warning(
    tool_name: str,
    current_version: str,
    target_version: str,
) -> str:
    """Format breaking change warning message."""
    return f"""
⚠️  BREAKING CHANGE WARNING

Tool:     {tool_name}
Current:  {current_version}
Target:   {target_version}

This is a MAJOR version upgrade and may include breaking changes:
  • API changes that break existing scripts/workflows
  • Command-line argument changes
  • Configuration file format changes
  • Behavior changes that affect automation

Recommendations:
  1. Review release notes before proceeding
  2. Test in isolated environment first
  3. Ensure backups are created

Continue with upgrade? [y/N]: """


def confirm_breaking_change(warning_message: str) -> bool:
    """
    Prompt user to confirm breaking change upgrade.

    Args:
        warning_message: Warning message to display

    Returns:
        True if user confirms, False otherwise
    """
    if not sys.stdin.isatty():
        # Non-interactive (CI/CD)
        return False

    print(warning_message, end="")
    response = input().strip().lower()
    return response in ('y', 'yes')


def confirm_bulk_breaking_changes(candidates: Sequence) -> bool:
    """
    Confirm bulk upgrade with breaking changes.

    Args:
        candidates: Upgrade candidates with breaking_change attribute

    Returns:
        True if user confirms, False otherwise
    """
    breaking = [c for c in candidates if c.breaking_change]

    if not breaking:
        return True

    if not sys.stdin.isatty():
        return False

    print(f"\n⚠️  {len(breaking)} tool(s) have BREAKING CHANGES:\n")
    for candidate in breaking:
        # Assumes candidate has tool_name and version_jump_description() method
        print(f"  • {candidate.tool_name}: {candidate.version_jump_description()}")

    print("\nReview release notes before proceeding.")
    print("Continue with upgrades? [y/N]: ", end="")

    response = input().strip().lower()
    return response in ('y', 'yes')


def filter_by_breaking_changes(
    candidates: Sequence,
    policy: str,
) -> tuple[list, list]:
    """
    Split candidates into allowed and blocked based on breaking change policy.

    Args:
        candidates: Upgrade candidates with breaking_change attribute
        policy: Breaking change policy ("accept", "warn", "reject")

    Returns:
        (allowed_candidates, blocked_candidates)
    """
    if policy == "accept":
        return (list(candidates), [])
    elif policy == "reject":
        allowed = [c for c in candidates if not c.breaking_change]
        blocked = [c for c in candidates if c.breaking_change]
        return (allowed, blocked)
    elif policy == "warn":
        # All allowed but will prompt for breaking changes
        return (list(candidates), [])

    return (list(candidates), [])
