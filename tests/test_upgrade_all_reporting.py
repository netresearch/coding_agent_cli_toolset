"""Regression tests for make upgrade-all version and path reporting."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "upgrade_all.sh"

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")


def _run_reporting_function(tmp_path: Path, before: str, after: str) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python3"
    python.write_text(f"#!/bin/sh\nprintf 'Python {after}\\n'\n")
    python.chmod(0o755)

    bash_code = f"""
set -euo pipefail
GREEN=
RESET=
TOTAL_UPGRADED=0
LOG_FILE={str(tmp_path / "upgrade.log")!r}
eval "$(sed -n '/^get_version()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^log_success_with_versions()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^log_success_with_info()/,/^}}/p' {str(SCRIPT)!r})"
log_success_with_info \
    "Python" \
    "python3" \
    "python3 --version | awk '{{print \\$2}}'" \
    {before!r}
"""
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    return subprocess.run(
        ["bash", "-c", bash_code],
        capture_output=True,
        text=True,
        env=env,
    )


def _run_unavailable_reporting(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    bash_code = f"""
set -euo pipefail
GREEN=
RESET=
TOTAL_UPGRADED=0
LOG_FILE={str(tmp_path / "upgrade.log")!r}
eval "$(sed -n '/^log_success_with_versions()/,/^}}/p' {str(SCRIPT)!r})"
log_success_with_versions "Mystery" "missing-binary" "unknown" "unknown"
"""
    return subprocess.run(
        ["bash", "-c", bash_code],
        capture_output=True,
        text=True,
    )


def _run_uv_tool_upgrade(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    version_file = tmp_path / "ansible-core-version"
    version_file.write_text("2.20.0")

    uv = bin_dir / "uv"
    uv.write_text("""#!/bin/sh
if [ "$1 $2" = "tool list" ]; then
    printf 'ansible-core v%s\\n- ansible\\n' "$(cat "$UV_VERSION_FILE")"
elif [ "$1 $2 $3" = "tool upgrade ansible-core" ]; then
    printf '2.21.0' > "$UV_VERSION_FILE"
else
    exit 1
fi
""")
    uv.chmod(0o755)

    ansible = bin_dir / "ansible"
    ansible.write_text("#!/bin/sh\nexit 0\n")
    ansible.chmod(0o755)

    bash_code = f"""
set -euo pipefail
GREEN=
RESET=
BLUE=
YELLOW=
DRY_RUN=0
TOTAL_UPGRADED=0
TOTAL_SKIPPED=0
LOG_FILE={str(tmp_path / "upgrade.log")!r}
log_info() {{ :; }}
log_skip() {{ :; }}
log_success() {{ :; }}
eval "$(sed -n '/^log_success_with_versions()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^get_uv_tool_version()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^get_uv_tool_binary()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^upgrade_uv_tools()/,/^}}/p' {str(SCRIPT)!r})"
upgrade_uv_tools
"""
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "UV_VERSION_FILE": str(version_file),
    }
    return subprocess.run(
        ["bash", "-c", bash_code],
        capture_output=True,
        text=True,
        env=env,
    )


def _run_system_manager_stage(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    project = tmp_path / "project"
    project.mkdir()

    bash_code = f"""
set -euo pipefail
GREEN=
RESET=
BLUE=
YELLOW=
DRY_RUN=0
TOTAL_UPGRADED=0
TOTAL_SKIPPED=0
PROJECT_ROOT={str(project)!r}
LOG_FILE={str(tmp_path / "upgrade.log")!r}
log_stage() {{ :; }}
log_info() {{ :; }}
log_skip() {{ :; }}
log_fail() {{ :; }}
log_reconcile() {{ :; }}
apt-get() {{
    if [ "${{1:-}}" = "--version" ]; then
        printf 'apt 2.9.0\\n'
    fi
}}
sudo() {{ "$@"; }}
command() {{
    if [ "${{1:-}}" = "-v" ]; then
        if [ "${{2:-}}" = "apt-get" ]; then
            printf '/fake/apt-get\\n'
            return 0
        fi
        return 1
    fi
    builtin command "$@"
}}
eval "$(sed -n '/^get_version()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^log_success_with_versions()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^log_success_with_info()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^stage_2_managers()/,/^}}/p' {str(SCRIPT)!r})"
stage_2_managers
"""
    return subprocess.run(
        ["bash", "-c", bash_code],
        capture_output=True,
        text=True,
    )


def _run_python_module_pip_stage(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    project = tmp_path / "project"
    project.mkdir()

    bash_code = f"""
