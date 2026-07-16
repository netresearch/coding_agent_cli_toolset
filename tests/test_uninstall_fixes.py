"""Tests for uninstall fixes: uv removal, nvm npm-package removal,
multi-install loop resilience, and apt path precision.

Covers the three bugs found via `make uninstall-poetry` / `make uninstall-pnpm`:
1. remove_installation had no `uv` handler, aborting the whole uninstall loop
2. npm packages inside an nvm node dir classified as `nvm` and were skipped
3. remove_installation re-resolved the binary via `command -v`, hitting the
   wrong installation when multiple exist (apt removal silently no-oped)
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason="Shell script tests require POSIX shell"
)

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


def _write_stub(stub_dir: Path, name: str, body: str) -> Path:
    """Create an executable stub command in stub_dir."""
    stub = stub_dir / name
    stub.write_text(f"#!/usr/bin/env bash\n{body}\n")
    stub.chmod(0o755)
    return stub


@skip_on_windows
class TestRemoveInstallationUv:
    """remove_installation must support the `uv` method (bug 1)."""

    def _run(self, bash_code: str) -> subprocess.CompletedProcess:
        full_code = f"""
set -euo pipefail
source "{SCRIPTS_DIR}/lib/reconcile.sh"
{bash_code}
"""
        return subprocess.run(
            ["bash", "-c", full_code],
            capture_output=True, text=True, timeout=10,
        )

    def test_uv_method_calls_uv_tool_uninstall(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stub_dir = Path(tmpdir)
            log_file = stub_dir / "calls.log"
            _write_stub(stub_dir, "uv", f'echo "uv $*" >> "{log_file}"')

            result = self._run(f"""
export PATH="{stub_dir}:$PATH"
remove_installation "poetry" "uv" "poetry"
""")
            assert result.returncode == 0, f"uv removal failed: {result.stderr}"
            assert "tool uninstall poetry" in log_file.read_text()

    def test_uv_method_with_failing_uv_does_not_crash(self):
        result = self._run("""
uv() { return 127; }
remove_installation "poetry" "uv" "poetry" 2>&1 || true
echo "SURVIVED"
""")
        assert "SURVIVED" in result.stdout


@skip_on_windows
class TestNvmClassification:
    """npm packages inside an nvm node dir must classify as npm, not nvm (bug 2)."""

    def _classify(self, tool: str, path: str) -> str:
        full_code = f"""
set -euo pipefail
source "{SCRIPTS_DIR}/lib/capability.sh"
classify_install_path "{tool}" "{path}"
"""
        result = subprocess.run(
            ["bash", "-c", full_code],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def test_pnpm_in_nvm_dir_classifies_as_npm(self):
        home = os.environ["HOME"]
        assert (
            self._classify("pnpm", f"{home}/.nvm/versions/node/v26.3.1/bin/pnpm")
            == "npm(v26.3.1)"
        )

    def test_eslint_in_nvm_dir_classifies_as_npm(self):
        home = os.environ["HOME"]
        assert (
            self._classify("eslint", f"{home}/.nvm/versions/node/v20.11.0/bin/eslint")
            == "npm(v20.11.0)"
        )

    def test_node_runtime_binaries_stay_nvm(self):
        home = os.environ["HOME"]
        for runtime_bin in ("node", "npm", "npx", "corepack"):
            assert (
                self._classify(
                    runtime_bin, f"{home}/.nvm/versions/node/v26.3.1/bin/{runtime_bin}"
                )
                == "nvm(v26.3.1)"
            ), f"{runtime_bin} must stay nvm-managed"

    def test_detect_install_method_npm_package_under_nvm(self):
        """detect_install_method must make the same distinction as classify."""
        home = os.environ["HOME"]
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_nvm_bin = Path(f"{tmpdir}/home/.nvm/versions/node/v26.3.1/bin")
            fake_nvm_bin.mkdir(parents=True)
            for name in ("pnpm", "node"):
                _write_stub(fake_nvm_bin, name, "echo fake")

            full_code = f"""
set -euo pipefail
export HOME="{tmpdir}/home"
source "{SCRIPTS_DIR}/lib/capability.sh"
export PATH="{fake_nvm_bin}:$PATH"
echo "pnpm=$(detect_install_method pnpm pnpm)"
echo "node=$(detect_install_method node node)"
"""
            result = subprocess.run(
                ["bash", "-c", full_code],
                capture_output=True, text=True, timeout=10,
            )
            assert result.returncode == 0, result.stderr
            assert "pnpm=npm" in result.stdout
            assert "node=nvm" in result.stdout
        # keep flake8 happy about unused import pattern parity
        assert home


@skip_on_windows
class TestUninstallLoopResilience:
    """One failing removal must not abort the multi-install loop (bug 1, class fix)."""

    def test_unsupported_method_does_not_abort_loop(self):
        """Replicate the install_tool.sh loop shape: a method the remover
        rejects must not kill the pipeline under set -euo pipefail."""
        full_code = f"""
