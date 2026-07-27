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

    def test_runtime_stage_uses_python3_for_version_and_path(self, tmp_path):
        result = _run_python_runtime_stage(tmp_path)

        assert result.returncode == 0, result.stderr
        assert "Python (3.14.5 → 3.14.6 at " in result.stdout
        assert str(tmp_path / "bin" / "python3") in result.stdout