set -euo pipefail
GREEN=
RESET=
BLUE=
YELLOW=
DRY_RUN=0
TOTAL_UPGRADED=0
TOTAL_SKIPPED=0
PROJECT_ROOT={str(project)!r}
LOG_FILE={str(tmp_path / "upgrade.log")!r}
log_stage() {{ :; }}
log_info() {{ :; }}
log_skip() {{ :; }}
log_fail() {{ :; }}
log_reconcile() {{ :; }}
python3() {{
    if [ "${{1:-}} ${{2:-}} ${{3:-}}" = "-m pip --version" ]; then
        printf 'pip 24.0 from /fake/site-packages/pip (python 3.14)\\n'
    elif [ "${{1:-}} ${{2:-}} ${{3:-}}" = "-m pip install" ]; then
        return 0
    else
        return 1
    fi
}}
command() {{
    if [ "${{1:-}}" = "-v" ]; then
        if [ "${{2:-}}" = "python3" ]; then
            printf '/fake/python3\\n'
            return 0
        fi
        return 1
    fi
    builtin command "$@"
}}
eval "$(sed -n '/^get_version()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^log_success_with_versions()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^log_success_with_info()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^stage_2_managers()/,/^}}/p' {str(SCRIPT)!r})"
stage_2_managers
"""
    return subprocess.run(
        ["bash", "-c", bash_code],
        capture_output=True,
        text=True,
    )


def _run_python_runtime_stage(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    project = tmp_path / "project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    version_file = tmp_path / "python-version"
    version_file.write_text("3.14.5")

    installer = scripts / "install_python.sh"
    installer.write_text("#!/bin/sh\nprintf '3.14.6' > \"$VERSION_FILE\"\n")
    installer.chmod(0o755)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python3"
    python.write_text('#!/bin/sh\nprintf \'Python %s\\n\' "$(cat "$VERSION_FILE")"\n')
    python.chmod(0o755)

    bash_code = f"""
set -euo pipefail
GREEN=
RESET=
BLUE=
YELLOW=
DRY_RUN=0
TOTAL_UPGRADED=0
TOTAL_SKIPPED=0
PROJECT_ROOT={str(project)!r}
LOG_FILE={str(tmp_path / "upgrade.log")!r}
log_stage() {{ :; }}
log_skip() {{ :; }}
log_success() {{ :; }}
eval "$(sed -n '/^get_version()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^log_success_with_versions()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^log_success_with_info()/,/^}}/p' {str(SCRIPT)!r})"
eval "$(sed -n '/^stage_3_runtimes()/,/^}}/p' {str(SCRIPT)!r})"
stage_3_runtimes
"""
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "VERSION_FILE": str(version_file),
    }
    return subprocess.run(
        ["bash", "-c", bash_code],
        capture_output=True,
        text=True,
        env=env,
    )


@skip_on_windows
class TestUpgradeAllVersionReporting:
    def test_reports_old_and_new_version_with_real_binary_path(self, tmp_path):
        result = _run_reporting_function(tmp_path, "3.14.5", "3.14.6")

        assert result.returncode == 0, result.stderr
        assert "Python (3.14.5 → 3.14.6 at " in result.stdout
        assert str(tmp_path / "bin" / "python3") in result.stdout
        assert "unknown" not in result.stdout

    def test_reports_unchanged_when_update_did_not_change_version(self, tmp_path):
        result = _run_reporting_function(tmp_path, "3.14.6", "3.14.6")

        assert result.returncode == 0, result.stderr
        assert "Python (3.14.6 unchanged at " in result.stdout

    def test_does_not_call_unavailable_versions_unchanged(self, tmp_path):
        result = _run_unavailable_reporting(tmp_path)

        assert result.returncode == 0, result.stderr
        assert "version unavailable" in result.stdout
        assert "unknown unchanged" not in result.stdout

    def test_runtime_stage_uses_python3_for_version_and_path(self, tmp_path):
        result = _run_python_runtime_stage(tmp_path)

        assert result.returncode == 0, result.stderr
        assert "Python (3.14.5 → 3.14.6 at " in result.stdout
        assert str(tmp_path / "bin" / "python3") in result.stdout

    def test_uv_tool_uses_package_version_and_exposed_binary(self, tmp_path):
        result = _run_uv_tool_upgrade(tmp_path)

        assert result.returncode == 0, result.stderr
        assert "ansible-core (2.20.0 → 2.21.0 at " in result.stdout
        assert str(tmp_path / "bin" / "ansible") in result.stdout
        assert "unknown" not in result.stdout

    def test_system_package_manager_reports_version_and_binary_path(self, tmp_path):
        result = _run_system_manager_stage(tmp_path)

        assert result.returncode == 0, result.stderr
        assert "apt (system) (2.9.0 unchanged at /fake/apt-get)" in result.stdout

    def test_pip_module_does_not_require_separate_pip3_launcher(self, tmp_path):
        result = _run_python_module_pip_stage(tmp_path)

        assert result.returncode == 0, result.stderr
        assert "pip (python3 -m pip) (24.0 unchanged at /fake/python3)" in result.stdout
