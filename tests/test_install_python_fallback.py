# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""Behaviour of scripts/install_python.sh against a fake ``uv``.

The fake ``uv`` knows a set of downloadable versions (``FAKE_UV_AVAILABLE``)
and keeps the installed versions in a state file, so each test can describe
"installed 3.14.8, uv can download 3.14.9" and observe which installs the
script attempts and which versions it reports.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

FAKE_UV = r"""#!/usr/bin/env bash
state="$FAKE_UV_STATE"
echo "$*" >> "$FAKE_UV_LOG"
touch "$state"
highest_of() {  # highest available version of series $1
  tr ' ' '\n' <<<"$FAKE_UV_AVAILABLE" | grep -F "$1." | sort -V | tail -1
}
case "$1 $2" in
  "--version "*) echo "uv 0.0.0-fake" ;;
  "python install")
    shift 2
    upgrade=0
    if [ "$1" = "--upgrade" ]; then upgrade=1; shift; fi
    spec="$1"
    if [ "$upgrade" = 1 ]; then spec="$(highest_of "$spec")"; fi
    if [ -n "$spec" ] && tr ' ' '\n' <<<"$FAKE_UV_AVAILABLE" | grep -qxF "$spec"; then
      grep -qxF "$spec" "$state" || echo "$spec" >> "$state"
      echo "Installed Python $spec"
      exit 0
    fi
    echo "error: No download found for request: cpython-$1-linux-x86_64-gnu" >&2
    exit 2
    ;;
  "python list")
    while read -r v; do
      [ -n "$v" ] || continue
      mm="${v%.*}"
      echo "cpython-$v-linux-x86_64-gnu    $HOME/.local/bin/python$mm -> /store/cpython-$v/bin/python$mm"
      echo "cpython-$v-linux-x86_64-gnu    /store/cpython-$v/bin/python$mm"
      echo "cpython-$v+freethreaded-linux-x86_64-gnu    /store/cpython-$v-ft/bin/python${mm}t"
    done < "$state"
    ;;
  "venv "*)
    venv="${!#}"
    mkdir -p "$venv/bin"
    printf '#!/bin/sh\nexit 0\n' > "$venv/bin/python"
    chmod +x "$venv/bin/python"
    ;;
  *) exit 0 ;;
esac
"""


@pytest.fixture
def env(tmp_path: Path) -> dict:
    """Copy the script (without audit.py, so no real snapshot refresh) and a fake uv."""
    scripts = tmp_path / "repo" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(SCRIPTS_DIR / "install_python.sh", scripts / "install_python.sh")
    shutil.copytree(SCRIPTS_DIR / "lib", scripts / "lib")

    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    uv = fakebin / "uv"
    uv.write_text(FAKE_UV)
    uv.chmod(0o755)

    home = tmp_path / "home"
    home.mkdir()
    return {
        "script": scripts / "install_python.sh",
        "fakebin": fakebin,
        "state": tmp_path / "uv_state",
        "log": tmp_path / "uv_log",
        "home": home,
    }


