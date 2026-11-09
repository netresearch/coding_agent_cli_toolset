# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""Tests for install_direct() in scripts/install_claude.sh: the direct-download
fallback must leave a working ~/.local/bin/claude untouched when the download
or the downloaded binary fails."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")

SCRIPT = Path(__file__).parent.parent / "scripts" / "install_claude.sh"

OLD_BINARY = "#!/bin/sh\necho '1.0.0 (Claude Code)'\n"
NEW_BINARY = "#!/bin/sh\necho '2.0.0 (Claude Code)'\n"
BROKEN_BINARY = "#!/bin/sh\nexit 1\n"

# The stub writes the payload to the -o target, then exits with the given code;
# a partial transfer under `curl -f` looks like this
CURL_STUB = """#!/usr/bin/env bash
out=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-o" ]; then out="$2"; shift; fi
  shift
done
cp "$CURL_PAYLOAD" "$out"
exit "$CURL_EXIT"
"""


def _write_exe(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)


@skip_on_windows
class TestInstallDirect:
    def _run(self, home: Path, payload: str, curl_exit: int) -> subprocess.CompletedProcess[str]:
        stubs = home / "stubs"
        _write_exe(stubs / "curl", CURL_STUB)
        # cleanup_npm_versions runs after a successful download: keep it off
        # the real npm and pnpm of the machine running the tests
        _write_exe(stubs / "npm", "#!/bin/sh\nexit 0\n")
        _write_exe(stubs / "pnpm", "#!/bin/sh\nexit 0\n")
        payload_file = home / "payload"
        payload_file.write_text(payload)
        return subprocess.run(
            ["bash", "-c", f'source "{SCRIPT}"; install_direct 2.0.0'],
            capture_output=True,
            text=True,
            timeout=20,
            env={
                "HOME": str(home),
                "PATH": f"{stubs}:{home}/.local/bin:/usr/bin:/bin",
                "CURL_PAYLOAD": str(payload_file),
                "CURL_EXIT": str(curl_exit),
            },
        )

    def _native_layout(self, home: Path) -> tuple[Path, Path]:
        """~/.local/bin/claude as the native installer leaves it: a symlink
        into ~/.local/share/claude/versions/<version>."""
        target = home / ".local" / "share" / "claude" / "versions" / "1.0.0"
        _write_exe(target, OLD_BINARY)
        launcher = home / ".local" / "bin" / "claude"
        launcher.parent.mkdir(parents=True)
        launcher.symlink_to(target)
        return launcher, target

    def _no_leftovers(self, home: Path) -> None:
        assert sorted(p.name for p in (home / ".local" / "bin").iterdir()) == ["claude"]

    def test_failed_download_keeps_the_working_binary(self, tmp_path: Path):
        launcher, target = self._native_layout(tmp_path)
        result = self._run(tmp_path, "partial", curl_exit=22)
        assert result.returncode == 1, result.stderr
        assert launcher.is_symlink()
        assert launcher.resolve() == target
        assert target.read_text() == OLD_BINARY
        self._no_leftovers(tmp_path)

    def test_binary_that_does_not_run_keeps_the_working_binary(self, tmp_path: Path):
        launcher, target = self._native_layout(tmp_path)
        result = self._run(tmp_path, BROKEN_BINARY, curl_exit=0)
        assert result.returncode == 1, result.stderr
        assert launcher.is_symlink()
        assert launcher.resolve() == target
        assert target.read_text() == OLD_BINARY
        self._no_leftovers(tmp_path)

    def test_successful_download_writes_through_the_native_symlink(self, tmp_path: Path):
        launcher, target = self._native_layout(tmp_path)
        result = self._run(tmp_path, NEW_BINARY, curl_exit=0)
        assert result.returncode == 0, result.stderr
        assert launcher.is_symlink()
        assert launcher.resolve() == target
        assert target.read_text() == NEW_BINARY
        self._no_leftovers(tmp_path)

    def test_successful_download_without_launcher_creates_it(self, tmp_path: Path):
        result = self._run(tmp_path, NEW_BINARY, curl_exit=0)
        assert result.returncode == 0, result.stderr
        launcher = tmp_path / ".local" / "bin" / "claude"
        assert not launcher.is_symlink()
        assert launcher.read_text() == NEW_BINARY
        assert launcher.stat().st_mode & 0o111
        self._no_leftovers(tmp_path)
