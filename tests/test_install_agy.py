# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""Tests for the agy (Google Antigravity CLI) catalog entry and scripts/install_agy.sh."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "install_agy.sh"

# The hand-over at the end of https://antigravity.google/cli/install.sh,
# copied verbatim; the fake binary records the arguments it is called with
FAKE_INSTALLER = """#!/bin/bash
set -euo pipefail
CUSTOM_DIR=""
BINARY_PATH="$HOME/.local/bin/agy"
mkdir -p "$HOME/.local/bin"
printf '#!/bin/sh\\necho "$*" >> "$HOME/agy-args"\\necho 1.5.19\\n' > "$BINARY_PATH"
chmod +x "$BINARY_PATH"
if [ -n "$CUSTOM_DIR" ]; then
    # Run with custom directory and absorb non-fatal soft warning exits
    "$BINARY_PATH" install --dir "$CUSTOM_DIR" || true
else
    # Run standard configuration and absorb non-fatal soft warning exits
    "$BINARY_PATH" install || true
fi
"""

CURL_STUB = """#!/usr/bin/env bash
out=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-o" ]; then out="$2"; shift; fi
  shift
done
cat "$CURL_PAYLOAD" > "$out"
"""


def _write_exe(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)


class TestAgyCatalog:
    def test_catalog_entry(self):
        data = json.loads((PROJECT_ROOT / "catalog" / "agy.json").read_text())
        assert data["name"] == "agy"
        assert data["install_method"] == "dedicated_script"
        assert data["script"] == "install_agy.sh"
        assert data["binary_name"] == "agy"
        assert data["skip_upstream"] is True
        assert "agy --version" in data["version_command"]

    def test_script_is_executable(self):
        assert os.access(SCRIPT, os.X_OK)


@skip_on_windows
class TestInstallAgy:
    def _run(self, home: Path, action: str, path_has_bin: bool, installer: str = FAKE_INSTALLER):
        stubs = home / "stubs"
        _write_exe(stubs / "curl", CURL_STUB)
        payload = home / "payload"
        payload.write_text(installer)
        # A copy without scripts/lib, so refresh_snapshot does not write the
        # repository's local_state.json
        script = home / "scripts" / "install_agy.sh"
        _write_exe(script, SCRIPT.read_text())
        path = f"{stubs}:/usr/bin:/bin"
        if path_has_bin:
            path = f"{home}/.local/bin:{path}"
        return subprocess.run(
            ["bash", str(script), action],
            capture_output=True,
            text=True,
            timeout=20,
            env={"HOME": str(home), "PATH": path, "CURL_PAYLOAD": str(payload)},
        )

    def _args(self, home: Path) -> list[str]:
        return (home / "agy-args").read_text().splitlines()

    def test_install_skips_path_line_when_bin_dir_on_path(self, tmp_path: Path):
        result = self._run(tmp_path, "install", path_has_bin=True)
        assert result.returncode == 0, result.stderr
        assert "install --skip-path" in self._args(tmp_path)

    def test_install_keeps_path_line_when_bin_dir_missing_from_path(self, tmp_path: Path):
        result = self._run(tmp_path, "install", path_has_bin=False)
        assert result.returncode == 0, result.stderr
        assert "install" in self._args(tmp_path)
        assert "install --skip-path" not in self._args(tmp_path)

    def test_install_warns_when_installer_layout_changed(self, tmp_path: Path):
        changed = FAKE_INSTALLER.replace('"$BINARY_PATH" install || true', '"$BINARY_PATH" setup || true')
        result = self._run(tmp_path, "install", path_has_bin=True, installer=changed)
        assert result.returncode == 0, result.stderr
        assert "installer layout changed" in result.stderr
        assert self._args(tmp_path)[0] == "setup"

    def test_install_leaves_existing_binary_alone(self, tmp_path: Path):
        _write_exe(tmp_path / ".local" / "bin" / "agy", '#!/bin/sh\necho "$*" >> "$HOME/agy-args"\n')
        result = self._run(tmp_path, "install", path_has_bin=True)
        assert result.returncode == 0, result.stderr
        assert "Already installed" in result.stderr
        assert not [a for a in self._args(tmp_path) if a.startswith("install")]

    def test_update_runs_agy_update(self, tmp_path: Path):
        _write_exe(tmp_path / ".local" / "bin" / "agy", '#!/bin/sh\necho "$*" >> "$HOME/agy-args"\n')
        result = self._run(tmp_path, "update", path_has_bin=True)
        assert result.returncode == 0, result.stderr
        assert self._args(tmp_path)[0] == "update"

    def test_uninstall_removes_binary(self, tmp_path: Path):
        binary = tmp_path / ".local" / "bin" / "agy"
        _write_exe(binary, "#!/bin/sh\n")
        result = self._run(tmp_path, "uninstall", path_has_bin=True)
        assert result.returncode == 0, result.stderr
        assert not binary.exists()
