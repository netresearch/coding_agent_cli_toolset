"""Tests for the ble.sh (Bash Line Editor) catalog entry and installer.

ble.sh is a dedicated_script tool that is *sourced* into interactive Bash
(not a PATH binary). These tests cover its catalog structure and the
installer's idempotent ~/.bashrc managed-block handling, without performing a
real network install.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATALOG = PROJECT_ROOT / "catalog" / "blesh.json"
SCRIPT = PROJECT_ROOT / "scripts" / "install_blesh.sh"

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")


class TestBleshCatalog:
    def test_catalog_exists_and_is_valid_json(self):
        assert CATALOG.exists(), "blesh.json catalog file should exist"
        json.loads(CATALOG.read_text())

    def test_catalog_structure(self):
        data = json.loads(CATALOG.read_text())
        assert data["name"] == "blesh"
        assert data["install_method"] == "dedicated_script"
        assert data["script"] == "install_blesh.sh"
        assert data["github_repo"] == "akinomyoga/ble.sh"
        assert data["binary_name"] == "ble.sh"

    def test_catalog_has_version_command(self):
        data = json.loads(CATALOG.read_text())
        # ble.sh has no PATH binary; version must come from the sourced file.
        assert "blesh/ble.sh" in data["version_command"]
        assert "--version" in data["version_command"]

    def test_catalog_notes_document_sourced_nature(self):
        data = json.loads(CATALOG.read_text())
        assert "source" in data.get("notes", "").lower()


@skip_on_windows
class TestBleshInstaller:
    def test_script_exists_and_executable(self):
        assert SCRIPT.exists(), "install_blesh.sh should exist"
        assert os.access(SCRIPT, os.X_OK), "install_blesh.sh should be executable"

    def test_unknown_action_prints_usage(self):
        proc = subprocess.run(
            ["bash", str(SCRIPT), "bogus"],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 1
        assert "Usage" in proc.stderr

    def _run_sourced(self, home: Path, snippet: str) -> subprocess.CompletedProcess:
        """Source the installer (main-guard prevents dispatch) and run snippet."""
        env = {**os.environ, "HOME": str(home)}
        return subprocess.run(
            ["bash", "-c", f'source "{SCRIPT}"\n{snippet}'],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_bashrc_block_is_idempotent(self, tmp_path):
        proc = self._run_sourced(
            tmp_path,
            "ensure_bashrc_block; ensure_bashrc_block; " r'grep -cF "# >>> cli-audit: ble.sh >>>" "$HOME/.bashrc"',
        )
        assert proc.returncode == 0, proc.stderr
        # Two inserts must yield exactly one managed block.
        assert proc.stdout.strip().splitlines()[-1] == "1"

    def test_bashrc_block_removal(self, tmp_path):
        proc = self._run_sourced(
            tmp_path,
            "ensure_bashrc_block; remove_bashrc_block; " r'grep -cF "cli-audit: ble.sh" "$HOME/.bashrc" || true',
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip().splitlines()[-1] == "0"

    def test_bashrc_block_preserves_existing_content(self, tmp_path):
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("export FOO=bar\nalias ll='ls -la'\n")
        proc = self._run_sourced(
            tmp_path,
            'ensure_bashrc_block; remove_bashrc_block; cat "$HOME/.bashrc"',
        )
        assert proc.returncode == 0, proc.stderr
        assert "export FOO=bar" in proc.stdout
        assert "alias ll='ls -la'" in proc.stdout
        assert "cli-audit: ble.sh" not in proc.stdout

    def test_bashrc_removal_preserves_content_when_end_marker_missing(self, tmp_path):
        # A begin marker without its matching end marker (tampering / interrupted
        # write) must NOT cause removal to delete everything that follows it.
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("keepA\n" "# >>> cli-audit: ble.sh >>>\n" "orphan\n" "keepB\n")
        proc = self._run_sourced(tmp_path, 'remove_bashrc_block; cat "$HOME/.bashrc"')
        assert proc.returncode == 0, proc.stderr
        # Unbalanced block is left intact; trailing user content survives.
        assert "keepA" in proc.stdout
        assert "keepB" in proc.stdout
