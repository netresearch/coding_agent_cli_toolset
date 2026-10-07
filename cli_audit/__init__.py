# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""
AI CLI Preparation - Tool version auditing and installation management.

Core Modules:
- Detection and Auditing: Version collection, catalog, snapshot management
- Foundation: Environment detection, config, package managers, install plans
- Installation: Tool installation with retry, validation, parallel operations
- Upgrade Management: Version comparison, breaking change detection, rollback
- Reconciliation: Multiple installation detection and conflict resolution
"""

__version__ = "2.0.0-alpha.6"  # keep equal to [project].version in pyproject.toml
__author__ = "AI CLI Preparation Contributors"

# Version info for backward compatibility
VERSION = __version__

# Breaking change detection
from .breaking_changes import (  # noqa: E402
    check_breaking_change_policy,
    confirm_breaking_change,
    confirm_bulk_breaking_changes,
    filter_by_breaking_changes,
    format_breaking_change_warning,
    is_major_upgrade,
)

# Bulk Operations
from .bulk import (  # noqa: E402
    BulkInstallResult,
    ProgressTracker,
    ToolSpec,
    bulk_install,
    execute_rollback,
    generate_rollback_script,
    get_missing_tools,
    resolve_dependencies,
)

# Detection and Auditing
from .catalog import ToolCatalog, ToolCatalogEntry  # noqa: E402
from .collectors import (  # noqa: E402
    collect_crates,
    collect_endoflife,
    collect_github,
    collect_gitlab,
    collect_npm,
    collect_pypi,
    get_endoflife_products,
    get_github_rate_limit,
    get_gitlab_rate_limit,
    is_wsl,
    normalize_version_tag,
)
from .config import (  # noqa: E402
    BulkPreferences,
    Config,
    Preferences,
    ToolConfig,
    load_config,
    load_config_file,
    validate_config,
)
from .detection import (  # noqa: E402
    audit_tool_installation,
    detect_install_method,
    detect_multi_versions,
    extract_version_number,
    find_paths,
    get_version_line,
)

# Foundation
from .environment import Environment, detect_environment, get_environment_from_config  # noqa: E402
from .install_plan import InstallPlan, InstallStep, dry_run_install, generate_install_plan  # noqa: E402

# Installation
from .installer import (  # noqa: E402
    InstallError,
    InstallResult,
    StepResult,
    execute_step,
    execute_step_with_retry,
    install_tool,
    validate_installation,
    verify_checksum,
)

# Logging configuration
from .logging_config import (  # noqa: E402
    get_logger,
    setup_logging,
)
from .package_managers import PackageManager, get_available_package_managers, select_package_manager  # noqa: E402
from .pins import (  # noqa: E402
    apply_pin_to_status,
    classify_pin,
    is_never,
    is_pinned,
    load_pins,
    lookup_pin,
    pin_label,
    should_skip,
)

# Reconciliation
from .reconcile import (  # noqa: E402
    SYSTEM_TOOL_SAFELIST,
    BulkReconciliationResult,
    Installation,
    ReconciliationResult,
    bulk_reconcile,
    classify_install_method,
    clear_detection_cache,
    detect_installations,
    reconcile_tool,
    sort_by_preference,
    verify_path_ordering,
)
from .render import osc8, print_summary, render_table, status_icon  # noqa: E402
from .snapshot import get_snapshot_path, load_snapshot, render_from_snapshot, write_snapshot  # noqa: E402
from .tools import Tool, all_tools, filter_tools, get_tool, latest_target_url, tool_homepage_url  # noqa: E402

# Upgrade Management
from .upgrade import (  # noqa: E402
    BulkUpgradeResult,
    UpgradeBackup,
    UpgradeCandidate,
    UpgradeResult,
    bulk_upgrade,
    check_upgrade_available,
    cleanup_backup,
    clear_version_cache,
    compare_versions,
    create_upgrade_backup,
    get_available_version,
    get_upgrade_candidates,
    restore_from_backup,
    upgrade_tool,
)

__all__ = [
    # Version
    "__version__",
    "VERSION",
    # Detection and Auditing
    "ToolCatalog",
    "ToolCatalogEntry",
    "collect_github",
    "collect_gitlab",
    "collect_pypi",
    "collect_npm",
    "collect_crates",
    "collect_endoflife",
    "get_endoflife_products",
    "detect_multi_versions",
    "normalize_version_tag",
    "extract_version_number",
    "get_github_rate_limit",
    "get_gitlab_rate_limit",
    "is_wsl",
    # Breaking changes
    "is_major_upgrade",
    "check_breaking_change_policy",
    "format_breaking_change_warning",
    "confirm_breaking_change",
    "confirm_bulk_breaking_changes",
    "filter_by_breaking_changes",
    # Foundation
    "Environment",
    "detect_environment",
    "get_environment_from_config",
    "Config",
    "ToolConfig",
    "Preferences",
    "BulkPreferences",
    "load_config",
    "load_config_file",
    "validate_config",
    "PackageManager",
    "select_package_manager",
    "get_available_package_managers",
    # Pins
    "load_pins",
    "lookup_pin",
    "is_pinned",
    "is_never",
    "should_skip",
    "classify_pin",
    "apply_pin_to_status",
    "pin_label",
    "InstallPlan",
    "InstallStep",
    "generate_install_plan",
    "dry_run_install",
    # Installation
    "InstallResult",
    "StepResult",
    "InstallError",
    "install_tool",
    "execute_step",
    "execute_step_with_retry",
    "verify_checksum",
    "validate_installation",
    # Bulk Operations
    "ToolSpec",
    "ProgressTracker",
    "BulkInstallResult",
    "bulk_install",
    "get_missing_tools",
    "resolve_dependencies",
    "generate_rollback_script",
    "execute_rollback",
    # Upgrade Management
    "UpgradeBackup",
    "UpgradeResult",
    "UpgradeCandidate",
    "BulkUpgradeResult",
    "compare_versions",
    "is_major_upgrade",
    "get_available_version",
    "check_upgrade_available",
    "clear_version_cache",
    "upgrade_tool",
    "bulk_upgrade",
    "get_upgrade_candidates",
    "filter_by_breaking_changes",
    "create_upgrade_backup",
    "restore_from_backup",
    "cleanup_backup",
    # Reconciliation
    "Installation",
    "ReconciliationResult",
    "BulkReconciliationResult",
    "detect_installations",
    "classify_install_method",
    "clear_detection_cache",
    "sort_by_preference",
    "reconcile_tool",
    "bulk_reconcile",
    "verify_path_ordering",
    "SYSTEM_TOOL_SAFELIST",
    # Logging
    "setup_logging",
    "get_logger",
]
