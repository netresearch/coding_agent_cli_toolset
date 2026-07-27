"""Regression tests for preserving deliberately uninstalled optional tools."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
PYTHON_INSTALLER = PROJECT_ROOT / "scripts" / "install_python.sh"
NODE_INSTALLER = PROJECT_ROOT / "scripts" / "install_node.sh"
TOOL_INSTALLER = PROJECT_ROOT / "scripts" / "install_tool.sh"
YARN_INSTALLER = PROJECT_ROOT / "scripts" / "install_yarn.sh"
POSIX_SHELL_ONLY = pytest.mark.skipif(os.name == "nt", reason="Behavioral shell tests require a POSIX host")


def _write_stub(directory: Path, name: str, body: str) -> Path:
    stub = directory / name
    stub.write_text(f"#!/usr/bin/env bash\n{body}\n")
    stub.chmod(0o755)
    return stub


def test_python_upgrade_does_not_fall_back_to_install():
    """A missing uv/pipx tool must stay missing during a stack update."""
    content = PYTHON_INSTALLER.read_text()

    assert 'uv tool upgrade -q "$p" >/dev/null 2>&1 || uv tool install' not in content
    assert 'pipx upgrade "$p" >/dev/null 2>&1 || pipx install' not in content


def test_python_explicit_install_still_installs_cli_tools():
    """The explicit install operation must retain its existing semantics."""
    content = PYTHON_INSTALLER.read_text()

    assert 'uv tool install -q "$p"' in content
    assert 'pipx install "$p"' in content


def test_node_update_records_optional_package_managers_before_switching_node():
    """Node updates must remember which optional managers existed beforehand."""
    content = NODE_INSTALLER.read_text()
    update_body = content.split("update_node() {", 1)[1].split("\nuninstall_node() {", 1)[0]

    ensure_nvm_position = update_body.index("ensure_nvm")
    assert update_body.index("command -v pnpm") < ensure_nvm_position
    assert update_body.index("command -v yarn") < ensure_nvm_position


def test_node_update_only_prepares_previously_installed_package_managers():
    """Corepack/npm must not bring yarn or pnpm back after uninstall."""
    content = NODE_INSTALLER.read_text()
    update_body = content.split("update_node() {", 1)[1].split("\nuninstall_node() {", 1)[0]

    assert 'if [ "$had_pnpm" -eq 1 ]; then' in update_body
    assert 'if [ "$had_yarn" -eq 1 ]; then' in update_body
    assert "corepack enable 2>" not in update_body
    assert "corepack enable pnpm" in update_body
    assert "corepack enable yarn" in update_body
    assert update_body.index('if [ "$had_pnpm" -eq 1 ]; then') < update_body.index("corepack prepare pnpm@latest")
    assert update_body.index('if [ "$had_yarn" -eq 1 ]; then') < update_body.index("corepack prepare yarn@1")


def test_generic_uninstall_refreshes_the_tool_snapshot():
    """Recommendations must not use stale state after an uninstall."""
    content = TOOL_INSTALLER.read_text()
    uninstall_body = content.split('if [ "$ACTION" = "uninstall" ]; then', 1)[1].split(
        "\n# Check if tool uses reconciliation system", 1
    )[0]

    assert '. "$DIR/lib/install_strategy.sh"' in content
    assert uninstall_body.count('refresh_snapshot "$TOOL"') >= 2


@POSIX_SHELL_ONLY
def test_direct_yarn_update_keeps_missing_yarn_uninstalled():
    """The dedicated `make upgrade-yarn` route must not bootstrap Yarn."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp = Path(tmpdir)
        home = temp / "home"
        nvm_bin = home / ".nvm" / "versions" / "node" / "v26.5.0" / "bin"
        nvm_bin.mkdir(parents=True)
        calls = temp / "calls.log"
        _write_stub(nvm_bin, "node", "echo v26.5.0")
        _write_stub(
            nvm_bin,
            "readlink",
            'echo "$HOME/.nvm/versions/node/v26.5.0/bin/node"',
        )
        _write_stub(nvm_bin, "corepack", f'echo "corepack $*" >> "{calls}"')
        _write_stub(nvm_bin, "npm", f'echo "npm $*" >> "{calls}"')

        env = os.environ.copy()
        env["HOME"] = str(home)
        env["PATH"] = f"{nvm_bin}:/usr/bin:/bin"
        result = subprocess.run(
            ["bash", str(YARN_INSTALLER), "update"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

        assert result.returncode == 0, result.stderr
        assert not calls.exists() or calls.read_text() == ""
        assert "not installed" in (result.stdout + result.stderr).lower()


@POSIX_SHELL_ONLY
def test_direct_yarn_uninstall_removes_shims_and_refreshes_snapshot():
    """The dedicated `make uninstall-yarn` route must do real cleanup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp = Path(tmpdir)
        home = temp / "home"
        stub_bin = temp / "bin"
        stub_bin.mkdir(parents=True)
        calls = temp / "calls.log"
        _write_stub(stub_bin, "npm", f'echo "npm $*" >> "{calls}"')
        _write_stub(stub_bin, "corepack", f'echo "corepack $*" >> "{calls}"')
        _write_stub(stub_bin, "python3", f'echo "python3 $*" >> "{calls}"')

        env = os.environ.copy()
        env["HOME"] = str(home)
        env["PATH"] = f"{stub_bin}:/usr/bin:/bin"
        result = subprocess.run(
            ["bash", str(YARN_INSTALLER), "uninstall"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

        assert result.returncode == 0, result.stderr
        log = calls.read_text()
        assert "npm uninstall -g yarn" in log
        assert "corepack disable yarn" in log
        assert "audit.py yarn" in log
