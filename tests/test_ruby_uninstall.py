"""Tests for per-cycle ruby uninstall (RUBY_VERSION=3.3 install_ruby.sh uninstall).

node (NODE_VERSION) and python (UV_PYTHON_SPEC) support removing a single
version cycle; ruby's uninstall previously always nuked all of ~/.rbenv.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason="Shell script tests require POSIX shell"
)

SCRIPT = Path(__file__).parent.parent / "scripts" / "install_ruby.sh"

RBENV_STUB = """#!/usr/bin/env bash
echo "rbenv $*" >> "$RBENV_STUB_LOG"
case "$1" in
  versions)
    printf '%s\\n' $RBENV_STUB_VERSIONS
    ;;
  global)
    if [ $# -eq 1 ]; then echo "$RBENV_STUB_GLOBAL"; fi
    ;;
esac
exit 0
"""


@skip_on_windows
class TestRubyPerCycleUninstall:
    def _run(self, tmpdir: str, env_extra: dict, versions: str, global_ver: str,
             args: list[str]) -> tuple[subprocess.CompletedProcess, str, Path]:
        stub_dir = Path(tmpdir) / "stubs"
        stub_dir.mkdir(exist_ok=True)
        log = Path(tmpdir) / "rbenv.log"
        log.touch()
        for name, body in (
            ("rbenv", RBENV_STUB),
            # keep the full-uninstall branch harmless if ever reached
            ("sudo", "#!/usr/bin/env bash\nexit 0\n"),
            ("dpkg", "#!/usr/bin/env bash\nexit 1\n"),
            ("apt-get", "#!/usr/bin/env bash\nexit 0\n"),
        ):
            stub = stub_dir / name
            stub.write_text(body)
            stub.chmod(0o755)

        home = Path(tmpdir) / "home"
        (home / ".rbenv" / "versions").mkdir(parents=True, exist_ok=True)

        env = {
            **os.environ,
            "HOME": str(home),
            "PATH": f"{stub_dir}:{os.environ['PATH']}",
            "RBENV_STUB_LOG": str(log),
            "RBENV_STUB_VERSIONS": versions,
            "RBENV_STUB_GLOBAL": global_ver,
            **env_extra,
        }
        env.pop("RUBY_VERSION", None)
        env.update({k: v for k, v in env_extra.items()})
        result = subprocess.run(
            ["bash", str(SCRIPT), *args],
            capture_output=True, text=True, timeout=30, env=env,
        )
        return result, log.read_text(), home

    def test_removes_only_requested_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result, log, home = self._run(
                tmpdir, {"RUBY_VERSION": "3.3"},
                versions="3.3.6 4.0.1 4.0.5", global_ver="4.0.5",
                args=["uninstall"],
            )
            assert result.returncode == 0, result.stderr
            assert "rbenv uninstall -f 3.3.6" in log
            assert "uninstall -f 4.0.1" not in log
            assert "uninstall -f 4.0.5" not in log
            # rbenv itself must survive a per-cycle removal
            assert (home / ".rbenv").exists()

    def test_full_version_spec_removes_its_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result, log, _ = self._run(
                tmpdir, {"RUBY_VERSION": "3.3.6"},
                versions="3.3.6 4.0.5", global_ver="4.0.5",
                args=["uninstall"],
            )
            assert result.returncode == 0, result.stderr
            assert "rbenv uninstall -f 3.3.6" in log

    def test_switches_global_before_removing_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result, log, _ = self._run(
                tmpdir, {"RUBY_VERSION": "3.3"},
                versions="3.3.6 4.0.5", global_ver="3.3.6",
                args=["uninstall"],
            )
            assert result.returncode == 0, result.stderr
            lines = [line for line in log.splitlines() if line]
            assert "rbenv global 4.0.5" in lines
            assert lines.index("rbenv global 4.0.5") < lines.index(
                "rbenv uninstall -f 3.3.6"
            )

    def test_missing_cycle_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result, log, home = self._run(
                tmpdir, {"RUBY_VERSION": "3.1"},
                versions="3.3.6 4.0.5", global_ver="4.0.5",
                args=["uninstall"],
            )
            assert result.returncode == 0, result.stderr
            assert "uninstall -f" not in log
            assert "not found" in result.stderr + result.stdout
            assert (home / ".rbenv").exists()

    def test_full_uninstall_without_ruby_version_still_removes_rbenv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result, _, home = self._run(
                tmpdir, {},
                versions="3.3.6 4.0.5", global_ver="4.0.5",
                args=["uninstall"],
            )
            assert result.returncode == 0, result.stderr
            assert not (home / ".rbenv").exists(), (
                "full uninstall must keep removing ~/.rbenv entirely"
            )
