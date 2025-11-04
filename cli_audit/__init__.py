"""
AI CLI Preparation - Tool version auditing and installation management.

Core Modules:
- Detection and Auditing: Version collection, catalog, snapshot management
- Foundation: Environment detection, config, package managers, install plans
- Installation: Tool installation with retry, validation, parallel operations
- Upgrade Management: Version comparison, breaking change detection, rollback
- Reconciliation: Multiple installation detection and conflict resolution
"""

__version__ = "2.0.0"
__author__ = "AI CLI Preparation Contributors"

# Version info for backward compatibility
VERSION = __version__

# Detection and Auditing
from .catalog import ToolCatalog, ToolCatalogEntry
from .collectors import (
    collect_github,
    collect_gitlab,
    collect_pypi,
    collect_npm,
    collect_crates,
    normalize_version_tag,
    extract_version_number,
    get_github_rate_limit,
)
from .tools import Tool, all_tools, filter_tools, get_tool, tool_homepage_url, latest_target_url
from .detection import (
    find_paths,
    get_version_line,
    extract_version_number,
    detect_install_method,
    audit_tool_installation,
)
from .snapshot import load_snapshot, write_snapshot, render_from_snapshot, get_snapshot_path
from .render import status_icon, osc8, render_table, print_summary

# Foundation
from .environment import Environment, detect_environment, get_environment_from_config
from .config import (
    Config,
    ToolConfig,
    Preferences,
    BulkPreferences,
    load_config,
    load_config_file,
    validate_config,
)
from .package_managers import PackageManager, select_package_manager, get_available_package_managers
from .install_plan import InstallPlan, InstallStep, generate_install_plan, dry_run_install

# Installation
from .installer import (
    InstallResult,
    StepResult,
    InstallError,
    install_tool,
    execute_step,
    execute_step_with_retry,
    verify_checksum,
    validate_installation,
)

# Bulk Operations
from .bulk import (
    ToolSpec,
    ProgressTracker,
    BulkInstallResult,
    bulk_install,
    get_missing_tools,
    resolve_dependencies,
    generate_rollback_script,
    execute_rollback,
)

# Breaking change detection
from .breaking_changes import (
    is_major_upgrade,
    check_breaking_change_policy,
    format_breaking_change_warning,
    confirm_breaking_change,
    confirm_bulk_breaking_changes,
    filter_by_breaking_changes,
)

# Upgrade Management
from .upgrade import (
    UpgradeBackup,
    UpgradeResult,
    UpgradeCandidate,
    BulkUpgradeResult,
    compare_versions,
    is_major_upgrade,
    get_available_version,
    check_upgrade_available,
    clear_version_cache,
    upgrade_tool,
    bulk_upgrade,
    get_upgrade_candidates,
    filter_by_breaking_changes,
    create_upgrade_backup,
    restore_from_backup,
    cleanup_backup,
)

# Reconciliation
from .reconcile import (
    Installation,
    ReconciliationResult,
    BulkReconciliationResult,
    detect_installations,
    classify_install_method,
    clear_detection_cache,
    sort_by_preference,
    reconcile_tool,
    bulk_reconcile,
    verify_path_ordering,
    SYSTEM_TOOL_SAFELIST,
)

# Logging configuration
from .logging_config import (
    setup_logging,
    get_logger,
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
    "normalize_version_tag",
    "extract_version_number",
    "get_github_rate_limit",
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
