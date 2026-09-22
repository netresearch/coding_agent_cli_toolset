"""Tests for the npm handler of remove_installation: the package name comes
from the binary's symlink into node_modules, not from the tool name."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


def _write_stub(stub_dir: Path, name: str, body: str) -> Path:
    """Create an executable stub command in stub_dir."""
    stub = stub_dir / name
    stub.write_text(f"#!/usr/bin/env bash\n{body}\n")
    stub.chmod(0o755)
    return stub


@skip_on_windows
class TestRemoveInstallationNpmPackageName:
    """The npm handler must uninstall the package that owns the binary."""

    def _remove(self, tmpdir: str, bin_target: str, tool: str) -> str:
        """Link <prefix>/bin/<tool> to bin_target and return the npm calls."""
        prefix = Path(tmpdir) / "prefix"
        target = prefix / "lib" / bin_target
        target.parent.mkdir(parents=True)
        target.write_text("#!/usr/bin/env node\n")
        (prefix / "bin").mkdir()
        link = prefix / "bin" / tool
        link.symlink_to(Path("..") / "lib" / bin_target)

        stub_dir = Path(tmpdir) / "stubs"
        stub_dir.mkdir()
        log_file = stub_dir / "calls.log"
        log_file.touch()
        _write_stub(stub_dir, "npm", f'echo "npm $*" >> "{log_file}"')

        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
set -euo pipefail
source "{SCRIPTS_DIR}/lib/reconcile.sh"
export PATH="{stub_dir}:$PATH"
hash -r
remove_installation "{tool}" "npm" "{tool}" "{link}"
""",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        return log_file.read_text()

    def test_scoped_package_is_read_from_the_bin_symlink(self):
        # The layout of a real `npm install -g @earendil-works/pi-coding-agent`.
        # A bare `npm uninstall -g pi` would target the unrelated package `pi`.
        with tempfile.TemporaryDirectory() as tmpdir:
            log = self._remove(
                tmpdir,
                "node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js",
                "pi",
            )
            assert log == "npm uninstall -g @earendil-works/pi-coding-agent\n"

    def test_unscoped_package_is_read_from_the_bin_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # `tsc` is the bin of the package `typescript`
            log = self._remove(tmpdir, "node_modules/typescript/bin/tsc", "tsc")
            assert log == "npm uninstall -g typescript\n"

    def test_binary_outside_node_modules_falls_back_to_tool_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = self._remove(tmpdir, "other/sometool", "sometool")
            assert log == "npm uninstall -g sometool\n"
