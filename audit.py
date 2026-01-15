#!/usr/bin/env python3
"""
AI CLI Preparation - Tool audit and version management.

Modular architecture for CLI tool management with parallel collection,
snapshot-based caching, and intelligent version detection.

Usage:
    audit.py              # Render audit from snapshot
    audit.py --update     # Collect fresh versions
    audit.py --install    # Install missing tools
    audit.py --upgrade    # Upgrade outdated tools
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import modules
from cli_audit.tools import Tool, all_tools, filter_tools, tool_homepage_url, latest_target_url  # noqa: E402
from cli_audit.detection import audit_tool_installation  # noqa: E402
from cli_audit.snapshot import load_snapshot, write_snapshot, render_from_snapshot, get_snapshot_path  # noqa: E402
from cli_audit.render import render_table, print_summary, status_icon  # noqa: E402
from cli_audit.collectors import get_github_rate_limit, get_github_rate_limit_help, get_gitlab_rate_limit, is_wsl  # noqa: E402
from cli_audit import collectors  # noqa: E402
from cli_audit.logging_config import setup_logging  # noqa: E402
# Split file support (Phase 2.1)
from cli_audit.upstream_cache import (  # noqa: E402
    UpstreamVersion, UpstreamCache,
    load_upstream_cache, write_upstream_cache, get_upstream_cache_path,
    update_cached_upstream,
)
from cli_audit.local_state import (  # noqa: E402
    LocalInstallation, LocalState,
    load_local_state, write_local_state, get_local_state_path,
    update_local_installation, merge_for_display, build_legacy_snapshot,
)

# Configuration from environment
OFFLINE_MODE = os.environ.get("CLI_AUDIT_OFFLINE", "0") == "1"
MAX_WORKERS = int(os.environ.get("CLI_AUDIT_MAX_WORKERS", "16"))
SHOW_HINTS = os.environ.get("CLI_AUDIT_HINTS", "1") == "1"
COLLECT_MODE = os.environ.get("CLI_AUDIT_COLLECT", "0") == "1"
RENDER_MODE = os.environ.get("CLI_AUDIT_RENDER", "0") == "1"
JSON_MODE = os.environ.get("CLI_AUDIT_JSON", "0") == "1"
FILTER_STATUS = os.environ.get("CLI_AUDIT_FILTER_STATUS", "")  # e.g., "NOT INSTALLED,OUTDATED"
# Split file modes (Phase 2.1)
UPDATE_LOCAL_ONLY = os.environ.get("CLI_AUDIT_UPDATE_LOCAL", "0") == "1"
UPDATE_BASELINE_ONLY = os.environ.get("CLI_AUDIT_UPDATE_BASELINE", "0") == "1"
USE_SPLIT_FILES = os.environ.get("CLI_AUDIT_SPLIT_FILES", "0") == "1"


def normalize_version(version: str) -> str:
    """Normalize version string for comparison.

    Args:
        version: Version string (e.g., "7.28.00", "v1.2.0")

    Returns:
        Normalized version string (e.g., "7.28.0", "1.2.0")
    """
    if not version:
        return version

    # Remove 'v' prefix
    version = version.lstrip('v')

    # Split into parts and remove trailing zeros from each part
    parts = version.split('.')
    normalized_parts = []

    for i, part in enumerate(parts):
        # For numeric parts, strip trailing zeros but keep at least one digit
        if part.isdigit():
            # Keep at least one zero if the part is all zeros
            normalized = part.lstrip('0') or '0'
            normalized_parts.append(normalized)
        else:
            # Non-numeric parts (e.g., "rc1", "beta") - keep as is
            normalized_parts.append(part)

    return '.'.join(normalized_parts)


def collect_latest_version(tool: Tool, offline_cache: dict[str, tuple[str, str]] | None = None) -> tuple[str, str]:
    """Collect latest version for a tool.

    Args:
        tool: Tool definition
        offline_cache: Optional offline cache for fallback

    Returns:
        Tuple of (tag, version_number)
    """
    if tool.source_kind == "skip":
        return ("", "")

    try:
        if tool.source_kind == "gh" and len(tool.source_args) >= 2:
            owner, repo = tool.source_args[0], tool.source_args[1]
            return collectors.collect_github(owner, repo, offline_cache)
        elif tool.source_kind == "gitlab" and len(tool.source_args) >= 2:
            group, project = tool.source_args[0], tool.source_args[1]
            return collectors.collect_gitlab(group, project, offline_cache)
        elif tool.source_kind == "pypi" and tool.source_args:
            package = tool.source_args[0]
            return collectors.collect_pypi(package, offline_cache)
        elif tool.source_kind == "npm" and tool.source_args:
            package = tool.source_args[0]
            return collectors.collect_npm(package, offline_cache)
        elif tool.source_kind == "crates" and tool.source_args:
            crate = tool.source_args[0]
            return collectors.collect_crates(crate, offline_cache)
        elif tool.source_kind == "gnu" and len(tool.source_args) >= 2:
            tool_name, ftp_url = tool.source_args[0], tool.source_args[1]
            return collectors.collect_gnu(tool_name, ftp_url, offline_cache)
        else:
            return ("", "")
    except Exception as e:
        if os.environ.get("CLI_AUDIT_DEBUG"):
            print(f"# DEBUG: Collection failed for {tool.name}: {e}", file=sys.stderr)
        return ("", "")


def audit_tool(tool: Tool, offline_cache: dict[str, tuple[str, str]] | None = None) -> dict[str, str]:
    """Audit a single tool.

    Args:
        tool: Tool definition
        offline_cache: Optional offline cache for latest versions

    Returns:
        Dictionary with audit results
    """
    # Load catalog metadata for version detection
    from cli_audit.catalog import ToolCatalog
    catalog = ToolCatalog()
    version_flag = None
    version_command = None
    if catalog.has_tool(tool.name):
        catalog_data = catalog.get_raw_data(tool.name)
        version_flag = catalog_data.get("version_flag")
        version_command = catalog_data.get("version_command")

    # Detect installed version
    deep_scan = tool.name in {"node", "python", "semgrep", "pre-commit", "bandit", "black", "flake8", "isort"}
    version_num, version_line, path, install_method = audit_tool_installation(
        tool.name, tool.candidates, deep=deep_scan, version_flag=version_flag, version_command=version_command
    )

    installed = version_num if version_num else (version_line if version_line != "X" else "")

    # Collect latest version
    latest_tag, latest_num = collect_latest_version(tool, offline_cache)
    latest = latest_num if latest_num else latest_tag

    # Determine status
    if version_line and version_line.startswith("CONFLICT:"):
        status = "CONFLICT"
    elif version_line == "X" or not installed:
        status = "NOT INSTALLED"
    elif version_num and latest_num:
        # Normalize versions for comparison (handles "7.28.00" vs "7.28.0")
        normalized_installed = normalize_version(version_num)
        normalized_latest = normalize_version(latest_num)
        status = "UP-TO-DATE" if normalized_installed == normalized_latest else "OUTDATED"
    elif version_num and not latest_num:
        status = "UNKNOWN"
    else:
        status = "UNKNOWN"

    # URLs
    tool_url = tool_homepage_url(tool)
    latest_url = latest_target_url(tool, latest_tag, latest_num)

    # Generate classification reason
    if install_method:
        classification_reason = f"Detected via path analysis: {install_method}"
    else:
        classification_reason = "No installation detected"

    return {
        "tool": tool.name,
        "category": tool.category,
        "installed": installed,
        "installed_method": install_method,
        "installed_version": version_num,
        "installed_path_selected": path,
        "classification_reason_selected": classification_reason,
        "latest_upstream": latest,
        "latest_version": latest_num,
        "upstream_method": tool.source_kind,
        "status": status,
        "tool_url": tool_url,
        "latest_url": latest_url,
        "hint": tool.hint if status in ("NOT INSTALLED", "OUTDATED", "CONFLICT") else "",
    }


def cmd_audit(args: argparse.Namespace) -> int:
    """Render audit from snapshot (fast, no network)."""
    # If COLLECT_MODE is enabled with specific tools, do fresh collection
    if COLLECT_MODE and args.tools:
        # Fresh collection for specific tools
        tools_list = filter_tools(args.tools)

        if not JSON_MODE:
            print(f"# Collecting fresh data for {len(tools_list)} tool(s)...", file=sys.stderr)

        # Collect in parallel
        results = []
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(tools_list))) as executor:
            future_to_tool = {executor.submit(audit_tool, tool, None): tool for tool in tools_list}
            for future in as_completed(future_to_tool):
                try:
                    result = future.result()
                    results.append(result)
                except Exception:
                    pass

        tools = results

        # If there's an existing snapshot and we're in merge mode, update it
        if os.environ.get("CLI_AUDIT_MERGE", "0") == "1":
            snapshot = load_snapshot()
            if snapshot.get("tools"):
                # Merge results into existing snapshot
                tool_names = {t.get("tool") for t in results}
                existing_tools = [t for t in snapshot.get("tools", []) if t.get("tool") not in tool_names]
                merged_tools = existing_tools + results

                # Write merged snapshot
                write_snapshot(merged_tools, offline=OFFLINE_MODE)

                if not JSON_MODE:
                    print(f"# Updated snapshot with {len(results)} tool(s)", file=sys.stderr)
    else:
        # Load snapshot
        snapshot = load_snapshot()
        if not snapshot.get("tools"):
            if not JSON_MODE:
                print("# No snapshot found - run 'make update' first", file=sys.stderr)
            return 1

        # Filter tools if specified
        selected = set(args.tools) if args.tools else None
        tools = render_from_snapshot(snapshot, selected)

    # Apply status filter if specified
    if FILTER_STATUS:
        allowed_statuses = {s.strip().upper() for s in FILTER_STATUS.split(",")}
        tools = [t for t in tools if t.get("status", "").upper() in allowed_statuses]

    # JSON output mode
    if JSON_MODE:
        # Enrich tools with additional fields for guide.sh compatibility
        enriched_tools = []
        for tool in tools:
            enriched = tool.copy()
            status = tool.get("status", "UNKNOWN")
            installed = tool.get("installed", "")
            install_method = tool.get("installed_method", "")

            # Add state_icon field
            enriched["state_icon"] = status_icon(status, installed)

            # Add is_up_to_date boolean field
            enriched["is_up_to_date"] = (status == "UP-TO-DATE")  # type: ignore[assignment]

            # Add path and classification fields (for backward compatibility with old snapshots)
            if "installed_path_selected" not in enriched:
                enriched["installed_path_selected"] = ""
            if "classification_reason_selected" not in enriched:
                if install_method:
                    enriched["classification_reason_selected"] = f"Detected via path analysis: {install_method}"
                else:
                    enriched["classification_reason_selected"] = "No installation detected"

            enriched_tools.append(enriched)

        # Output JSON array to stdout
        print(json.dumps(enriched_tools, indent=2, ensure_ascii=False))
        return 0

    # Table output mode
    print("=" * 80, file=sys.stderr)
    print("Audit Mode", file=sys.stderr)
    print("=" * 80, file=sys.stderr)

    # Get metadata for friendly message
    meta = snapshot.get("__meta__", {})
    count = meta.get("count", len(tools))
    created_at = meta.get("created_at", "cached")

    # Calculate age
    if created_at and created_at != "cached":
        try:
            from datetime import datetime
            created_dt = datetime.fromisoformat(created_at)
            now = datetime.now(created_dt.tzinfo)
            age_seconds = (now - created_dt).total_seconds()
            if age_seconds < 60:
                age_str = "just now"
            elif age_seconds < 3600:
                age_str = f"{int(age_seconds / 60)}m ago"
            elif age_seconds < 86400:
                age_str = f"{int(age_seconds / 3600)}h ago"
            else:
                age_str = f"{int(age_seconds / 86400)}d ago"
        except Exception:
            age_str = "cached"
    else:
        age_str = "cached"

    print(f"# Auditing {count} development tools from snapshot ({age_str})...", file=sys.stderr)
    print("", file=sys.stderr)

    # Render table
    render_table(tools, show_hints=SHOW_HINTS)

    # Print summary
    print_summary(snapshot, tools)

    # Suggest package manager upgrades
    from cli_audit.catalog import suggest_package_manager_upgrades
    suggest_package_manager_upgrades()

    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Collect fresh version data from upstream."""
    # Reset terminal state at start (in case previous run left corruption)
    print("\033[0m", end="", file=sys.stderr, flush=True)

    print("=" * 80, file=sys.stderr)
    print("Update Mode", file=sys.stderr)
    print("=" * 80, file=sys.stderr)

    # Show platform info
    if is_wsl():
        print("ℹ️  Platform: WSL (Windows Subsystem for Linux)", file=sys.stderr)

    # Get tools to audit
    tools_list = filter_tools(args.tools) if args.tools else all_tools()
    total = len(tools_list)

    # Show GitHub rate limit before starting
    rate_limit = get_github_rate_limit()
    if rate_limit:
        remaining = rate_limit.get("remaining", 0)
        limit = rate_limit.get("limit", 0)
        authenticated = rate_limit.get("authenticated", False)
        token_source = rate_limit.get("token_source", "")

        # Build status message
        auth_info = ""
        if authenticated:
            if token_source == "gh_cli":
                auth_info = " (via gh CLI)"
            elif token_source == "GITHUB_TOKEN":
                auth_info = " (via GITHUB_TOKEN)"

        if remaining < limit * 0.2:  # Warn if less than 20% remaining
            print(f"⚠️  GitHub rate limit: {remaining}/{limit} remaining{auth_info}", file=sys.stderr)
            if not authenticated:
                print(get_github_rate_limit_help(), file=sys.stderr)
        elif not authenticated and limit == 60:
            # Unauthenticated with default limit - suggest authentication
            print(f"ℹ️  GitHub rate limit: {remaining}/{limit} remaining (unauthenticated)", file=sys.stderr)
            print(get_github_rate_limit_help(), file=sys.stderr)
        else:
            print(f"✓ GitHub rate limit: {remaining}/{limit} remaining{auth_info}", file=sys.stderr)

    # Show GitLab rate limit if we have GitLab tools
    gitlab_rate = get_gitlab_rate_limit()
    if gitlab_rate:
        gl_remaining = gitlab_rate.get("remaining", 0)
        gl_limit = gitlab_rate.get("limit", 0)
        gl_authenticated = gitlab_rate.get("authenticated", False)
        gl_token_source = gitlab_rate.get("token_source", "")
        gl_host = gitlab_rate.get("host", "gitlab.com")

        gl_auth_info = ""
        if gl_authenticated:
            if gl_token_source == "glab_cli":
                gl_auth_info = " (via glab CLI)"
            else:
                gl_auth_info = " (via GITLAB_TOKEN)"

        if gl_remaining < gl_limit * 0.2:
            print(f"⚠️  GitLab rate limit ({gl_host}): {gl_remaining}/{gl_limit} remaining{gl_auth_info}", file=sys.stderr)
        else:
            print(f"✓ GitLab rate limit ({gl_host}): {gl_remaining}/{gl_limit} remaining{gl_auth_info}", file=sys.stderr)

    print(f"# Collecting fresh data for {total} tools...", file=sys.stderr)
    est_time = int((total / MAX_WORKERS) * 3 * 1.5)
    print(f"# Estimated time: ~{est_time}s (timeout=3s per tool, {MAX_WORKERS} workers)", file=sys.stderr)
    print("", file=sys.stderr)

    # Group tools by category for organized output
    from cli_audit.render import CATEGORY_ORDER, CATEGORY_ICON, CATEGORY_DESC
    categorized: dict[str, list] = {}
    for tool in tools_list:
        cat = tool.category or "general"
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(tool)
    sorted_cats = sorted(categorized.keys(), key=lambda c: CATEGORY_ORDER.get(c, 99))

    # Parallel audit with progress tracking, grouped by category
    results = []
    completed = 0

    try:
        for category in sorted_cats:
            cat_tools = categorized[category]
            icon = CATEGORY_ICON.get(category, "📦")
            desc = CATEGORY_DESC.get(category, category)
            print(f"\n# {icon} {desc} ({len(cat_tools)} tools)", file=sys.stderr)

            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(cat_tools))) as executor:
                future_to_tool = {executor.submit(audit_tool, tool, None): tool for tool in cat_tools}

                for future in as_completed(future_to_tool):
                    tool = future_to_tool[future]
                    try:
                        result = future.result()
                        results.append(result)
                        completed += 1

                        # Progress
                        inst = result.get("installed", "")
                        latest = result.get("latest_upstream", "")
                        status = result.get("status", "")

                        # ANSI colors for all platforms
                        GREEN = "\033[32m"
                        BOLD_GREEN = "\033[1;32m"
                        YELLOW = "\033[33m"
                        BLUE = "\033[34m"
                        RESET = "\033[0m"

                        # Color the installed version based on status
                        if status == "UP-TO-DATE":
                            inst_color = GREEN
                            latest_color = GREEN
                            op = "==="
                        elif status == "OUTDATED":
                            inst_color = YELLOW
                            latest_color = BOLD_GREEN  # Latest is newer, make it bold green
                            op = "!=="
                        elif status == "CONFLICT":
                            inst_color = YELLOW
                            latest_color = BOLD_GREEN
                            op = "⚠️"
                        else:  # NOT INSTALLED, UNKNOWN
                            inst_color = BLUE  # Blue for not-installed
                            latest_color = BLUE
                            op = "?"

                        inst_display = inst if inst else "n/a"
                        latest_display = latest if latest else "n/a"

                        # Add pinned/skip markers
                        from cli_audit.catalog import ToolCatalog
                        catalog = ToolCatalog()
                        markers = []
                        if catalog.is_pinned(tool.name):
                            markers.append("PINNED")
                        if catalog.should_skip(tool.name, latest):
                            markers.append("SKIP")

                        marker_str = f" [{' '.join(markers)}]" if markers else ""
                        inst_fmt = f"{inst_color}{inst_display}{RESET}"
                        latest_fmt = f"{latest_color}{latest_display}{RESET}"
                        msg = f"# [{completed}/{total}] {tool.name} (installed: {inst_fmt} {op} latest: {latest_fmt}){marker_str}"

                        print(msg, file=sys.stderr, flush=True)

                    except Exception as e:
                        completed += 1
                        print(f"# [{completed}/{total}] {tool.name} (failed: {e})", file=sys.stderr, flush=True)

                        # Add failure entry
                        results.append({
                            "tool": tool.name,
                            "category": tool.category,
                            "installed": "",
                            "installed_method": "",
                            "installed_version": "",
                            "installed_path_selected": "",
                            "classification_reason_selected": "Detection failed",
                            "latest_upstream": "",
                            "latest_version": "",
                            "upstream_method": tool.source_kind,
                            "status": "UNKNOWN",
                            "tool_url": tool_homepage_url(tool),
                            "latest_url": "",
                            "hint": "",
                        })
    except KeyboardInterrupt:
        # Shutdown executor immediately without waiting for threads
        executor.shutdown(wait=False, cancel_futures=True)
        print("\n\n✗ Interrupted", file=sys.stderr)
        # Reset terminal state before exiting
        print("\033[0m", end="", file=sys.stderr, flush=True)
        sys.stderr.flush()
        # Exit immediately to avoid shutdown deadlocks
        import os
        os._exit(130)

    # Write snapshot
    try:
        meta = write_snapshot(results, offline=OFFLINE_MODE)
        print("", file=sys.stderr)
        print(f"✓ Snapshot updated: {get_snapshot_path()}", file=sys.stderr)
        print(f"✓ Collected {meta['count']} tools", file=sys.stderr)

        # Report GitHub rate limit status
        rate_limit = get_github_rate_limit()
        if rate_limit:
            remaining = rate_limit.get("remaining", 0)
            limit = rate_limit.get("limit", 0)
            authenticated = rate_limit.get("authenticated", False)
            token_source = rate_limit.get("token_source", "")

            auth_info = ""
            if authenticated:
                if token_source == "gh_cli":
                    auth_info = " (via gh CLI)"
                elif token_source == "GITHUB_TOKEN":
                    auth_info = " (via GITHUB_TOKEN)"

            if remaining < limit * 0.2:
                print(f"⚠️  GitHub rate limit: {remaining}/{limit} remaining{auth_info}", file=sys.stderr)
            else:
                print(f"✓ GitHub rate limit: {remaining}/{limit} remaining{auth_info}", file=sys.stderr)

        # Suggest package manager upgrades
        from cli_audit.catalog import suggest_package_manager_upgrades
        suggest_package_manager_upgrades()

        # Reset terminal state (reset colors + ensure echo mode)
        # \033[0m = reset colors/attributes
        # Flush to ensure it's sent before returning
        print("\033[0m", end="", file=sys.stderr, flush=True)
        sys.stderr.flush()
        return 0
    except Exception as e:
        print(f"✗ Failed to write snapshot: {e}", file=sys.stderr)
        # Reset terminal state even on error
        print("\033[0m", end="", file=sys.stderr, flush=True)
        sys.stderr.flush()
        return 1


