"""Tests for tool@cycle make targets (make uninstall-node@24 etc.).

cycle_action.sh maps TOOL@CYCLE to the dedicated installer with the tool's
version env var set; the install-%/upgrade-%/uninstall-% pattern targets
branch to it whenever the stem contains '@'.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason="Shell script tests require POSIX shell"
)

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "cycle_action.sh"

STUB = (
    "#!/usr/bin/env bash\n"
    'echo "{name} action=$1'
    ' NODE_VERSION=${{NODE_VERSION:-}} RUBY_VERSION=${{RUBY_VERSION:-}}'
    ' GO_VERSION=${{GO_VERSION:-}} UV_PYTHON_SPEC=${{UV_PYTHON_SPEC:-}}"\n'
)


@skip_on_windows
class TestCycleAction:
    def _run(self, tmp_path: Path, spec: str, action: str) -> subprocess.CompletedProcess:
        stub_dir = tmp_path / "installers"
        stub_dir.mkdir(exist_ok=True)
        for name in ("install_node.sh", "install_ruby.sh", "install_go.sh", "install_python.sh"):
            stub = stub_dir / name
            stub.write_text(STUB.format(name=name))
            stub.chmod(0o755)
        return subprocess.run(
            ["bash", str(SCRIPT), spec, action],
            capture_output=True, text=True, timeout=15,
            env={"PATH": "/usr/bin:/bin", "INSTALLER_DIR": str(stub_dir)},
        )

    @pytest.mark.parametrize("spec,action,expected", [
        ("node@24", "uninstall",
         ("install_node.sh action=uninstall", "NODE_VERSION=24")),
        ("ruby@3.3", "uninstall",
         ("install_ruby.sh action=uninstall", "RUBY_VERSION=3.3")),
        ("go@1.26", "update",
         ("install_go.sh action=update", "GO_VERSION=1.26")),
        ("python@3.13", "install",
         ("install_python.sh action=install", "UV_PYTHON_SPEC=3.13")),
    ])
    def test_dispatches_with_cycle_env(self, tmp_path, spec, action, expected):
        result = self._run(tmp_path, spec, action)
        assert result.returncode == 0, result.stderr
        for part in expected:
            assert part in result.stdout

    def test_unsupported_tool_errors(self, tmp_path):
        result = self._run(tmp_path, "php@8.4", "uninstall")
        assert result.returncode == 1
        assert "no version-cycle support" in result.stderr

    def test_spec_without_cycle_errors(self, tmp_path):
        result = subprocess.run(
            ["bash", str(SCRIPT), "node", "uninstall"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 2
        assert "Usage" in result.stderr


@skip_on_windows
class TestMakeCycleTargets:
    @pytest.mark.parametrize("target,expected_action", [
        ("uninstall-node@24", "uninstall"),
        ("upgrade-node@24", "update"),
        ("install-python@3.13", "install"),
    ])
    def test_pattern_targets_branch_to_cycle_action(self, target, expected_action):
        result = subprocess.run(
            ["make", "-n", target],
            capture_output=True, text=True, timeout=30, cwd=ROOT,
        )
        assert result.returncode == 0, result.stderr
        assert f'cycle_action.sh "$spec" {expected_action}' in result.stdout

    def test_plain_targets_unaffected(self):
        result = subprocess.run(
            ["make", "-n", "uninstall-ripgrep"],
            capture_output=True, text=True, timeout=30, cwd=ROOT,
        )
        assert result.returncode == 0, result.stderr
        assert 'install_tool.sh "ripgrep" uninstall' in result.stdout
