"""Tests for resolve_global_bin's GOPATH fallback.

A successful `go install` lands in ${GOPATH:-$HOME/go}/bin; when that dir is
not on PATH, resolve_global_bin previously only fell back to npm's global bin
dir, so the install verify reported a false "binary not found" error.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason="Shell script tests require POSIX shell"
)

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


@skip_on_windows
class TestResolveGlobalBinGopath:
    def _resolve(self, env_setup: str, binary: str) -> str:
        full_code = f"""
set -euo pipefail
source "{SCRIPTS_DIR}/lib/common.sh"
{env_setup}
resolve_global_bin "{binary}"
"""
        result = subprocess.run(
            ["bash", "-c", full_code],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    @staticmethod
    def _make_tool(bin_dir: Path, name: str) -> Path:
        bin_dir.mkdir(parents=True, exist_ok=True)
        tool = bin_dir / name
        tool.write_text("#!/bin/sh\necho tool\n")
        tool.chmod(0o755)
        return tool

    def test_finds_binary_in_gopath_bin_off_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gopath = Path(tmpdir) / "gopath"
            tool = self._make_tool(gopath / "bin", "faketool_xyz")

            resolved = self._resolve(
                f'export GOPATH="{gopath}"; export PATH="/usr/bin:/bin"',
                "faketool_xyz",
            )
            assert resolved == str(tool)

    def test_defaults_to_home_go_bin_without_gopath(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "home"
            tool = self._make_tool(home / "go" / "bin", "faketool_xyz")

            resolved = self._resolve(
                f'export HOME="{home}"; unset GOPATH; export PATH="/usr/bin:/bin"',
                "faketool_xyz",
            )
            assert resolved == str(tool)

    def test_path_hit_wins_over_gopath(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gopath = Path(tmpdir) / "gopath"
            self._make_tool(gopath / "bin", "faketool_xyz")
            path_dir = Path(tmpdir) / "onpath"
            on_path = self._make_tool(path_dir, "faketool_xyz")

            resolved = self._resolve(
                f'export GOPATH="{gopath}"; export PATH="{path_dir}:/usr/bin:/bin"',
                "faketool_xyz",
            )
            assert resolved == str(on_path)

    def test_missing_binary_resolves_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            resolved = self._resolve(
                f'export GOPATH="{tmpdir}"; export PATH="/usr/bin:/bin"',
                "faketool_definitely_missing_xyz",
            )
            assert resolved == ""