def cmd_update_local(args: argparse.Namespace) -> int:
    """Update only local installation state (fast, no network)."""
    # Check if we're in merge mode (updating specific tools only)
    merge_mode = os.environ.get("CLI_AUDIT_MERGE", "0") == "1"
    specific_tools = bool(args.tools)

    # Only show header if not in quiet merge mode
    if not (merge_mode and specific_tools):
        print("=" * 80, file=sys.stderr)
        print("Update Local State", file=sys.stderr)
        print("=" * 80, file=sys.stderr)

    # Get tools to audit
    tools_list = filter_tools(args.tools) if args.tools else all_tools()
    total = len(tools_list)

    if not (merge_mode and specific_tools):
        print(f"# Detecting local installations for {total} tools...", file=sys.stderr)

    # Load existing upstream cache for status determination
    upstream_cache = load_upstream_cache()

    # In merge mode with specific tools, load existing local state first
    if merge_mode and specific_tools:
        local_state = load_local_state()
    else:
        local_state = LocalState()
    completed = 0

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, total)) as executor:
        future_to_tool = {}
        for tool in tools_list:
            # Submit only local detection (no upstream collection)
            future = executor.submit(_detect_local_only, tool)
            future_to_tool[future] = tool

        for future in as_completed(future_to_tool):
            tool = future_to_tool[future]
            try:
                installation = future.result()
                # Determine status using cached upstream
                cached = upstream_cache.versions.get(tool.name)
                if cached and installation.installed_version:
                    norm_inst = normalize_version(installation.installed_version)
                    norm_latest = normalize_version(cached.latest_version)
                    if norm_inst == norm_latest:
                        installation.status = "UP-TO-DATE"
                    else:
                        installation.status = "OUTDATED"
                elif not installation.installed_version:
                    installation.status = "NOT INSTALLED"
                else:
                    installation.status = "UNKNOWN"

                local_state.tools[tool.name] = installation
                completed += 1
                print(f"# [{completed}/{total}] {tool.name}: {installation.installed_version or 'not installed'}", file=sys.stderr)
            except Exception as e:
                completed += 1
                print(f"# [{completed}/{total}] {tool.name}: failed ({e})", file=sys.stderr)

    # Write local state
    write_local_state(local_state, offline=OFFLINE_MODE)

    if not (merge_mode and specific_tools):
        print("", file=sys.stderr)
        print(f"✓ Local state updated: {get_local_state_path()}", file=sys.stderr)
        print(f"✓ Detected {len(local_state.tools)} tools", file=sys.stderr)

    # Update legacy snapshot for backward compatibility
    if merge_mode and specific_tools:
        # In merge mode, load existing snapshot and merge in updated tools
        existing_snapshot = load_snapshot()
        existing_tools = existing_snapshot.get("tools", [])

        # Build dict of existing tools keyed by name
        tools_by_name = {t.get("tool"): t for t in existing_tools}

        # Get updated tool data for the specific tools we just detected
        updated_tools = build_legacy_snapshot(upstream_cache, local_state).get("tools", [])
        tools_to_update = {tool.name for tool in tools_list}
        updated_tool_names = {t.get("tool") for t in updated_tools if t.get("tool") in tools_to_update}

        # Merge: update only the tools we re-detected
        for updated_tool in updated_tools:
            tool_name = updated_tool.get("tool")
            if tool_name in updated_tool_names:
                tools_by_name[tool_name] = updated_tool

        # Write merged snapshot
        merged_tools = list(tools_by_name.values())
        write_snapshot(merged_tools, offline=OFFLINE_MODE)
    else:
        # Full update: replace entire snapshot
        legacy_snapshot = build_legacy_snapshot(upstream_cache, local_state)
        write_snapshot(legacy_snapshot.get("tools", []), offline=OFFLINE_MODE)
        print(f"✓ Legacy snapshot updated: {get_snapshot_path()}", file=sys.stderr)

    return 0


