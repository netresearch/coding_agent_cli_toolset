"""Tests for the upgrade verdict in scripts/guide.sh.

The auto-update branch counted an upgrade as "Updated" whenever the install
script exited 0. A run where black, isort, python@3.14, codex, sd and bwrap all
stayed at their old version reported "Updated: 6". The verdict now compares the
version after the re-audit, for auto-update and interactive upgrades alike.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
GUIDE = PROJECT_ROOT / "scripts" / "guide.sh"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")


def _function(name: str) -> str:
    """Return the source of one top-level function of guide.sh."""
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", GUIDE.read_text(), re.S | re.M)
    assert match, f"{name} not found in guide.sh"
    return match.group(0)


def _run(
    tmp_path: Path, *, script_ok: str, installed: str, latest: str, audited: str, probed: str = "", marker: str = ""
) -> tuple[str, str]:
    """Run upgrade_verdict + report_upgrade_verdict; return (stdout, counters)."""
    marker_dir = Path("/tmp/.cli-audit")
    marker_dir.mkdir(exist_ok=True)
    tool = f"verdicttest{os.getpid()}"
    if marker:
        (marker_dir / f"{tool}.{marker}").write_text(latest)
    root = tmp_path / "root"
    (root / "scripts").mkdir(parents=True)
    pin_log = tmp_path / "pins.log"
    (root / "scripts" / "pin_version.sh").write_text(f'#!/bin/sh\necho "$@" >> "{pin_log}"\n')
    (root / "scripts" / "pin_version.sh").chmod(0o755)
    script = "\n".join(
        [
            f'ROOT="{root}"',
            "SUMMARY_UPDATED=0 SUMMARY_SKIPPED=0 SUMMARY_FAILED=0",
            f'json_field() {{ echo "{audited}"; }}',
            f'probe_installed_version() {{ echo "{probed}"; }}',
            _function("upgrade_verdict"),
            _function("report_upgrade_verdict"),
            f'report_upgrade_verdict "$(upgrade_verdict "{script_ok}" "{tool}" "{tool}" "{installed}" "{latest}")" '
            f'"{tool}" "{installed}" "{latest}"',
            'echo "COUNTERS updated=$SUMMARY_UPDATED skipped=$SUMMARY_SKIPPED failed=$SUMMARY_FAILED"',
        ]
    )
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True)
    for suffix in ("already-current", "held-back"):
        assert not (marker_dir / f"{tool}.{suffix}").exists(), "marker must be consumed"
    counters = proc.stdout.strip().splitlines()[-1]
    return proc.stdout, counters


def test_exit_zero_without_version_change_is_a_failure(tmp_path):
    # The black run: uv upgraded a shadowed copy, the audited version stayed 25.11.0
    out, counters = _run(tmp_path, script_ok="1", installed="25.11.0", latest="26.5.1", audited="25.11.0", probed="25.11.0")
    assert counters == "COUNTERS updated=0 skipped=0 failed=1"
    assert "did not take effect: still 25.11.0, target 26.5.1" in out


def test_version_change_is_an_update(tmp_path):
    _out, counters = _run(tmp_path, script_ok="1", installed="0.70.0", latest="0.71.0", audited="0.71.0")
    assert counters == "COUNTERS updated=1 skipped=0 failed=0"


def test_probe_rescues_a_stale_snapshot(tmp_path):
    _out, counters = _run(tmp_path, script_ok="1", installed="0.70.0", latest="0.71.0", audited="0.70.0", probed="0.71.0")
    assert counters == "COUNTERS updated=1 skipped=0 failed=0"


def test_script_error_is_a_failure(tmp_path):
    out, counters = _run(tmp_path, script_ok="0", installed="0.70.0", latest="0.71.0", audited="0.70.0")
    assert counters == "COUNTERS updated=0 skipped=0 failed=1"
    assert "install script error" in out


def test_held_back_package_is_skipped(tmp_path):
    out, counters = _run(tmp_path, script_ok="1", installed="0.9.0", latest="0.12.0", audited="0.9.0", marker="held-back")
    assert counters == "COUNTERS updated=0 skipped=1 failed=0"
    assert "no newer version than 0.9.0" in out


def test_already_current_binary_is_skipped_and_pinned(tmp_path):
    out, counters = _run(tmp_path, script_ok="1", installed="1.0.0", latest="1.1.0", audited="1.0.0", marker="already-current")
    assert counters == "COUNTERS updated=0 skipped=1 failed=0"
    assert (tmp_path / "pins.log").read_text().split()[-1] == "1.1.0"


def test_short_version_form_counts_as_update(tmp_path):
    _out, counters = _run(tmp_path, script_ok="1", installed="3.13", latest="3.13.11", audited="3.13")
    assert counters == "COUNTERS updated=1 skipped=0 failed=0"


def test_every_upgrade_branch_uses_the_verdict():
    # auto-update, [Yy] and [Aa] must all judge the outcome the same way
    source = GUIDE.read_text()
    assert source.count('$(upgrade_verdict "') == 3
    assert "SUMMARY_UPDATED=$((SUMMARY_UPDATED + 1))" not in source.replace(_function("report_upgrade_verdict"), "")
