"""scripts/lib/catalog_command.sh and common.sh::validate_package_list.

Two catalog fields are shell code stored as JSON strings -- ``version_command``
(28 entries) and ``bash_completion.command`` (41). Twelve places executed them: five
through ``eval`` and seven through ``bash -c``, none of them checking. These tests pin the shared helper that replaced them and
the package-name check that now runs before every package-manager install.

The helper deliberately does not try to parse shell. Every catalog entry is
legitimate shell -- 24 of 28 use pipes, one ``&&``, one ``$(command -v …)``,
one a ``;`` inside quoted awk -- so an allowlist of first words would reject
real tools while ``&&`` walks past it. It refuses only what no catalog entry
needs and a reviewer easily misses inside a JSON string: a newline and a
backtick. Both fields are repository code; review them as code.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
COMMON = SCRIPTS / "lib" / "common.sh"
CATALOG_COMMAND = SCRIPTS / "lib" / "catalog_command.sh"
CATALOG = PROJECT_ROOT / "catalog"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")


def _bash(snippet: str, env: dict | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", f'source "{COMMON}"\n{snippet}'],
        capture_output=True,
        text=True,
        env=env or dict(os.environ),
        timeout=timeout,
    )


def _catalog_entries():
    for path in sorted(CATALOG.glob("*.json")):
        yield path.stem, json.loads(path.read_text())


def _catalog_commands():
    """Every catalog command that a script executes: version_command (a string)
    and bash_completion.command (an object field, which completion.sh reads)."""
    for name, e in _catalog_entries():
        if e.get("version_command"):
            yield f"{name}.version_command", e["version_command"]
        completion = e.get("bash_completion") or {}
        if completion.get("command"):
            yield f"{name}.bash_completion.command", completion["command"]


CATALOG_COMMANDS = list(_catalog_commands())


class TestRunCatalogCommand:
    def test_prints_the_command_output(self):
        proc = _bash('run_catalog_command "echo 1.2.3 | head -1"')
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "1.2.3"

    @pytest.mark.parametrize("payload", ["echo 1.2.3\ntouch {marker}", "echo `touch {marker}`"])
    def test_refuses_newline_and_backtick_without_running_anything(self, tmp_path, payload):
        marker = tmp_path / "ran"
        cmd = payload.format(marker=marker)
        proc = _bash('run_catalog_command "$CMD"', env={**os.environ, "CMD": cmd})
        assert proc.returncode != 0
        assert not marker.exists(), "the refused command was executed"
        assert "Refusing catalog command" in proc.stderr

    def test_runs_in_a_subshell_and_cannot_clobber_caller_variables(self):
        proc = _bash('TOOL=keep; run_catalog_command "TOOL=clobbered; echo x" >/dev/null; echo "$TOOL"')
        assert proc.stdout.strip() == "keep"

    def test_a_path_prefix_on_the_call_reaches_the_command(self, tmp_path):
        fake = tmp_path / "zzfake-tool"
        fake.write_text("#!/bin/sh\necho 9.9.9\n")
        fake.chmod(0o755)
        proc = _bash(f'PATH="{tmp_path}:$PATH" run_catalog_command "zzfake-tool"')
        assert proc.stdout.strip() == "9.9.9", proc.stderr

    @pytest.mark.skipif(shutil.which("timeout") is None, reason="no timeout(1) on this host")
    def test_a_hanging_command_is_cut_off(self):
        start = time.monotonic()
        proc = _bash('run_catalog_command "sleep 20" 1')
        assert time.monotonic() - start < 10
        assert proc.returncode == 124, (proc.returncode, proc.stderr)

    @pytest.mark.parametrize("name,cmd", CATALOG_COMMANDS, ids=[n for n, _ in CATALOG_COMMANDS])
    def test_every_catalog_command_is_accepted(self, name, cmd):
        proc = _bash('catalog_command_is_safe "$CMD"', env={**os.environ, "CMD": cmd})
        assert proc.returncode == 0, f"{name}: catalog command would be refused: {cmd!r}"


def test_both_catalog_command_fields_are_collected():
    fields = {n.rsplit(".", 1)[-1] if n.endswith("version_command") else "bash_completion" for n, _ in CATALOG_COMMANDS}
    assert fields == {"version_command", "bash_completion"}, fields
    assert len(CATALOG_COMMANDS) >= 60, len(CATALOG_COMMANDS)


class TestNoUncheckedExecutionLeft:
    """Every catalog command goes through the helper."""

    def test_no_script_runs_a_catalog_command_directly(self):
        offenders = []
        # upgrade_all.sh's get_version evaluates the script's own literal strings
        # (apt-get, brew, snap, pip, uv version probes), never catalog data, and
        # needs the caller's shell functions -- it is deliberately left on eval.
        not_catalog = {CATALOG_COMMAND, SCRIPTS / "upgrade_all.sh"}
        for path in SCRIPTS.rglob("*.sh"):
            if path in not_catalog:
                continue
            for n, line in enumerate(path.read_text().splitlines(), 1):
                code = line.split("#", 1)[0]
                for var in ("VERSION_CMD", "VERSION_COMMAND", "version_cmd", "cmd"):
                    if f'eval "${var}' in code or f'bash -c "${var}' in code:
                        offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{n}: {line.strip()}")
        assert not offenders, "\n".join(offenders)


PACKAGE_NAMES = sorted(
    {
        word
        for _, e in _catalog_entries()
        for value in (e.get("packages") or e.get("package_managers") or {}).values()
        if isinstance(value, str)
        for word in value.split()
    }
)


class TestValidatePackageList:
    @pytest.mark.parametrize("pkgs", ["fd-find", "php8.3 php8.3-cli", "python3-pip", "g++", "lib/foo@1:2"])
    def test_accepts_real_package_names(self, pkgs):
        proc = _bash('validate_package_list "$P"', env={**os.environ, "P": pkgs})
        assert proc.returncode == 0, proc.stderr

    @pytest.mark.parametrize("pkgs", ["-y", "foo --allow-downgrades", "foo;touch x", "a$(b)", "*", "foo`x`"])
    def test_rejects_options_and_shell_syntax(self, pkgs):
        proc = _bash('validate_package_list "$P"', env={**os.environ, "P": pkgs})
        assert proc.returncode != 0
        assert "Invalid package name" in proc.stderr

    @pytest.mark.parametrize("name", PACKAGE_NAMES)
    def test_every_catalog_package_name_is_accepted(self, name):
        proc = _bash('validate_package_list "$P"', env={**os.environ, "P": name})
        assert proc.returncode == 0, f"catalog package name would be refused: {name!r}"

    def test_package_manager_validates_before_every_install_and_ends_options(self):
        src = (SCRIPTS / "installers" / "package_manager.sh").read_text()
        for invocation in ("apt-get install -y -- ", "dnf install -y -- ", "pacman -S --noconfirm -- "):
            assert invocation in src, f"missing option terminator: {invocation!r}"
        assert src.count("validate_package_list") >= 4, "brew, apt, dnf and pacman must each validate first"