def cmd_update_baseline(args: argparse.Namespace) -> int:
    """Update only upstream baseline cache (network required)."""
    print("=" * 80, file=sys.stderr)
    print("Update Upstream Baseline", file=sys.stderr)
    print("=" * 80, file=sys.stderr)

    # Get tools to audit
    tools_list = filter_tools(args.tools) if args.tools else all_tools()
    total = len(tools_list)

    # Show GitHub rate limit
    rate_limit = get_github_rate_limit()
    if rate_limit:
        remaining = rate_limit.get("remaining", 0)
        limit = rate_limit.get("limit", 0)
        authenticated = rate_limit.get("authenticated", False)
        token_source = rate_limit.get("token_source", "")

        auth_info = ""
        if authenticated:
            if token_source == "gh_cli":
                auth_info = " (via gh CLI)"
            elif token_source == "GITHUB_TOKEN":
                auth_info = " (via GITHUB_TOKEN)"

        if not authenticated and limit == 60:
            print(f"ℹ️  GitHub rate limit: {remaining}/{limit} remaining (unauthenticated)", file=sys.stderr)
            print(get_github_rate_limit_help(), file=sys.stderr)
        else:
            print(f"✓ GitHub rate limit: {remaining}/{limit} remaining{auth_info}", file=sys.stderr)

    print(f"# Collecting upstream versions for {total} tools...", file=sys.stderr)

    # Collect upstream versions only
    upstream_cache = UpstreamCache()
    completed = 0

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, total)) as executor:
        future_to_tool = {}
        for tool in tools_list:
            future = executor.submit(collect_latest_version, tool, None)
            future_to_tool[future] = tool

        for future in as_completed(future_to_tool):
            tool = future_to_tool[future]
            try:
                latest_tag, latest_num = future.result()
                version = UpstreamVersion(
                    latest_tag=latest_tag,
                    latest_version=latest_num,
                    latest_url=latest_target_url(tool, latest_tag, latest_num),
                    tool_url=tool_homepage_url(tool),
                    upstream_method=tool.source_kind,
                )
                upstream_cache.versions[tool.name] = version
                completed += 1

                display = latest_num or latest_tag or "n/a"
                print(f"# [{completed}/{total}] {tool.name}: {display}", file=sys.stderr)
            except Exception as e:
                completed += 1
                print(f"# [{completed}/{total}] {tool.name}: failed ({e})", file=sys.stderr)

    # Write upstream cache
    write_upstream_cache(upstream_cache)
    print("", file=sys.stderr)
    print(f"✓ Upstream baseline updated: {get_upstream_cache_path()}", file=sys.stderr)
    print(f"✓ Collected {len(upstream_cache.versions)} versions", file=sys.stderr)

    # Report rate limit
    rate_limit = get_github_rate_limit()
    if rate_limit:
        remaining = rate_limit.get("remaining", 0)
        limit = rate_limit.get("limit", 0)
        authenticated = rate_limit.get("authenticated", False)
        token_source = rate_limit.get("token_source", "")

        auth_info = ""
        if authenticated:
            if token_source == "gh_cli":
                auth_info = " (via gh CLI)"
            elif token_source == "GITHUB_TOKEN":
                auth_info = " (via GITHUB_TOKEN)"

        print(f"✓ GitHub rate limit: {remaining}/{limit} remaining{auth_info}", file=sys.stderr)

    return 0


