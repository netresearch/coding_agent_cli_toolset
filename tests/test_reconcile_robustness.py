"""Reconcile and installer robustness, ported from the cli-tools-skill fork.

* ``remove_installation`` passed the *tool* name to ``cargo uninstall``. Cargo
  wants the crate name, which differs from the binary for real tools
  (``ripgrep_all`` installs ``rga``, ``git-delta`` installs ``delta``), so the
  uninstall failed and ``|| true`` swallowed it, leaving the duplicate behind.
* ``detect_all_installations`` parsed the prose of ``type -a``
  (``"<name> is <path>"``). Bash localizes that sentence where its
  translations are installed, and every localized line was then dropped.
* After removing an installation, nothing checked that the surviving binary
  still runs, though a wrapper can depend on files the removed package owned.
* ``refresh_snapshot`` is bookkeeping after a successful install, but nineteen
  installers called it unguarded, so a failed refresh turned the install into
  a reported failure.
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")

CARGO_LIST = """ripgrep_all v0.10.10:
    rga
    rga-fzf
tokei v15.0.0:
    tokei
git-delta v0.18.2:
    delta
"""


def _stub(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(f"#!/usr/bin/env bash\n{body}\n")
    path.chmod(0o755)
    return path


def _bash(snippet: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", snippet], capture_output=True, text=True, timeout=timeout)


class TestCargoUninstallUsesTheOwningCrate:
    def _uninstall(self, tmp_path: Path, binary: str) -> str:
        stubs = tmp_path / "stubs"
        log = tmp_path / "cargo.log"
        log.touch()
        listing = tmp_path / "list.txt"
        listing.write_text(CARGO_LIST)
        _stub(
            stubs,
            "cargo",
            f"""case "$1 $2" in
  "install --list") cat "{listing}" ;;
  uninstall*) echo "cargo $*" >> "{log}" ;;
esac""",
        )
        proc = _bash(f"""set -euo pipefail
source "{SCRIPTS}/lib/reconcile.sh"
export PATH="{stubs}:/usr/bin:/bin"
hash -r
remove_installation "{binary}" cargo "{binary}"
""")
        assert proc.returncode == 0, proc.stderr
        return log.read_text()

    @pytest.mark.parametrize("binary,crate", [("rga", "ripgrep_all"), ("delta", "git-delta"), ("tokei", "tokei")])
    def test_uninstalls_the_crate_that_owns_the_binary(self, tmp_path, binary, crate):
        assert self._uninstall(tmp_path, binary) == f"cargo uninstall {crate}\n"

    def test_unknown_binary_falls_back_to_the_tool_name(self, tmp_path):
        assert self._uninstall(tmp_path, "notinstalled") == "cargo uninstall notinstalled\n"


class TestDetectAllInstallationsIsLocaleIndependent:
    def test_localized_type_output_still_finds_the_binary(self, tmp_path):
        bin_dir = tmp_path / "bin"
        _stub(bin_dir, "zztool", "echo 1.0")
        # What `type -a` prints where bash's German translations are installed.
        proc = _bash(f"""source "{SCRIPTS}/lib/capability.sh"
export PATH="{bin_dir}:/usr/bin:/bin"
type() {{
  if [ "$1" = "-a" ]; then echo "$2 ist {bin_dir}/$2"; else builtin type "$@"; fi
}}
detect_all_installations zztool zztool
""")
        assert f"{bin_dir}/zztool" in proc.stdout, proc.stdout + proc.stderr


class TestSurvivingBinaryMustRun:
    def test_warns_when_the_remaining_binary_no_longer_runs(self, tmp_path):
        broken = _stub(tmp_path / "bin", "wrapped", 'exec /nonexistent/lib/wrapped "$@"')
        proc = _bash(f'source "{SCRIPTS}/lib/reconcile.sh"\nwarn_if_bin_does_not_run wrapped "{broken}"')
        assert proc.returncode == 0
        assert "does not run" in proc.stderr

    def test_is_silent_when_the_binary_runs(self, tmp_path):
        ok = _stub(tmp_path / "bin", "fine", 'echo "fine 1.0"')
        proc = _bash(f'source "{SCRIPTS}/lib/reconcile.sh"\nwarn_if_bin_does_not_run fine "{ok}"')
        assert proc.returncode == 0
        assert proc.stderr == ""


class TestSnapshotRefreshIsNotFatal:
    def test_every_refresh_snapshot_call_is_guarded(self):
        unguarded = []
        for path in SCRIPTS.rglob("*.sh"):
            for n, line in enumerate(path.read_text().splitlines(), 1):
                code = line.split("#", 1)[0].strip()
                if code.startswith('refresh_snapshot "') and not code.endswith("|| true"):
                    unguarded.append(f"{path.relative_to(PROJECT_ROOT)}:{n}: {code}")
        assert not unguarded, "\n".join(unguarded)