def run(env: dict, *, spec: str, installed: list[str], available: list[str], path_prefix: str = "") -> tuple[str, list[str]]:
    env["state"].write_text("".join(f"{v}\n" for v in installed))
    env["log"].write_text("")
    proc_env = {
        "HOME": str(env["home"]),
        "PATH": f"{path_prefix}{env['fakebin']}:/usr/bin:/bin",
        "UV_PYTHON_SPEC": spec,
        "FAKE_UV_STATE": str(env["state"]),
        "FAKE_UV_LOG": str(env["log"]),
        "FAKE_UV_AVAILABLE": " ".join(available),
    }
    proc = subprocess.run(
        ["bash", str(env["script"]), "update"],
        env=proc_env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    calls = env["log"].read_text().splitlines()
    env["venv_calls"] = [line for line in calls if line.startswith("venv ")]
    installs = [line for line in calls if line.startswith("python install")]
    return proc.stdout + proc.stderr, installs


def make_dev_venv(env: dict, *, working: bool) -> Path:
    python = env["home"] / ".venvs" / "dev" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(f"#!/bin/sh\nexit {0 if working else 1}\n")
    python.chmod(0o755)
    return python


@skip_on_windows
class TestPatchFallback:
    def test_falls_back_to_next_lower_patch(self, env):
        """Installed 3.14.8, target 3.14.10 not downloadable: install 3.14.9."""
        out, installs = run(env, spec="3.14.10", installed=["3.14.8"], available=["3.14.8", "3.14.9"])
        assert installs == ["python install 3.14.10", "python install 3.14.9"]
        assert "Installed 3.14.9 (target 3.14.10" in out
        assert "[python] before: 3.14.8" in out
        assert "[python] after:  3.14.9" in out

    def test_stops_at_installed_patch(self, env):
        """Nothing between installed and target: no reinstall of 3.14.8 or lower."""
        out, installs = run(env, spec="3.14.10", installed=["3.14.8"], available=["3.14.7", "3.14.8"])
        assert installs == ["python install 3.14.10", "python install 3.14.9"]
        assert "No patch between installed 3.14.8 and target 3.14.10" in out
        assert "[python] after:  3.14.8" in out

    def test_exact_target_available(self, env):
        out, installs = run(env, spec="3.14.10", installed=["3.14.8"], available=["3.14.9", "3.14.10"])
        assert installs == ["python install 3.14.10"]
        assert "[python] after:  3.14.10" in out


@skip_on_windows
class TestMinorSpecUpgrades:
    def test_minor_spec_moves_to_newest_patch(self, env):
        """`make install-python@3.15` with 3.15.0 installed must reach 3.15.2."""
        out, installs = run(env, spec="3.15", installed=["3.15.0"], available=["3.15.0", "3.15.2"])
        assert installs == ["python install --upgrade 3.15"]
        assert "[python] before: 3.15.0" in out
        assert "[python] after:  3.15.2" in out


@skip_on_windows
class TestVersionDetection:
    def test_virtualenv_on_path_is_not_reported(self, env, tmp_path):
        """An activated venv's python3.14 (3.14.0) must not replace the uv-managed version."""
        venv_bin = tmp_path / "venv" / "bin"
        venv_bin.mkdir(parents=True)
        fake_py = venv_bin / "python3.14"
        fake_py.write_text("#!/bin/sh\necho 'Python 3.14.0'\n")
        fake_py.chmod(0o755)
        out, _ = run(
            env,
            spec="3.14.10",
            installed=["3.14.8"],
            available=["3.14.9"],
            path_prefix=f"{venv_bin}:",
        )
        assert "3.14.0" not in out
        assert "[python] before: 3.14.8" in out
        assert f"[python] path:   {env['home']}/.local/bin/python3.14" in out

    def test_other_series_does_not_leak_into_detection(self, env):
        """Series 3.1 must not match 3.14/3.15 installs, and free-threaded builds are skipped."""
        out, _ = run(env, spec="3.14.10", installed=["3.15.2", "3.14.8"], available=["3.14.10"])
        assert "[python] before: 3.14.8" in out
        assert "[python] after:  3.14.10" in out


@skip_on_windows
class TestDevVenv:
    def test_working_dev_venv_is_not_rebuilt(self, env):
        """A run for another series must not clear or move ~/.venvs/dev."""
        make_dev_venv(env, working=True)
        run(env, spec="3.15", installed=["3.14.8", "3.15.0"], available=["3.15.2"])
        assert env["venv_calls"] == []

    def test_missing_dev_venv_uses_newest_series(self, env):
        run(env, spec="3.14.10", installed=["3.14.8", "3.15.2"], available=["3.14.10"])
        dev = env["home"] / ".venvs" / "dev"
        assert env["venv_calls"] == [f"venv --clear --managed-python --python 3.15 {dev}"]

    def test_broken_dev_venv_is_rebuilt(self, env):
        """The interpreter it was built from is gone: rebuild."""
        make_dev_venv(env, working=False)
        run(env, spec="3.14.10", installed=["3.14.8"], available=["3.14.10"])
        dev = env["home"] / ".venvs" / "dev"
        assert env["venv_calls"] == [f"venv --clear --managed-python --python 3.14 {dev}"]


@skip_on_windows
class TestUvStoreDetection:
    """A uv-managed series without a pythonX.Y link on PATH is still installed."""

    def test_series_found_in_uv_store(self, tmp_path, monkeypatch):
        import json

        from cli_audit.detection import detect_multi_versions

        catalog = json.loads((SCRIPTS_DIR.parent / "catalog" / "python.json").read_text())
        uv_candidates = [c for c in catalog["multi_version"]["candidates"] if "/uv/python/" in c]
        assert uv_candidates, "catalog/python.json must list the uv install dir as a candidate"

        home = tmp_path / "home"
        store = home / ".local" / "share" / "uv" / "python"
        for name, version in [
            ("cpython-3.13-linux-x86_64-gnu", "3.13.15"),
            ("cpython-3.13+freethreaded-linux-x86_64-gnu", "3.13.0"),
        ]:
            binary = store / name / "bin" / "python3.13"
            binary.parent.mkdir(parents=True)
            binary.write_text(f"#!/bin/sh\necho 'Python {version}'\n")
            binary.chmod(0o755)
        empty = tmp_path / "empty"
        empty.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("PATH", str(empty))

        result = detect_multi_versions(
            "python",
            {"candidates": ["python{cycle}", *uv_candidates]},
            [{"cycle": "3.13", "latest": "3.13.15", "status": "security"}],
        )
        assert result[0]["installed"] == "3.13.15"
        assert result[0]["path"] == str(store / "cpython-3.13-linux-x86_64-gnu" / "bin" / "python3.13")
        assert result[0]["install_method"] == "uv"