def _detect_local_only(tool: Tool) -> LocalInstallation:
    """Detect local installation without collecting upstream version."""
    from cli_audit.catalog import ToolCatalog
    catalog = ToolCatalog()
    version_flag = None
    version_command = None
    if catalog.has_tool(tool.name):
        catalog_data = catalog.get_raw_data(tool.name)
        version_flag = catalog_data.get("version_flag")
        version_command = catalog_data.get("version_command")

    deep_scan = tool.name in {"node", "python", "semgrep", "pre-commit", "bandit", "black", "flake8", "isort"}
    version_num, version_line, path, install_method = audit_tool_installation(
        tool.name, tool.candidates, deep=deep_scan, version_flag=version_flag, version_command=version_command
    )

    installed = version_num if version_num else (version_line if version_line != "X" else "")

    if install_method:
        classification_reason = f"Detected via path analysis: {install_method}"
    else:
        classification_reason = "No installation detected"

    return LocalInstallation(
        installed_version=installed,
        installed_path=path,
        installed_method=install_method,
        status="UNKNOWN",  # Will be determined by caller using cached upstream
        classification_reason=classification_reason,
        category=tool.category,
        hint=tool.hint,
    )


def cmd_install(args: argparse.Namespace) -> int:
    """Install missing tools using bulk installation system."""
    print("=" * 80, file=sys.stderr)
    print("Install Mode", file=sys.stderr)
    print("=" * 80, file=sys.stderr)

    print("Please specify tools to install: audit.py --install TOOL1 TOOL2", file=sys.stderr)
    return 1


