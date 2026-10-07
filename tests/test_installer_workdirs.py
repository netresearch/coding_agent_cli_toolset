# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""Where installers keep downloaded files before installing or running them.

Each run downloads into a directory that ``mktemp -d`` creates for it under
``$TMPDIR`` (mode 0700) and removes afterwards. The stubs below record the path
a file was downloaded to, or run from, together with the mode of its directory.
"""

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="the installers and the stubs use GNU coreutils (stat -c)"
)

RECORD = 'printf "%s %s\\n" "$1" "$(stat -c %a "$(dirname "$1")")" >> "$LOG"\n'


def _write_exe(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def box(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    log = tmp_path / "paths.log"
    env = {
        "HOME": str(home),
        "TMPDIR": str(scratch),
        "PATH": os.pathsep.join([str(stubs), os.environ["PATH"]]),
        "LOG": str(log),
        "USER": "tester",
    }
    return env, stubs, scratch, log


def _recorded(log: Path) -> list[tuple[str, str]]:
    return [tuple(line.split()) for line in log.read_text().splitlines()] if log.exists() else []


def _assert_private(records, scratch: Path, context: str) -> None:
    assert records, context
    for path, mode in records:
        assert Path(path).parent.parent == scratch, f"{path} is not in a directory of its own under TMPDIR\n{context}"
        assert mode == "700", f"directory of {path} has mode {mode}\n{context}"
    assert list(scratch.iterdir()) == [], f"the run left its working directory behind\n{context}"


def _curl_writing(content: str) -> str:
    """A curl stub that writes ``content`` to its -o target and records the target."""
    return (
        'out=""; prev=""\n'
        'for a in "$@"; do [ "$prev" = "-o" ] && out="$a"; prev="$a"; done\n'
        'case "$*" in *-w*) printf "%s" "https://github.com/docker/compose/releases/tag/v9.9.9"; exit 0 ;; esac\n'
        '[ -n "$out" ] || exit 22\n'
        'set -- "$out"\n' + RECORD + f"cat > \"$out\" <<'STUB'\n{content}\nSTUB\n"
    )


def test_docker_plugin_downloads_into_a_private_directory(box):
    env, stubs, scratch, log = box
    _write_exe(stubs / "curl", _curl_writing("#!/bin/sh\necho compose"))
    _write_exe(stubs / "docker", "exit 0\n")

    proc = subprocess.run(
        ["bash", str(SCRIPTS / "installers" / "docker_plugin.sh"), "compose"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    _assert_private(_recorded(log), scratch, proc.stdout + proc.stderr)
    assert (Path(env["HOME"]) / ".docker" / "cli-plugins" / "docker-compose").exists(), proc.stdout + proc.stderr


def test_docker_convenience_script_runs_from_a_private_directory(box):
    env, stubs, scratch, log = box
    _write_exe(stubs / "curl", _curl_writing("echo get-docker; sleep 20"))
    # is_wsl() greps /proc/version; answer "yes" for that one call only.
    _write_exe(stubs / "grep", 'case "$*" in *"/proc/version"*) exit 0 ;; esac\nexec /usr/bin/grep "$@"\n')
    _write_exe(stubs / "apt-get", "exit 0\n")
    _write_exe(stubs / "dpkg", "exit 1\n")
    _write_exe(stubs / "sudo", 'if [ "$1" = sh ]; then set -- "$2"; ' + RECORD.strip() + "; fi\nexit 0\n")

    proc = subprocess.run(
        ["bash", str(SCRIPTS / "install_docker.sh"), "install"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    _assert_private(_recorded(log), scratch, proc.stdout + proc.stderr)


def test_claude_native_installer_runs_from_a_private_directory(box):
    env, stubs, scratch, log = box
    _write_exe(stubs / "curl", _curl_writing('set -- "$0"\n' + RECORD))

    proc = subprocess.run(
        ["bash", "-c", f'source "{SCRIPTS / "install_claude.sh"}"; install_native'],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    _assert_private(_recorded(log), scratch, proc.stdout + proc.stderr)
