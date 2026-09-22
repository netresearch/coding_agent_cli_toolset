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

    def _remove(self, tmpdir: str, bin_target: str, tool: str, linked_pkg: str = "") -> str:
        """Link <prefix>/bin/<tool> to bin_target and return the npm calls.

        linked_pkg: make node_modules/<linked_pkg> a symlink to a source
        folder, the layout of `npm link` and `npm install -g <folder>`.
        """
        prefix = Path(tmpdir) / "prefix"
        target = prefix / "lib" / bin_target
        if linked_pkg:
            pkg_dir = prefix / "lib" / "node_modules" / linked_pkg
            source = Path(tmpdir) / "src"
            (source / Path(bin_target).relative_to(Path("node_modules") / linked_pkg)).parent.mkdir(parents=True)
            pkg_dir.parent.mkdir(parents=True, exist_ok=True)
            pkg_dir.symlink_to(source)
        else:
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
export PATH="{stub_dir}:/usr/bin:/bin"
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

    def test_linked_package_directory_is_not_resolved_past(self):
        # `npm link` / `npm install -g <folder>`: the package directory is a
        # symlink too, so a full resolution would leave node_modules behind
        with tempfile.TemporaryDirectory() as tmpdir:
            log = self._remove(
                tmpdir,
                "node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
                "pi",
                linked_pkg="@earendil-works/pi-coding-agent",
            )
            assert log == "npm uninstall -g @earendil-works/pi-coding-agent\n"

    def test_nested_scoped_dependency_names_the_owning_package(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = self._remove(tmpdir, "node_modules/owner/node_modules/@d/e/bin/x", "x")
            assert log == "npm uninstall -g owner\n"

    def test_binary_outside_node_modules_falls_back_to_tool_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = self._remove(tmpdir, "other/sometool", "sometool")
            assert log == "npm uninstall -g sometool\n"