def cmd_upgrade(args: argparse.Namespace) -> int:
    """Upgrade outdated tools using upgrade orchestration system."""
    print("=" * 80, file=sys.stderr)
    print("Upgrade Mode", file=sys.stderr)
    print("=" * 80, file=sys.stderr)

    print("Upgrade functionality available via upgrade module", file=sys.stderr)
    return 1


def main() -> int:
    """Main entry point for audit system."""
    parser = argparse.ArgumentParser(
        description="AI CLI Preparation - Tool Audit and Version Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--update",
        action="store_true",
        help="Collect latest versions from upstream (network required)",
    )
    parser.add_argument(
        "--update-local",
        action="store_true",
        help="Update only local state (no network, fast)",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Update only upstream baseline cache (network required)",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install missing tools",
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Upgrade outdated tools",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "tools",
        nargs="*",
        help="Specific tools to operate on",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose)

    # Route to appropriate command
    if args.update:
        # Explicit --update flag: full update of all tools
        return cmd_update(args)
    elif getattr(args, 'update_local', False) or UPDATE_LOCAL_ONLY:
        # Update only local state (fast, no network)
        return cmd_update_local(args)
    elif getattr(args, 'update_baseline', False) or UPDATE_BASELINE_ONLY:
        # Update only upstream baseline cache
        return cmd_update_baseline(args)
    elif args.install:
        return cmd_install(args)
    elif args.upgrade:
        return cmd_upgrade(args)
    elif COLLECT_MODE and not args.tools:
        # COLLECT_MODE without specific tools: full update
        return cmd_update(args)
    else:
        # Default: audit mode (supports both snapshot rendering and per-tool fresh collection)
        return cmd_audit(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