set -euo pipefail
source "{SCRIPTS_DIR}/lib/reconcile.sh"
printf 'weirdmethod:/tmp/nope\\nmanual:/tmp/alsonope\\n' | while IFS=: read -r method path; do
  base_method="${{method%%(*}}"
  remove_installation "sometool" "$base_method" "sometool" "$path" || true
done
echo "LOOP_COMPLETED"
"""
        result = subprocess.run(
            ["bash", "-c", full_code],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert "LOOP_COMPLETED" in result.stdout

    def test_install_tool_uninstall_loop_tolerates_removal_failure(self):
        """The actual loop in install_tool.sh must guard remove_installation."""
        content = (SCRIPTS_DIR / "install_tool.sh").read_text()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("remove_installation "):
                assert stripped.endswith("|| true"), (
                    "remove_installation in the uninstall loop must not abort "
                    f"the loop under set -e: {stripped!r}"
                )
                break
        else:
            pytest.fail("uninstall loop in install_tool.sh not found")


@skip_on_windows
class TestRemoveInstallationAptPathPrecision:
    """The apt handler must use the detected path, not command -v (bug 3)."""

    def _run_with_stubs(self, stub_dir: Path, bash_code: str) -> subprocess.CompletedProcess:
        full_code = f"""
set -euo pipefail
source "{SCRIPTS_DIR}/lib/reconcile.sh"
export PATH="{stub_dir}:$PATH"
hash -r
{bash_code}
"""
        return subprocess.run(
            ["bash", "-c", full_code],
            capture_output=True, text=True, timeout=10,
        )

    def _apt_stubs(self, stub_dir: Path, log_file: Path) -> None:
        # dpkg knows only /usr/bin/poetry, owned by python3-poetry
        _write_stub(stub_dir, "dpkg", f"""
echo "dpkg $*" >> "{log_file}"
case "$1" in
  -S)
    if [ "$2" = "/usr/bin/poetry" ]; then
      echo "python3-poetry: /usr/bin/poetry"
      exit 0
    fi
    exit 1
    ;;
  -s)
    [ "$2" = "python3-poetry" ] && exit 0
    exit 1
    ;;
esac
exit 1
""")
        _write_stub(stub_dir, "sudo", f'echo "sudo $*" >> "{log_file}"')
        _write_stub(stub_dir, "apt-get", f'echo "apt-get $*" >> "{log_file}"')

    def test_apt_removal_uses_passed_path_over_command_v(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stub_dir = Path(tmpdir)
            log_file = stub_dir / "calls.log"
            log_file.touch()
            self._apt_stubs(stub_dir, log_file)
            # Decoy: command -v poetry resolves to this stub-dir binary,
            # which dpkg does NOT know. Only the passed path works.
            _write_stub(stub_dir, "poetry", "echo decoy")

            result = self._run_with_stubs(stub_dir, """
remove_installation "poetry" "apt" "poetry" "/usr/bin/poetry"
""")
            assert result.returncode == 0, result.stderr
            log = log_file.read_text()
            assert "dpkg -S /usr/bin/poetry" in log
            assert "apt-get remove -y python3-poetry" in log

    def test_apt_removal_falls_back_to_command_v_without_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stub_dir = Path(tmpdir)
            log_file = stub_dir / "calls.log"
            log_file.touch()
            self._apt_stubs(stub_dir, log_file)

            result = self._run_with_stubs(stub_dir, f"""
cat > "{stub_dir}/poetry" <<'EOF'
#!/usr/bin/env bash
echo decoy
EOF
chmod +x "{stub_dir}/poetry"
hash -r
remove_installation "poetry" "apt" "poetry"
""")
            # Falls back to command -v; the decoy path is unknown to dpkg,
            # so nothing is removed — but it must not crash.
            assert result.returncode == 0, result.stderr

    def test_manual_removal_uses_passed_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stub_dir = Path(tmpdir)
            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            decoy = _write_stub(stub_dir, "sometool", "echo decoy")
            target = _write_stub(target_dir, "sometool", "echo real")

            result = self._run_with_stubs(stub_dir, f"""
remove_installation "sometool" "manual" "sometool" "{target}"
""")
            assert result.returncode == 0, result.stderr
            assert not target.exists(), "passed-path binary should be removed"
            assert decoy.exists(), "PATH decoy must be untouched"
