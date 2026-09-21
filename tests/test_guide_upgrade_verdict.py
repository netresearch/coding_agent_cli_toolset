"""Tests for the upgrade verdict in scripts/guide.sh.

The auto-update branch counted an upgrade as "Updated" whenever the install
script exited 0. A run where black, isort, python@3.14, codex, sd and bwrap all
stayed at their old version reported "Updated: 6". The verdict now compares the
version after the re-audit, for auto-update and interactive upgrades alike.
"""

from __future__ import annotations

import os
import re
import shutil
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
    tmp_path: Path,
    *,
    script_ok: str,
    installed: str,
    latest: str,
    audited: str,
    probed: str = "",
    marker: str = "",
    clear_first: bool = False,
) -> tuple[str, str]:
    """Run upgrade_verdict + report_upgrade_verdict; return (stdout, counters)."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    tool = "verdicttest"
    if marker:
        (marker_dir / f"{tool}.{marker}").write_text(latest)
    root = tmp_path / "root"
    (root / "scripts").mkdir(parents=True)
    pin_log = tmp_path / "pins.log"
    (root / "scripts" / "pin_version.sh").write_text(f'#!/bin/sh\necho "$@" >> "{pin_log}"\n')
    (root / "scripts" / "pin_version.sh").chmod(0o755)
    script = "\n".join(
        [
            "set -euo pipefail",
            f'ROOT="{root}"',
            f'MARKER_DIR="{marker_dir}"',
            "SUMMARY_UPDATED=0 SUMMARY_SKIPPED=0 SUMMARY_FAILED=0",
            f'json_field() {{ echo "{audited}"; }}',
            f'probe_installed_version() {{ echo "{probed}"; }}',
            _function("upgrade_verdict"),
            _function("report_upgrade_verdict"),
            _function("clear_upgrade_markers"),
            f'clear_upgrade_markers "{tool}"' if clear_first else ":",
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


def test_already_current_binary_is_skipped_without_a_pin(tmp_path):
    # A pin would hide the tool from every later run, the next real release included
    out, counters = _run(tmp_path, script_ok="1", installed="1.0.0", latest="1.1.0", audited="1.0.0", marker="already-current")
    assert counters == "COUNTERS updated=0 skipped=1 failed=0"
    assert not (tmp_path / "pins.log").exists()


def test_marker_from_an_earlier_run_is_cleared_before_install(tmp_path):
    out, counters = _run(
        tmp_path, script_ok="1", installed="0.9.0", latest="0.12.0", audited="0.9.0", marker="held-back", clear_first=True
    )
    assert counters == "COUNTERS updated=0 skipped=0 failed=1"


def test_short_version_needs_a_dot_boundary(tmp_path):
    # 1.1 is not a short form of 1.12.0
    _out, counters = _run(tmp_path, script_ok="1", installed="1.1", latest="1.12.0", audited="1.1")
    assert counters == "COUNTERS updated=0 skipped=0 failed=1"


def test_short_version_form_counts_as_update(tmp_path):
    _out, counters = _run(tmp_path, script_ok="1", installed="3.13", latest="3.13.11", audited="3.13")
    assert counters == "COUNTERS updated=1 skipped=0 failed=0"


def test_every_upgrade_branch_uses_the_verdict():
    # auto-update, [Yy] and [Aa] must all judge the outcome the same way
    source = GUIDE.read_text()
    assert source.count('$(upgrade_verdict "') == 3
    assert source.count('  clear_upgrade_markers "$catalog_tool"') == 3
    assert "pin_version.sh" not in _function("report_upgrade_verdict")
    assert "SUMMARY_UPDATED=$((SUMMARY_UPDATED + 1))" not in source.replace(_function("report_upgrade_verdict"), "")


SCRIPTS = PROJECT_ROOT / "scripts"


def _run_package_manager(
    tmp_path: Path,
    *,
    install_rc: int,
    candidate: str,
    detected: str = "0.9.0",
    lang: str = "C",
    owner: str = "bubblewrap",
    dpkg_stub: str = "",
) -> bool:
    """Run package_manager.sh bwrap against stub apt tools; return whether held-back was marked."""
    if not shutil.which("jq"):
        pytest.skip("jq not installed")
    fake = tmp_path / "fakebin"
    fake.mkdir()
    stubs = {
        "sudo": 'exec "$@"',
        "apt-get": f'[ "$1" = install ] && exit {install_rc}; exit 0',
        "dpkg-query": "echo 0.9.0-1ubuntu0.3",
        # dpkg -S <path>: which package owns the binary found on PATH
        "dpkg": dpkg_stub or f'[ "$1" = -S ] && [ -n "{owner}" ] && echo "{owner}: $2" && exit 0; exit 1',
        # apt-cache translates its labels unless LC_ALL=C
        "apt-cache": (
            'label="Candidate:"; [ "${LC_ALL:-}" != C ] && [ "${LANG:-C}" != C ] && label="Installationskandidat:"\n'
            f'echo "  Installed: 0.9.0-1ubuntu0.3"; echo "  $label {candidate}"'
        ),
        "bwrap": f"echo 'bubblewrap {detected}'",
        "python3": "exit 0",  # refresh_snapshot must not touch the real snapshot
    }
    for name, body in stubs.items():
        (fake / name).write_text(f"#!/bin/bash\n{body}\n")
        (fake / name).chmod(0o755)
    (fake / "jq").symlink_to(shutil.which("jq"))
    marker = tmp_path / "markers" / "bwrap.held-back"
    env = {**os.environ, "PATH": f"{fake}:/usr/bin:/bin", "CLI_AUDIT_MARKER_DIR": str(tmp_path / "markers"), "LANG": lang}
    env.pop("LC_ALL", None)
    subprocess.run(
        ["bash", str(SCRIPTS / "installers" / "package_manager.sh"), "bwrap"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return marker.exists()


def test_package_manager_marks_held_back_when_candidate_is_installed(tmp_path):
    assert _run_package_manager(tmp_path, install_rc=0, candidate="0.9.0-1ubuntu0.3")


def test_failed_install_is_not_held_back(tmp_path):
    # dpkg lock, refused sudo, no network: the version is unchanged for another reason
    assert not _run_package_manager(tmp_path, install_rc=100, candidate="0.9.0-1ubuntu0.3")


def test_newer_candidate_is_not_held_back(tmp_path):
    # apt has a newer package, yet the detected version did not move: something shadows it
    assert not _run_package_manager(tmp_path, install_rc=0, candidate="0.12.0-1")


def _pin_applies(*args: str) -> bool:
    script = "\n".join(["set -euo pipefail", _function("pin_applies"), "pin_applies " + " ".join(f'"{a}"' for a in args)])
    return subprocess.run(["bash", "-c", script]).returncode == 0


def test_skipped_release_hides_the_tool_until_a_newer_one_is_out():
    # s = "Skip only 1.1.0 (ask again when newer patch available)"
    assert _pin_applies("1.1.0", "1.1.0", "1.0.0")
    assert not _pin_applies("1.1.0", "1.2.0", "1.0.0")


def test_held_version_keeps_hiding_the_tool():
    # p = "Pin to 1.0.0 (don't ask for upgrades)"
    assert _pin_applies("1.0.0", "1.2.0", "1.0.0")


def test_never_and_cycle_pins_apply():
    assert _pin_applies("never", "1.2.0", "")
    assert _pin_applies("3.13", "3.13.11", "3.13.4", "3.13")
    assert not _pin_applies("", "1.2.0", "1.0.0")


def test_guide_loop_uses_pin_applies_for_both_pin_kinds():
    assert GUIDE.read_text().count('&& pin_applies "$') == 2


def test_held_back_detection_is_locale_independent(tmp_path):
    assert _run_package_manager(tmp_path, install_rc=0, candidate="0.9.0-1ubuntu0.3", lang="de_DE.UTF-8")


def test_shadowed_package_is_not_held_back(tmp_path):
    # apt installed its newest 0.9.0, but a copy no package owns answers on PATH
    assert not _run_package_manager(tmp_path, install_rc=0, candidate="0.9.0-1ubuntu0.3", detected="0.8.0", owner="")


def test_package_version_longer_than_binary_version_is_held_back(tmp_path):
    # universal-ctags 5.9.20210829.0-1 prints 5.9.0; ownership decides, not versions
    assert _run_package_manager(tmp_path, install_rc=0, candidate="0.9.0-1ubuntu0.3", detected="0.9")


def test_binary_owned_by_another_package_is_not_held_back(tmp_path):
    assert not _run_package_manager(tmp_path, install_rc=0, candidate="0.9.0-1ubuntu0.3", owner="otherpkg")


def test_install_that_left_nothing_is_a_failure(tmp_path):
    out, counters = _run(tmp_path, script_ok="1", installed="", latest="", audited="")
    assert counters == "COUNTERS updated=0 skipped=0 failed=1"


def test_unknown_upstream_is_not_a_failure(tmp_path):
    out, counters = _run(tmp_path, script_ok="1", installed="2.0.0", latest="", audited="2.0.0")
    assert counters == "COUNTERS updated=0 skipped=1 failed=0"
    assert "No upstream version known" in out


def test_probe_path_skips_venv_dirs(tmp_path):
    venv = tmp_path / "env-with-any-name"  # recognised by pyvenv.cfg alone
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
    named = tmp_path / "proj" / "venv" / "bin"
    named.mkdir(parents=True)
    keep = tmp_path / ".local" / "bin"
    keep.mkdir(parents=True)
    path = ":".join([str(venv / "bin") + "/", str(named), str(keep)])
    script = "\n".join(["set -euo pipefail", _function("installation_path"), f'PATH="{path}"', "installation_path"])
    out = subprocess.run(["/bin/bash", "-c", script], capture_output=True, text=True, check=True).stdout
    assert out == str(keep)


# Real `dpkg -S` output shapes (Ubuntu 24.04): diversions, several owners,
# multiarch suffixes, and merged-/usr packages that still record /bin/x
DPKG_DIVERTED = 'echo "diversion by other from: $2"; echo "diversion by other to: $2.other"; echo "bubblewrap, other: $2"'
DPKG_MULTIARCH = 'echo "bubblewrap:amd64: $2"'
# A comma inside the path must not become a second "owner" before the colon split
DPKG_COMMA_PATH = 'echo "other: /opt/x, bubblewrap"'
DPKG_BIN_ONLY = 'case "$2" in /bin/bwrap) echo "bubblewrap: /bin/bwrap" ;; *) echo "no path found" >&2; exit 1 ;; esac'


@pytest.mark.parametrize(
    "dpkg_stub",
    [DPKG_DIVERTED, DPKG_MULTIARCH, DPKG_BIN_ONLY],
    ids=["diverted", "multiarch", "bin-only"],
)
def test_owner_is_found_in_real_dpkg_output_shapes(tmp_path, dpkg_stub):
    assert _run_package_manager(tmp_path, install_rc=0, candidate="0.9.0-1ubuntu0.3", dpkg_stub=dpkg_stub)


def test_comma_in_the_path_is_not_an_owner(tmp_path):
    assert not _run_package_manager(tmp_path, install_rc=0, candidate="0.9.0-1ubuntu0.3", dpkg_stub=DPKG_COMMA_PATH)
