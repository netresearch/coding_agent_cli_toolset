"""
AI CLI Preparation - Tool version auditing and installation management.

Phase 1: Detection and auditing (complete)
Phase 2.1: Foundation - Environment, config, package managers, install plans (complete)
Phase 2.2: Core Installation - Single tool installation with retry and validation (complete)
Phase 2.3: Bulk Operations - Parallel installation with progress tracking (complete)
Phase 2.4: Upgrade Management - Version comparison, breaking changes, rollback (complete)
Phase 2.5: Reconciliation - Detect and manage multiple tool installations (complete)
"""

__version__ = "2.0.0-alpha.6"
__author__ = "AI CLI Preparation Contributors"

# Version info for backward compatibility
VERSION = __version__

# Phase 2.1 exports
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

# Phase 2.2 exports
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

# Phase 2.3 exports
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

# Phase 2.4 exports
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

# Phase 2.5 exports
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
    # Breaking changes
    "is_major_upgrade",
    "check_breaking_change_policy",
    "format_breaking_change_warning",
    "confirm_breaking_change",
    "confirm_bulk_breaking_changes",
    "filter_by_breaking_changes",
    # Phase 2.1
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
    # Phase 2.2
    "InstallResult",
    "StepResult",
    "InstallError",
    "install_tool",
    "execute_step",
    "execute_step_with_retry",
    "verify_checksum",
    "validate_installation",
    # Phase 2.3
    "ToolSpec",
    "ProgressTracker",
    "BulkInstallResult",
    "bulk_install",
    "get_missing_tools",
    "resolve_dependencies",
    "generate_rollback_script",
    "execute_rollback",
    # Phase 2.4
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
    # Phase 2.5
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
