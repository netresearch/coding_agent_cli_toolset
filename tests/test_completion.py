"""Tests for the catalog-driven bash-completion framework.

Exercises scripts/lib/completion.sh directly (sourced in a subshell) against a
fixture catalog (CLI_AUDIT_CATALOG_DIR) and a temp XDG_DATA_HOME. No network and
no real tool execution: completion "commands" are plain `printf` snippets.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIB = PROJECT_ROOT / "scripts" / "lib" / "completion.sh"

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")


def _write_catalog(catalog_dir: Path, name: str, entry: dict) -> None:
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / f"{name}.json").write_text(json.dumps(entry))


def _run(catalog_dir: Path, xdg: Path, home: Path, snippet: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "CLI_AUDIT_CATALOG_DIR": str(catalog_dir),
        "XDG_DATA_HOME": str(xdg),
        "HOME": str(home),
    }
    return subprocess.run(
        ["bash", "-c", f'source "{LIB}"\n{snippet}'],
        capture_output=True,
        text=True,
        env=env,
    )


def _completions_path(xdg: Path, name: str) -> Path:
    return xdg / "bash-completion" / "completions" / name


@skip_on_windows
class TestInstallCompletion:
    def test_command_shape_installs_named_by_binary(self, tmp_path):
        catalog = tmp_path / "catalog"
        _write_catalog(
            catalog,
            "faketool",
            {
                "name": "faketool",
                "binary_name": "ft",
                "bash_completion": {"command": "printf 'complete -F _ft ft\\n'"},
            },
        )
        xdg = tmp_path / "xdg"
        proc = _run(catalog, xdg, tmp_path, "install_completion faketool")
        assert proc.returncode == 0, proc.stderr
        # File must be named after the COMMAND (binary_name), not the tool.
        target = _completions_path(xdg, "ft")
        assert target.exists()
        assert "complete -F _ft ft" in target.read_text()
        assert not _completions_path(xdg, "faketool").exists()

    def test_source_path_shape(self, tmp_path):
        clone = tmp_path / "clone"
        (clone / "shell").mkdir(parents=True)
        (clone / "shell" / "comp.bash").write_text("complete -F _s s\n")
        catalog = tmp_path / "catalog"
        _write_catalog(
            catalog,
            "srctool",
            {
                "name": "srctool",
                "binary_name": "s",
                "clone_path": str(clone),
                "bash_completion": {"source_path": "shell/comp.bash"},
            },
        )
        xdg = tmp_path / "xdg"
        proc = _run(catalog, xdg, tmp_path, "install_completion srctool")
        assert proc.returncode == 0, proc.stderr
        assert _completions_path(xdg, "s").read_text() == "complete -F _s s\n"

    def test_no_bash_completion_is_noop(self, tmp_path):
        catalog = tmp_path / "catalog"
        _write_catalog(catalog, "plain", {"name": "plain", "binary_name": "plain"})
        xdg = tmp_path / "xdg"
        proc = _run(catalog, xdg, tmp_path, "install_completion plain; echo rc=$?")
        assert proc.returncode == 0, proc.stderr
        assert "rc=0" in proc.stdout
        assert not _completions_path(xdg, "plain").exists()

    def test_unknown_tool_is_noop(self, tmp_path):
        catalog = tmp_path / "catalog"
        catalog.mkdir()
        xdg = tmp_path / "xdg"
        proc = _run(catalog, xdg, tmp_path, "install_completion ghost; echo rc=$?")
        assert proc.returncode == 0, proc.stderr
        assert "rc=0" in proc.stdout

    def test_garbage_output_is_rejected(self, tmp_path):
        catalog = tmp_path / "catalog"
        _write_catalog(
            catalog,
            "badtool",
            {
                "name": "badtool",
                "binary_name": "bad",
                "bash_completion": {"command": "printf 'usage: bad [opts]\\n'"},
            },
        )
        xdg = tmp_path / "xdg"
        proc = _run(catalog, xdg, tmp_path, "install_completion badtool; echo rc=$?")
        # Non-completion output must not be written.
        assert not _completions_path(xdg, "bad").exists()
        assert "rc=1" in proc.stdout

    def test_empty_output_is_rejected(self, tmp_path):
        catalog = tmp_path / "catalog"
        _write_catalog(
            catalog,
            "emptytool",
            {
                "name": "emptytool",
                "binary_name": "et",
                "bash_completion": {"command": "true"},
            },
        )
        xdg = tmp_path / "xdg"
        proc = _run(catalog, xdg, tmp_path, "install_completion emptytool; echo rc=$?")
        assert not _completions_path(xdg, "et").exists()
        assert "rc=1" in proc.stdout


@skip_on_windows
class TestRemoveCompletion:
    def test_remove_deletes_installed_file(self, tmp_path):
        catalog = tmp_path / "catalog"
        _write_catalog(
            catalog,
            "faketool",
            {
                "name": "faketool",
                "binary_name": "ft",
                "bash_completion": {"command": "printf 'complete -F _ft ft\\n'"},
            },
        )
        xdg = tmp_path / "xdg"
        _run(catalog, xdg, tmp_path, "install_completion faketool")
        assert _completions_path(xdg, "ft").exists()
        proc = _run(catalog, xdg, tmp_path, "remove_completion faketool")
        assert proc.returncode == 0, proc.stderr
        assert not _completions_path(xdg, "ft").exists()

    def test_remove_missing_is_noop(self, tmp_path):
        catalog = tmp_path / "catalog"
        _write_catalog(
            catalog,
            "faketool",
            {"name": "faketool", "binary_name": "ft", "bash_completion": {"command": "true"}},
        )
        xdg = tmp_path / "xdg"
        proc = _run(catalog, xdg, tmp_path, "remove_completion faketool; echo rc=$?")
        assert "rc=0" in proc.stdout


@skip_on_windows
class TestRobustness:
    """Regressions for defects found in adversarial review of #121."""

    def test_unknown_tool_via_wrapper_under_set_e_exits_zero(self, tmp_path):
        # _completion_catalog_file used to return 1 for a missing catalog, which
        # aborted the `set -euo pipefail` wrapper before its own no-op guard.
        catalog = tmp_path / "catalog"
        catalog.mkdir()
        env = {
            **os.environ,
            "CLI_AUDIT_CATALOG_DIR": str(catalog),
            "XDG_DATA_HOME": str(tmp_path / "xdg"),
            "HOME": str(tmp_path),
        }
        proc = subprocess.run(
            ["bash", str(WRAPPER), "ghost", "install"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"

    def test_unwritable_target_reports_failure_and_leaks_no_tempfile(self, tmp_path):
        # mkdir/mv were unchecked, so a failed install still echoed "installed"
        # and returned 0, leaving the temp file behind.
        catalog = tmp_path / "catalog"
        _write_catalog(
            catalog,
            "g",
            {"name": "g", "binary_name": "g", "bash_completion": {"command": "printf 'complete -F _g g\\n'"}},
        )
        blocked = tmp_path / "blocked"
        blocked.mkdir()
        blocked.chmod(0o500)
        tmpdir = tmp_path / "tmp"
        tmpdir.mkdir()
        env = {
            **os.environ,
            "CLI_AUDIT_CATALOG_DIR": str(catalog),
            "XDG_DATA_HOME": str(blocked / "sub"),
            "HOME": str(tmp_path),
            "TMPDIR": str(tmpdir),
        }
        proc = subprocess.run(
            ["bash", "-c", f'source "{LIB}"\ninstall_completion g; echo rc=$?'],
            capture_output=True,
            text=True,
            env=env,
        )
        blocked.chmod(0o700)
        assert "rc=1" in proc.stdout
        assert "installed completion" not in proc.stderr
        assert list(tmpdir.iterdir()) == [], "temp file leaked"

    def test_generator_reading_stdin_does_not_hang(self, tmp_path):
        # stdin is now detached and the run bounded; `cat` used to block forever.
        catalog = tmp_path / "catalog"
        _write_catalog(
            catalog,
            "h",
            {"name": "h", "binary_name": "h", "bash_completion": {"command": "cat"}},
        )
        env = {
            **os.environ,
            "CLI_AUDIT_CATALOG_DIR": str(catalog),
            "XDG_DATA_HOME": str(tmp_path / "xdg"),
            "HOME": str(tmp_path),
        }
        proc = subprocess.run(
            ["bash", "-c", f'source "{LIB}"\ninstall_completion h'],
            capture_output=True,
            text=True,
            env=env,
            stdin=subprocess.PIPE,
            timeout=30,
        )
        assert proc.returncode == 1

    def test_framework_block_is_guarded_for_non_interactive_shells(self, tmp_path):
        # The distro bash_completion enables extglob/progcomp at top level and
        # has no guard of its own; sourcing it non-interactively changes glob
        # semantics for scripts (e.g. `ssh host somescript`).
        env = {**os.environ, "HOME": str(tmp_path)}
        subprocess.run(
            ["bash", "-c", f'source "{LIB}"\nensure_bash_completion_framework'],
            capture_output=True,
            text=True,
            env=env,
        )
        bashrc = tmp_path / ".bashrc"
        if not bashrc.exists():
            pytest.skip("framework not available in this environment")
        assert "$- == *i*" in bashrc.read_text()
        proc = subprocess.run(
            ["bash", "-c", 'source "$HOME/.bashrc" 2>/dev/null; shopt extglob'],
            capture_output=True,
            text=True,
            env=env,
        )
        assert "off" in proc.stdout, "non-interactive shell got extglob enabled"


@skip_on_windows
class TestBashrcLib:
    """Direct coverage for the shared managed-block primitives."""

    BASHRC_LIB = PROJECT_ROOT / "scripts" / "lib" / "bashrc.sh"

    def _run(self, home, snippet):
        return subprocess.run(
            ["bash", "-c", f'source "{self.BASHRC_LIB}"\n{snippet}'],
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(home)},
        )

    def test_ensure_is_idempotent(self, tmp_path):
        rc = tmp_path / "rc"
        proc = self._run(
            tmp_path,
            f'bashrc_ensure_block "{rc}" demo "X"; bashrc_ensure_block "{rc}" demo "X"; '
            f'grep -c ">>> cli-audit: demo >>>" "{rc}"',
        )
        assert proc.stdout.strip().splitlines()[-1] == "1"

    def test_remove_preserves_surrounding_content(self, tmp_path):
        rc = tmp_path / "rc"
        rc.write_text("before\nafter\n")
        proc = self._run(
            tmp_path,
            f'bashrc_ensure_block "{rc}" demo "X"; bashrc_remove_block "{rc}" demo; cat "{rc}"',
        )
        assert "before" in proc.stdout and "after" in proc.stdout
        assert "cli-audit" not in proc.stdout

    def test_remove_restores_unbalanced_block_intact(self, tmp_path):
        rc = tmp_path / "rc"
        rc.write_text("keepA\n# >>> cli-audit: demo >>>\norphan\nkeepB\n")
        proc = self._run(tmp_path, f'bashrc_remove_block "{rc}" demo; cat "{rc}"')
        assert "keepA" in proc.stdout and "keepB" in proc.stdout


class TestRealCatalogSchema:
    """Invariants over the shipped catalog's bash_completion declarations."""

    def _entries(self):
        for f in sorted((PROJECT_ROOT / "catalog").glob("*.json")):
            data = json.loads(f.read_text())
            if "bash_completion" in data:
                yield f.stem, data

    def test_declarations_have_exactly_one_shape(self):
        for tool, data in self._entries():
            bc = data["bash_completion"]
            assert isinstance(bc, dict), f"{tool}: bash_completion must be an object"
            keys = set(bc) & {"command", "source_path"}
            assert len(keys) == 1, f"{tool}: need exactly one of command|source_path, got {sorted(bc)}"
            assert bc[keys.pop()], f"{tool}: bash_completion value must be non-empty"

    def test_source_path_entries_have_clone_path(self):
        for tool, data in self._entries():
            if "source_path" in data["bash_completion"]:
                assert data.get("clone_path"), f"{tool}: source_path requires clone_path"

    def test_no_two_declarations_share_a_binary_name(self):
        # The completion file is named after binary_name, so two declaring
        # entries with the same binary_name would silently overwrite each other
        # (e.g. the `compose` entry has binary_name "docker").
        seen: dict[str, str] = {}
        for tool, data in self._entries():
            binary = data.get("binary_name") or tool
            assert binary not in seen, f"{tool} and {seen[binary]} both declare bash_completion for binary '{binary}'"
            seen[binary] = tool


WRAPPER = PROJECT_ROOT / "scripts" / "install_completion.sh"


@skip_on_windows
class TestWrapperCli:
    def _run_wrapper(self, catalog, xdg, home, *args):
        env = {
            **os.environ,
            "CLI_AUDIT_CATALOG_DIR": str(catalog),
            "XDG_DATA_HOME": str(xdg),
            "HOME": str(home),
        }
        return subprocess.run(
            ["bash", str(WRAPPER), *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_no_args_prints_usage(self, tmp_path):
        proc = self._run_wrapper(tmp_path / "catalog", tmp_path / "xdg", tmp_path)
        assert proc.returncode == 1
        assert "Usage" in proc.stderr

    def test_all_backfills_only_declared_and_valid(self, tmp_path):
        catalog = tmp_path / "catalog"
        _write_catalog(
            catalog,
            "faketool",
            {
                "name": "faketool",
                "binary_name": "ft",
                "bash_completion": {"command": "printf 'complete -F _ft ft\\n'"},
            },
        )
        _write_catalog(catalog, "plain", {"name": "plain", "binary_name": "plain"})
        xdg = tmp_path / "xdg"
        proc = self._run_wrapper(catalog, xdg, tmp_path, "--all")
        assert proc.returncode == 0, proc.stderr
        assert _completions_path(xdg, "ft").exists()
        assert not _completions_path(xdg, "plain").exists()
        assert "1 installed" in proc.stdout
