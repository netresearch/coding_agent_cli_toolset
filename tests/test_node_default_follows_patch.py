"""The nvm default follows a newer patch of its own major, never another major.

make upgrade installed node v26.10.0 while the default stayed v26.8.1, so new
shells kept the old node and every global npm tool (bw, codex, ...) stayed
in v26.8.1's prefix.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "install_node.sh"


def _func(name: str) -> str:
    out: list[str] = []
    capturing = False
    for ln in SCRIPT.read_text().splitlines():
        if ln.startswith(f"{name}() {{"):
            capturing = True
        if capturing:
            out.append(ln)
            if ln == "}":
                break
    assert out, f"{name} not found in {SCRIPT}"
    return "\n".join(out)


def _run(default: str, node_version: str, resolved: str) -> list[str]:
    """Run the real helper against a stub nvm; return the nvm calls it made."""
    script = f"""
set -euo pipefail
calls=()
nvm() {{
  calls+=("$*")
  if [ "$1" = version ]; then
    if [ "$2" = default ]; then echo "{default}"; else echo "{resolved}"; fi
  fi
}}
NODE_VERSION="{node_version}"
NODE_CHANNEL="{node_version}"
{_func("follow_default_within_major")}
follow_default_within_major >/dev/null
printf '%s\\n' ${{calls[@]+"${{calls[@]}}"}}
"""
    res = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True)
    return [c for c in res.stdout.splitlines() if c and not c.startswith("version ")]


def _prune(tmp_path, installed: list[str], default: str, current: str, resolved: str) -> list[str]:
    """Run the real prune helper against a fake NVM_DIR; return the nvm uninstall calls."""
    for v in installed:
        (tmp_path / "versions" / "node" / v).mkdir(parents=True)
    script = f"""
set -euo pipefail
calls=()
nvm() {{
  case "$1" in
    version) if [ "$2" = default ]; then echo "{default}"; else echo "{resolved}"; fi ;;
    current) echo "{current}" ;;
    *) calls+=("$*") ;;
  esac
}}
NVM_DIR="{tmp_path}"
NODE_VERSION="26"
NODE_CHANNEL="26"
{_func("prune_older_patches")}
prune_older_patches >/dev/null
printf '%s\\n' ${{calls[@]+"${{calls[@]}}"}}
"""
    res = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True)
    return [c for c in res.stdout.splitlines() if c]


@skip_on_windows
class TestPruneOlderPatches:
    def test_removes_only_older_patches_of_the_same_major(self, tmp_path):
        calls = _prune(
            tmp_path,
            ["v26.8.1", "v26.9.0", "v26.10.0", "v26.11.0", "v25.9.0", "v2.0.0"],
            default="v26.10.0",
            current="v26.10.0",
            resolved="v26.10.0",
        )
        assert calls == ["uninstall v26.8.1", "uninstall v26.9.0"]

    def test_keeps_default_and_active_version(self, tmp_path):
        calls = _prune(
            tmp_path,
            ["v26.7.0", "v26.8.1", "v26.9.0", "v26.10.0"],
            default="v26.8.1",
            current="v26.9.0",
            resolved="v26.10.0",
        )
        assert calls == ["uninstall v26.7.0"]


@skip_on_windows
class TestFollowDefaultWithinMajor:
    def test_same_major_moves_default_and_globals(self):
        calls = _run("v26.8.1", "26", "v26.10.0")
        assert calls == [
            "use v26.10.0",
            "reinstall-packages v26.8.1",
            "alias default v26.10.0",
        ]

    @pytest.mark.parametrize(
        "default,node_version,resolved",
        [
            ("v25.9.0", "24", "v24.21.0"),  # upgrading another major
            ("v26.10.0", "26", "v26.10.0"),  # already current
            ("N/A", "26", "v26.10.0"),  # no default set
        ],
    )
    def test_default_untouched(self, default, node_version, resolved):
        assert _run(default, node_version, resolved) == []
