"""
Version collection from upstream sources.

This module provides functions to collect latest version information from various
package repositories and version control systems.

Phase 2.0: Detection and Auditing - Version Collection
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class CollectionError(Exception):
    """Raised when version collection fails."""
    pass


class NetworkError(CollectionError):
    """Raised when network requests fail."""
    pass


class ParseError(CollectionError):
    """Raised when response parsing fails."""
    pass


def normalize_version_tag(tag: str) -> str:
    """Normalize a version tag by removing common prefixes.

    Args:
        tag: Raw version tag (e.g., "v1.2.3", "release-1.2.3", "3_4_7")

    Returns:
        Normalized tag (e.g., "1.2.3", "3.4.7")
    """
    tag = tag.strip()
    # Remove common prefixes
    for prefix in ("release-", "version-", "ver-", "go", "v"):
        if tag.lower().startswith(prefix):
            tag = tag[len(prefix):]
    # Replace underscores with periods in version numbers (e.g., ruby "3_4_7" -> "3.4.7")
    tag = tag.replace("_", ".")
    return tag


def extract_version_number(s: str) -> str:
    """Extract version number from a string.

    Args:
        s: String potentially containing version (e.g., "v1.2.3", "tool-1.2.3", "20251023")

    Returns:
        Version number (e.g., "1.2.3", "20251023") or empty string if not found
    """
    s = normalize_version_tag(s)
    # Match version patterns: 1.2.3, 1.2, 1.2.3.4, 20251023 (date-based)
    match = re.search(r"\d+(?:\.\d+)*", s)
    return match.group(0) if match else ""


def http_get(url: str, timeout: int = 3, headers: dict[str, str] | None = None) -> bytes:
    """Perform HTTP GET request.

    Args:
        url: URL to fetch
        timeout: Timeout in seconds
        headers: Optional HTTP headers

    Returns:
        Response body as bytes

    Raises:
        NetworkError: If request fails
    """
    try:
        default_headers = {"User-Agent": "ai-cli-preparation/2.0"}
        if headers:
            default_headers.update(headers)

        req = urllib.request.Request(url, headers=default_headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()  # type: ignore[no-any-return]
    except Exception as e:
        raise NetworkError(f"Failed to fetch {url}: {e}") from e


def collect_github(owner: str, repo: str, offline_cache: dict[str, tuple[str, str]] | None = None) -> tuple[str, str]:
    """Collect latest version from GitHub repository.

    Args:
        owner: Repository owner
        repo: Repository name
        offline_cache: Optional offline cache for fallback

    Returns:
        Tuple of (tag, version_number) or ("", "") if not found
    """
    # Try latest redirect first (skips pre-releases)
    try:
        url = f"https://github.com/{owner}/{repo}/releases/latest"
        logger.debug(f"Checking GitHub latest redirect: {url}")

        req = urllib.request.Request(url, headers={"User-Agent": "ai-cli-preparation/2.0"}, method="HEAD")
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)

        with opener.open(req, timeout=3) as resp:
            final_url = resp.geturl()
            last_segment = final_url.rsplit("/", 1)[-1]

            if last_segment and last_segment.lower() not in ("releases", "latest"):
                tag = normalize_version_tag(last_segment)
                version = extract_version_number(tag)
                logger.debug(f"GitHub {owner}/{repo}: {tag} via redirect")
                return tag, version
    except Exception as e:
        logger.debug(f"GitHub redirect failed for {owner}/{repo}: {e}")

    # Fallback to releases API
    try:
        data = json.loads(http_get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest", timeout=3))
        tag = normalize_version_tag(data.get("tag_name", ""))

        if tag:
            version = extract_version_number(tag)
            logger.debug(f"GitHub {owner}/{repo}: {tag} via API")
            return tag, version
    except Exception as e:
        logger.debug(f"GitHub API failed for {owner}/{repo}: {e}")

    # Fallback to Atom feed (filters pre-releases automatically)
    try:
        atom_url = f"https://github.com/{owner}/{repo}/releases.atom"
        atom = http_get(atom_url, timeout=3).decode("utf-8", "ignore")

        # Extract all tags from Atom feed
        best = None
        for match in re.finditer(r"/releases/tag/([^<\"]+)", atom):
            raw_tag = match.group(1).strip()
            tag = normalize_version_tag(raw_tag)

            # Accept only stable versions: v3.14.0, v28.5.1 (exclude -rc, -alpha, -beta, etc.)
            # This filters out pre-releases automatically
            if tag and re.match(r"^v?\d+\.\d+(\.\d+)?$", tag):
                ver = extract_version_number(tag)
                if ver:
                    # Parse version as tuple for comparison
                    try:
                        nums = tuple(int(x) for x in ver.split("."))
                        tup = (nums, tag, ver)
                        if best is None or tup[0] > best[0]:
                            best = tup
                    except (ValueError, AttributeError):
                        continue

        if best is not None:
            _, tag, version = best
            logger.debug(f"GitHub {owner}/{repo}: {tag} via Atom feed (filtered stable)")
            return tag, version
    except Exception as e:
        logger.debug(f"GitHub Atom feed failed for {owner}/{repo}: {e}")

    # Use offline cache if available
    if offline_cache:
        key = f"gh:{owner}/{repo}"
        if key in offline_cache:
            logger.debug(f"GitHub {owner}/{repo}: Using offline cache")
            return offline_cache[key]

    logger.warning(f"GitHub {owner}/{repo}: No version found")
    return "", ""


def collect_gitlab(group: str, project: str, offline_cache: dict[str, tuple[str, str]] | None = None) -> tuple[str, str]:
    """Collect latest version from GitLab repository.

    Args:
        group: GitLab group/namespace
        project: Project name
        offline_cache: Optional offline cache for fallback

    Returns:
        Tuple of (tag, version_number) or ("", "") if not found
    """
    project_path = f"{group}%2F{project}"

    # Try releases API
    try:
        url = f"https://gitlab.com/api/v4/projects/{project_path}/releases"
        data = json.loads(http_get(url))

        if isinstance(data, list) and data:
            tag = normalize_version_tag(data[0].get("tag_name", ""))
            if tag:
                version = extract_version_number(tag)
                logger.debug(f"GitLab {group}/{project}: {tag}")
                return tag, version
    except Exception as e:
        logger.debug(f"GitLab API failed for {group}/{project}: {e}")

    # Use offline cache if available
    if offline_cache:
        key = f"gitlab:{group}/{project}"
        if key in offline_cache:
            logger.debug(f"GitLab {group}/{project}: Using offline cache")
            return offline_cache[key]

    logger.warning(f"GitLab {group}/{project}: No version found")
    return "", ""


def collect_pypi(package: str, offline_cache: dict[str, tuple[str, str]] | None = None) -> tuple[str, str]:
    """Collect latest version from PyPI.

    Args:
        package: Package name
        offline_cache: Optional offline cache for fallback

    Returns:
        Tuple of (version, version_number) or ("", "") if not found
    """
    try:
        data = json.loads(http_get(f"https://pypi.org/pypi/{package}/json"))
        version = data.get("info", {}).get("version", "")

        if version:
            version_num = extract_version_number(version)
            logger.debug(f"PyPI {package}: {version}")
            return version, version_num
    except Exception as e:
        logger.debug(f"PyPI failed for {package}: {e}")

    # Use offline cache if available
    if offline_cache and package in offline_cache:
        logger.debug(f"PyPI {package}: Using offline cache")
        return offline_cache[package]

    logger.warning(f"PyPI {package}: No version found")
    return "", ""


def collect_npm(package: str, offline_cache: dict[str, tuple[str, str]] | None = None) -> tuple[str, str]:
    """Collect latest version from npm registry.

    Args:
        package: Package name
        offline_cache: Optional offline cache for fallback

    Returns:
        Tuple of (version, version_number) or ("", "") if not found
    """
    try:
        data = json.loads(http_get(f"https://registry.npmjs.org/{package}"))
        dist_tags = data.get("dist-tags", {})
        version = dist_tags.get("latest", "")

        if version:
            version_num = extract_version_number(version)
            logger.debug(f"npm {package}: {version}")
            return version, version_num
    except Exception as e:
        logger.debug(f"npm failed for {package}: {e}")

    # Use offline cache if available
    if offline_cache and package in offline_cache:
        logger.debug(f"npm {package}: Using offline cache")
        return offline_cache[package]

    logger.warning(f"npm {package}: No version found")
    return "", ""


def collect_crates(crate: str, offline_cache: dict[str, tuple[str, str]] | None = None) -> tuple[str, str]:
    """Collect latest version from crates.io.

    Args:
        crate: Crate name
        offline_cache: Optional offline cache for fallback

    Returns:
        Tuple of (version, version_number) or ("", "") if not found
    """
    try:
        data = json.loads(http_get(f"https://crates.io/api/v1/crates/{crate}"))
        version = data.get("crate", {}).get("max_version", "")

        if version:
            version_num = extract_version_number(version)
            logger.debug(f"crates.io {crate}: {version}")
            return version, version_num
    except Exception as e:
        logger.debug(f"crates.io failed for {crate}: {e}")

    # Use offline cache if available
    if offline_cache and crate in offline_cache:
        logger.debug(f"crates.io {crate}: Using offline cache")
        return offline_cache[crate]

    logger.warning(f"crates.io {crate}: No version found")
    return "", ""


def collect_gnu(tool_name: str, ftp_url: str, offline_cache: dict[str, tuple[str, str]] | None = None) -> tuple[str, str]:
    """Collect latest version from GNU FTP mirror.

    Args:
        tool_name: Tool name
        ftp_url: GNU FTP URL (e.g., "https://ftp.gnu.org/gnu/parallel/")
        offline_cache: Optional offline cache for fallback

    Returns:
        Tuple of (version, version_number) or ("", "") if not found
    """
    try:
        # Fetch FTP directory listing
        response = http_get(ftp_url, timeout=5).decode("utf-8", errors="ignore")

        # Extract tarball filenames matching: tool-YYYYMMDD.tar.* or tool-X.Y.Z.tar.*
        # Example patterns:
        #   parallel-20251022.tar.gz
        #   make-4.4.1.tar.gz
        pattern = re.compile(rf'{re.escape(tool_name)}-(\d{{8}}|\d+(?:\.\d+)+)\.tar\.')
        versions = []

        for match in pattern.finditer(response):
            version = match.group(1)
            versions.append(version)

        if not versions:
            logger.debug(f"GNU FTP {tool_name}: No versions found in {ftp_url}")
            # Try offline cache
            if offline_cache and tool_name in offline_cache:
                logger.debug(f"GNU FTP {tool_name}: Using offline cache")
                return offline_cache[tool_name]
            return "", ""

        # Sort versions
        # For date-based versions (8 digits): sort as integers
        # For semver versions: sort using version comparison
        if all(len(v) == 8 and v.isdigit() for v in versions):
            # Date-based versions (YYYYMMDD)
            latest = max(versions, key=lambda v: int(v))
        else:
            # Semantic versions - sort by version components
            def version_key(v: str) -> tuple:
                try:
                    return tuple(int(x) for x in v.split('.'))
                except ValueError:
                    return (0,)

            latest = max(versions, key=version_key)

        version_num = extract_version_number(latest) if not latest.isdigit() else latest
        logger.debug(f"GNU FTP {tool_name}: {latest}")
        return latest, version_num

    except Exception as e:
        logger.debug(f"GNU FTP failed for {tool_name}: {e}")

    # Use offline cache if available
    if offline_cache and tool_name in offline_cache:
        logger.debug(f"GNU FTP {tool_name}: Using offline cache")
        return offline_cache[tool_name]

    logger.warning(f"GNU FTP {tool_name}: No version found")
    return "", ""


def get_gh_cli_token() -> str | None:
    """Try to get GitHub token from gh CLI if authenticated.

    Returns:
        Token string or None if gh CLI is not available/authenticated
    """
    import shutil
    import subprocess

    if not shutil.which("gh"):
        return None

    try:
        # Check if gh is authenticated
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        # Get the token
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    return None


def get_github_rate_limit() -> dict[str, Any]:
    """Get GitHub API rate limit status.

    Returns:
        Dictionary with rate limit info or empty dict on failure
    """
    import os

    try:
        headers = {"User-Agent": "ai-cli-preparation/2.0"}

        # Try to get token from multiple sources
        token = os.environ.get("GITHUB_TOKEN")
        token_source = "GITHUB_TOKEN" if token else None

        # Try gh CLI if no token in environment
        if not token:
            token = get_gh_cli_token()
            if token:
                token_source = "gh_cli"

        if token:
            headers["Authorization"] = f"token {token}"

        data = json.loads(http_get("https://api.github.com/rate_limit", headers=headers))
        core = data.get("resources", {}).get("core", {})

        return {
            "limit": core.get("limit", 0),
            "remaining": core.get("remaining", 0),
            "used": core.get("used", 0),
            "reset": core.get("reset", 0),
            "authenticated": token is not None,
            "token_source": token_source,
        }
    except Exception as e:
        logger.debug(f"Failed to get GitHub rate limit: {e}")
        return {}


def get_github_rate_limit_help() -> str:
    """Get helpful instructions for setting up GitHub authentication.

    Returns:
        Multiline string with instructions
    """
    import shutil

    lines = []

    # Check if gh CLI is available
    has_gh = shutil.which("gh") is not None

    lines.append("")
    lines.append("To increase GitHub API rate limit from 60 to 5,000 requests/hour:")
    lines.append("")

    if has_gh:
        lines.append("Option 1 (Recommended): Use GitHub CLI (already installed)")
        lines.append("  gh auth login")
        lines.append("")
        lines.append("Option 2: Set GITHUB_TOKEN environment variable")
    else:
        lines.append("Option 1 (Recommended): Install and authenticate GitHub CLI")
        lines.append("  # Install: https://cli.github.com/")
        lines.append("  gh auth login")
        lines.append("")
        lines.append("Option 2: Set GITHUB_TOKEN environment variable")

    # Deep link to create PAT with minimal required scopes
    # The 'public_repo' scope is needed for accessing public repository data
    pat_url = "https://github.com/settings/tokens/new?description=CLI%20Toolset&scopes=public_repo"
    lines.append(f"  1. Create a PAT: {pat_url}")
    lines.append("  2. Add to your shell profile:")
    lines.append("     export GITHUB_TOKEN='ghp_your_token_here'")

    return "\n".join(lines)
