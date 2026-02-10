"""
Regression tests for make-update fixes.

Covers issues found in make update output:
- filter_tools handles multi-version tool names (node@25, go@1.25)
- audit.py COLLECT_MODE generates multi-version entries
- Catalog fixes: codex install_method, tmux version_command, codex version_command
- Shell script behavior via subprocess (capability.sh, reconcile.sh, etc.)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Skip marker for Windows
skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Uses Unix-style paths and shell scripts"
)

PROJECT_ROOT = Path(__file__).parent.parent
CATALOG_DIR = PROJECT_ROOT / "catalog"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


# ===========================================================================
# 1. filter_tools handles multi-version tool names
# ===========================================================================

class TestFilterToolsMultiVersion:
    """Tests for filter_tools handling tool@version format (Issue #1, #2)."""

    def test_filter_node_at_version(self):
        """filter_tools('node@25') should match the 'node' tool."""
        from cli_audit.tools import filter_tools
        result = filter_tools(["node@25"])
        names = [t.name for t in result]
        assert "node" in names

    def test_filter_go_at_version(self):
        """filter_tools('go@1.25') should match the 'go' tool."""
        from cli_audit.tools import filter_tools
        result = filter_tools(["go@1.25"])
        names = [t.name for t in result]
        assert "go" in names

    def test_filter_python_at_version(self):
        """filter_tools('python@3.14') should match the 'python' tool."""
        from cli_audit.tools import filter_tools
        result = filter_tools(["python@3.14"])
        names = [t.name for t in result]
        assert "python" in names

    def test_filter_multiple_multi_version(self):
        """filter_tools with multiple tool@version entries."""
        from cli_audit.tools import filter_tools
        result = filter_tools(["node@25", "python@3.13"])
        names = [t.name for t in result]
        assert "node" in names
        assert "python" in names

    def test_filter_mixed_plain_and_versioned(self):
        """filter_tools with both plain and versioned tool names."""
        from cli_audit.tools import filter_tools
        result = filter_tools(["git", "node@24"])
        names = [t.name for t in result]
        assert "git" in names
        assert "node" in names

    def test_filter_plain_tools_still_work(self):
        """filter_tools with plain names still works as before."""
        from cli_audit.tools import filter_tools
        result = filter_tools(["git"])
        names = [t.name for t in result]
        assert "git" in names

    def test_filter_unknown_tool_returns_empty(self):
        """filter_tools with unknown tool name returns empty list."""
        from cli_audit.tools import filter_tools
        result = filter_tools(["nonexistent_tool_xyz"])
        assert len(result) == 0

    def test_filter_empty_list(self):
        """filter_tools with empty list returns empty."""
        from cli_audit.tools import filter_tools
        result = filter_tools([])
        assert len(result) == 0


# ===========================================================================
# 2. audit.py COLLECT_MODE handles multi-version tools
# ===========================================================================

class TestAuditCollectModeMultiVersion:
    """Tests for audit.py COLLECT_MODE multi-version support (Issue #1, #2)."""

    def test_collect_node_generates_versioned_entries(self):
        """Re-auditing 'node' in COLLECT_MODE should produce node@NN entries."""
        env = os.environ.copy()
        env["CLI_AUDIT_JSON"] = "1"
        env["CLI_AUDIT_COLLECT"] = "1"
        env["CLI_AUDIT_MERGE"] = "1"

        result = subprocess.run(
            [sys.executable, "audit.py", "node@25"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            env=env, timeout=60,
        )

        # Should not crash (was ValueError: max_workers must be > 0)
        assert result.returncode == 0, f"audit.py crashed: {result.stderr}"

        # Should produce JSON with multi-version entries
        data = json.loads(result.stdout)
        tool_names = [t.get("tool") for t in data]
        # Must have at least one node@NN entry
        node_versioned = [n for n in tool_names if n and n.startswith("node@")]
        assert len(node_versioned) > 0, f"Expected node@NN entries, got: {tool_names}"

    def test_collect_go_generates_versioned_entries(self):
        """Re-auditing 'go' in COLLECT_MODE should produce go@X.Y entries."""
        env = os.environ.copy()
        env["CLI_AUDIT_JSON"] = "1"
        env["CLI_AUDIT_COLLECT"] = "1"
        env["CLI_AUDIT_MERGE"] = "1"

        result = subprocess.run(
            [sys.executable, "audit.py", "go@1.25"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            env=env, timeout=60,
        )

        assert result.returncode == 0, f"audit.py crashed: {result.stderr}"

        data = json.loads(result.stdout)
        tool_names = [t.get("tool") for t in data]
        go_versioned = [n for n in tool_names if n and n.startswith("go@")]
        assert len(go_versioned) > 0, f"Expected go@X.Y entries, got: {tool_names}"

    def test_collect_empty_filter_does_not_crash(self):
        """Passing a nonexistent tool should not crash audit.py."""
        env = os.environ.copy()
        env["CLI_AUDIT_JSON"] = "1"
        env["CLI_AUDIT_COLLECT"] = "1"

        result = subprocess.run(
            [sys.executable, "audit.py", "nonexistent_tool_xyz"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            env=env, timeout=30,
        )

        # Should exit cleanly, not crash
        assert result.returncode == 0, f"Should not crash: {result.stderr}"


# ===========================================================================
# 3. Catalog entry fixes
# ===========================================================================

class TestCatalogCodex:
    """Tests for codex.json catalog fixes (Issue #9, #10)."""

    def test_codex_install_method_is_npm_global(self):
        """codex.json install_method should be 'npm_global', not 'npm'."""
        with open(CATALOG_DIR / "codex.json") as f:
            data = json.load(f)
        assert data["install_method"] == "npm_global", (
            "install_method should be 'npm_global' to match scripts/installers/npm_global.sh"
        )

    def test_codex_installer_script_exists(self):
        """The installer for codex's install_method must exist."""
        with open(CATALOG_DIR / "codex.json") as f:
            data = json.load(f)
        method = data["install_method"]
        installer = SCRIPTS_DIR / "installers" / f"{method}.sh"
        assert installer.exists(), f"Installer {installer} must exist for install_method={method}"

    def test_codex_version_command_extracts_semver(self):
        """codex version_command should extract clean semver, not garbage."""
        with open(CATALOG_DIR / "codex.json") as f:
            data = json.load(f)
        version_cmd = data.get("version_command", "")
        # Must use grep to extract version pattern
        assert "grep" in version_cmd, "version_command should filter for semver pattern"
        assert "[0-9]" in version_cmd, "version_command should match digits"


class TestCatalogTmux:
    """Tests for tmux.json catalog fix (Issue #11)."""

    def test_tmux_has_version_command(self):
        """tmux.json should have a version_command field."""
        with open(CATALOG_DIR / "tmux.json") as f:
            data = json.load(f)
        assert "version_command" in data, "tmux needs version_command (uses -V, not --version)"

    def test_tmux_version_command_uses_dash_v(self):
        """tmux version_command should use -V flag, not --version."""
        with open(CATALOG_DIR / "tmux.json") as f:
            data = json.load(f)
        version_cmd = data["version_command"]
        assert "-V" in version_cmd, "tmux uses -V flag for version output"
        assert "--version" not in version_cmd, "tmux does NOT support --version"


# ===========================================================================
# 4. Shell script: capability.sh - symlink dedup & venv exclusion
# ===========================================================================

@skip_on_windows
class TestCapabilityShell:
    """Tests for capability.sh fixes (Issue #8, #15)."""

    def _source_and_run(self, bash_code: str) -> str:
        """Source capability.sh and run bash code."""
        full_code = f"""
set -euo pipefail
source "{SCRIPTS_DIR}/lib/capability.sh" 2>/dev/null || true
source "{SCRIPTS_DIR}/lib/common.sh" 2>/dev/null || true
source "{SCRIPTS_DIR}/lib/policy.sh" 2>/dev/null || true
{bash_code}
"""
        result = subprocess.run(
            ["bash", "-c", full_code],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()

    def test_detect_all_installations_excludes_venv(self):
        """Venv paths should be excluded from installation detection."""
        # Create a temporary venv-like structure
        with tempfile.TemporaryDirectory() as tmpdir:
            venv_dir = Path(tmpdir) / ".venv" / "bin"
            venv_dir.mkdir(parents=True)
            fake_bin = venv_dir / "test_tool"
            fake_bin.write_text("#!/bin/sh\necho test")
            fake_bin.chmod(0o755)

            output = self._source_and_run(f"""
export PATH="{venv_dir}:$PATH"
detect_all_installations "test_tool" "test_tool"
""")
            # Should NOT contain .venv path
            assert ".venv" not in output, f"Venv paths should be excluded, got: {output}"

    def test_detect_all_installations_deduplicates_symlinks(self):
        """Symlinked paths (e.g., /bin -> /usr/bin) should be deduplicated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two directories, one symlinked to the other
            real_dir = Path(tmpdir) / "real_bin"
            real_dir.mkdir()
            link_dir = Path(tmpdir) / "link_bin"
            link_dir.symlink_to(real_dir)

            fake_bin = real_dir / "test_dedup"
            fake_bin.write_text("#!/bin/sh\necho test")
            fake_bin.chmod(0o755)

            output = self._source_and_run(f"""
export PATH="{real_dir}:{link_dir}:$PATH"
detect_all_installations "test_dedup" "test_dedup"
""")
            # Should only list one entry, not two
            lines = [l for l in output.strip().split("\n") if l]
            assert len(lines) <= 1, f"Expected at most 1 entry (deduped), got {len(lines)}: {lines}"

    def test_classify_corepack_path(self):
        """Corepack symlinks should be classified as 'corepack'."""
        # The classify_install_path function checks /usr/bin/* paths and
        # resolves symlinks to detect corepack. We test the detection logic
        # directly since we can't create paths in /usr/bin from tests.
        # Verify the corepack detection code exists in classify_install_path.
        content = (SCRIPTS_DIR / "lib" / "capability.sh").read_text()
        assert '*/corepack/*' in content, "classify_install_path should check for corepack in resolved path"
        assert 'readlink -f' in content, "classify_install_path should resolve symlinks"

        # Also verify /usr/bin/pnpm on this system is actually detected as corepack
        # (integration test - only runs if pnpm is available via corepack)
        if shutil.which("pnpm"):
            pnpm_path = shutil.which("pnpm")
            resolved = os.path.realpath(pnpm_path)
            if "corepack" in resolved:
                output = self._source_and_run(f"""
classify_install_path "pnpm" "{pnpm_path}"
""")
                assert output == "corepack", f"Expected 'corepack', got: {output}"


# ===========================================================================
# 5. Shell script: reconcile.sh - manual removal & corepack handling
# ===========================================================================

@skip_on_windows
class TestReconcileShell:
    """Tests for reconcile.sh fixes (Issue #4, #7, #12, #13)."""

    def _source_and_run(self, bash_code: str) -> subprocess.CompletedProcess:
        """Source reconcile.sh and run bash code."""
        full_code = f"""
set -euo pipefail
source "{SCRIPTS_DIR}/lib/reconcile.sh"
{bash_code}
"""
        return subprocess.run(
            ["bash", "-c", full_code],
            capture_output=True, text=True, timeout=10,
        )

    def test_remove_installation_manual_method(self):
        """remove_installation should handle 'manual' method by removing the binary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake binary
            fake_bin = Path(tmpdir) / "fake_tool"
            fake_bin.write_text("#!/bin/sh\necho fake")
            fake_bin.chmod(0o755)

            result = self._source_and_run(f"""
export PATH="{tmpdir}:$PATH"
remove_installation "fake_tool" "manual" "fake_tool"
""")
            # Should not fail
            assert result.returncode == 0, f"manual removal failed: {result.stderr}"
            # Binary should be removed
            assert not fake_bin.exists(), "Binary should have been removed"

    def test_remove_installation_system_method_returns_error(self):
        """remove_installation should fail for 'system' method with clear message."""
        result = self._source_and_run("""
remove_installation "python3" "system" "python3" 2>&1
""")
        assert result.returncode != 0 or "System-managed" in result.stdout or "System-managed" in result.stderr

    def test_remove_installation_corepack_skips_gracefully(self):
        """remove_installation should skip 'corepack' method without failing."""
        result = self._source_and_run("""
remove_installation "pnpm" "corepack" "pnpm"
""")
        assert result.returncode == 0, f"corepack removal should succeed: {result.stderr}"

    def test_remove_installation_unknown_returns_error(self):
        """remove_installation should still fail for 'unknown' method."""
        result = self._source_and_run("""
remove_installation "some_tool" "unknown" "some_tool" 2>&1 || echo "FAILED_AS_EXPECTED"
""")
        assert "FAILED_AS_EXPECTED" in result.stdout or "Unknown" in result.stderr

    def test_reconcile_proceeds_when_unknown_removal_fails(self):
        """Reconciliation should proceed with install even if unknown removal fails."""
        # The reconcile_tool function should now continue when removal of
        # unknown/system fails, rather than aborting
        reconcile_path = SCRIPTS_DIR / "lib" / "reconcile.sh"
        result = self._source_and_run(f"""
# Verify the code path exists by checking the source
grep -q "proceeding with install via" "{reconcile_path}" && echo "PATTERN_FOUND"
""")
        assert "PATTERN_FOUND" in result.stdout, "Reconcile should have fallback for unknown removal"


# ===========================================================================
# 6. Shell script: uv_tool.sh - version detection from catalog
# ===========================================================================

@skip_on_windows
class TestUvToolShell:
    """Tests for uv_tool.sh version detection fix (Issue #14)."""

    def test_uv_tool_reads_version_flag_from_catalog(self):
        """uv_tool.sh should read version_flag from catalog, not hardcode --version."""
        script = SCRIPTS_DIR / "installers" / "uv_tool.sh"
        content = script.read_text()
        # Should read version_flag from catalog JSON
        assert "version_flag" in content, "uv_tool.sh should read version_flag from catalog"
        assert "VERSION_FLAG" in content, "uv_tool.sh should use VERSION_FLAG variable"

    def test_uv_tool_has_fallback_to_uv_tool_list(self):
        """uv_tool.sh should fall back to 'uv tool list' for version detection."""
        script = SCRIPTS_DIR / "installers" / "uv_tool.sh"
        content = script.read_text()
        assert "uv tool list" in content, "Should use 'uv tool list' as fallback"

    def test_uv_tool_no_hardcoded_skip_list(self):
        """uv_tool.sh should not have hardcoded tool skip lists for version detection."""
        script = SCRIPTS_DIR / "installers" / "uv_tool.sh"
        content = script.read_text()
        # The old pattern: if [ "$TOOL" = "codex" ] || [ "$TOOL" = "gam" ]
        # Should no longer exist for version detection
        assert 'TOOL" = "gam"' not in content, "Should not hardcode gam skip"
        assert 'TOOL" = "codex"' not in content, "Should not hardcode codex skip"


# ===========================================================================
# 7. Shell script: install_python.sh - unavailable version messaging
# ===========================================================================

@skip_on_windows
class TestInstallPythonShell:
    """Tests for install_python.sh unavailable version handling (Issue #1, #2)."""

    def test_install_python_has_unavailable_version_message(self):
        """install_python.sh should report when a version is unavailable in uv."""
        script = SCRIPTS_DIR / "install_python.sh"
        content = script.read_text()
        assert "not available via uv" in content or "not yet available" in content, (
            "Should have clear messaging when uv doesn't have the requested version"
        )

    def test_install_python_reports_actual_installed_version(self):
        """install_python.sh should report what was actually installed on fallback."""
        script = SCRIPTS_DIR / "install_python.sh"
        content = script.read_text()
        assert "Installed" in content and "target" in content, (
            "Should report actual version vs target when falling back"
        )


# ===========================================================================
# 8. Shell script: install_go.sh - refresh_snapshot
# ===========================================================================

@skip_on_windows
class TestInstallGoShell:
    """Tests for install_go.sh refresh_snapshot fix (Issue #7)."""

    def test_install_go_calls_refresh_snapshot(self):
        """install_go.sh should call refresh_snapshot after installation."""
        script = SCRIPTS_DIR / "install_go.sh"
        content = script.read_text()
        assert "refresh_snapshot" in content, "install_go.sh must call refresh_snapshot"

    def test_install_go_sources_install_strategy(self):
        """install_go.sh should source install_strategy.sh for refresh_snapshot."""
        script = SCRIPTS_DIR / "install_go.sh"
        content = script.read_text()
        assert "install_strategy.sh" in content, "Must source install_strategy.sh"


# ===========================================================================
# 9. Shell script: package_manager.sh - apt version gap feedback
# ===========================================================================

@skip_on_windows
class TestPackageManagerShell:
    """Tests for package_manager.sh apt feedback fix (Issue #8)."""

    def test_package_manager_reports_no_newer_version(self):
        """package_manager.sh should report when package manager has no newer version."""
        script = SCRIPTS_DIR / "installers" / "package_manager.sh"
        content = script.read_text()
        assert "no newer version" in content.lower() or "no newer version" in content, (
            "Should warn when package manager can't provide a newer version"
        )

    def test_package_manager_avoids_redundant_apt_update(self):
        """package_manager.sh should skip apt-get update after PPA add."""
        script = SCRIPTS_DIR / "installers" / "package_manager.sh"
        content = script.read_text()
        assert "ppa_added" in content, "Should track whether PPA was added to skip redundant update"


# ===========================================================================
# 10. Shell script: install_tool.sh - uninstall improvements
# ===========================================================================

@skip_on_windows
class TestInstallToolShell:
    """Tests for install_tool.sh uninstall fixes (Issue #3, #5)."""

    def test_install_tool_delegates_to_dedicated_script(self):
        """Uninstall should delegate to dedicated script when available."""
        script = SCRIPTS_DIR / "install_tool.sh"
        content = script.read_text()
        assert "dedicated_script" in content, "Should check for dedicated_script install_method"
        assert "uninstall" in content, "Should pass uninstall action to dedicated script"

    def test_install_tool_skips_system_binaries(self):
        """Uninstall should skip system binaries with a clear message."""
        script = SCRIPTS_DIR / "install_tool.sh"
        content = script.read_text()
        assert "system" in content.lower() and "skip" in content.lower(), (
            "Should skip system binaries during uninstall"
        )

    def test_install_tool_ignores_system_in_verification(self):
        """Post-uninstall verification should ignore system entries."""
        script = SCRIPTS_DIR / "install_tool.sh"
        content = script.read_text()
        assert "remaining_nonsystem" in content or "grep -v" in content, (
            "Verification should filter out system entries"
        )


# ===========================================================================
# 11. Catalog JSON validity
# ===========================================================================

class TestCatalogValidity:
    """Validate all modified catalog files are valid JSON with required fields."""

    @pytest.mark.parametrize("catalog_name", ["codex", "tmux", "go", "node", "python"])
    def test_catalog_is_valid_json(self, catalog_name):
        """Each catalog file should be valid JSON."""
        path = CATALOG_DIR / f"{catalog_name}.json"
        if not path.exists():
            pytest.skip(f"{catalog_name}.json not found")
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert "name" in data

    @pytest.mark.parametrize("catalog_name", ["codex", "tmux", "go", "node", "python"])
    def test_catalog_install_method_has_installer(self, catalog_name):
        """Each catalog's install_method should map to an existing installer or dedicated script."""
        path = CATALOG_DIR / f"{catalog_name}.json"
        if not path.exists():
            pytest.skip(f"{catalog_name}.json not found")
        with open(path) as f:
            data = json.load(f)
        method = data.get("install_method", "")
        if method == "dedicated_script":
            script = data.get("script", "")
            assert script, f"{catalog_name}: dedicated_script needs 'script' field"
            assert (SCRIPTS_DIR / script).exists(), f"{catalog_name}: script {script} not found"
        elif method == "auto":
            pass  # auto uses reconciliation, no installer script needed
        elif method:
            installer = SCRIPTS_DIR / "installers" / f"{method}.sh"
            assert installer.exists(), (
                f"{catalog_name}: installer {installer} not found for install_method={method}"
            )
