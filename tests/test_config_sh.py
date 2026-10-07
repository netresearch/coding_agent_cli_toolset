# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""scripts/lib/config.sh — the bash bridge to the Python configuration.

``guide.sh`` asks ``config_get_auto_update`` about keys such as
``python@3.13``, whose cycle part comes from endoflife.date data. The key has to
reach ``Config.is_auto_update_enabled`` as a plain string, whatever characters
it contains.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_SH = PROJECT_ROOT / "scripts" / "lib" / "config.sh"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")


def _ask(tmp_path: Path, func: str, *args: str) -> str:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    proc = subprocess.run(
        ["bash", "-c", f'source "{CONFIG_SH}"; {func} "$@"', "_", *args],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={"HOME": str(home), "PATH": os.environ["PATH"]},
        timeout=60,
    )
    return proc.stdout.strip()


def _write_config(tmp_path: Path, body: str) -> None:
    cfg = tmp_path / "home" / ".config" / "cli-audit" / "config.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(body)


def test_per_cycle_key_is_looked_up(tmp_path):
    _write_config(
        tmp_path,
        "preferences:\n  auto_upgrade: false\ntools:\n  python@3.13:\n    auto_update: true\n",
    )
    assert _ask(tmp_path, "config_get_auto_update", "python@3.13") == "true"
    assert _ask(tmp_path, "config_get_auto_update", "python@3.12") == "false"


def test_key_with_quotes_and_parentheses_is_treated_as_a_name(tmp_path):
    marker = tmp_path / "marker"
    key = f"python@3') or open('{marker}', 'w').write('x') or ('"
    _write_config(tmp_path, "preferences:\n  auto_upgrade: false\n")

    answer = _ask(tmp_path, "config_get_auto_update", key)

    assert answer == "false"
    assert not marker.exists(), "the key was evaluated as Python instead of being looked up"


def test_global_auto_upgrade_is_read(tmp_path):
    _write_config(tmp_path, "preferences:\n  auto_upgrade: false\n")
    assert _ask(tmp_path, "config_get_global_auto_upgrade") == "false"


SET_AUTO_UPDATE = PROJECT_ROOT / "scripts" / "set_auto_update.sh"


def _set(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return subprocess.run(
        ["bash", str(SET_AUTO_UPDATE), *args],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={"HOME": str(home), "PATH": os.environ["PATH"]},
        timeout=60,
    )


def test_set_auto_update_writes_the_key_and_the_reader_finds_it(tmp_path):
    _write_config(tmp_path, "preferences:\n  auto_upgrade: false\n")
    proc = _set(tmp_path, "python@3.13", "true")
    assert proc.returncode == 0, proc.stderr
    assert _ask(tmp_path, "config_get_auto_update", "python@3.13") == "true"

    proc = _set(tmp_path, "python@3.13", "false")
    assert proc.returncode == 0, proc.stderr
    assert _ask(tmp_path, "config_get_auto_update", "python@3.13") == "false"


def test_set_auto_update_stores_a_key_with_quotes_as_written(tmp_path):
    import yaml

    marker = tmp_path / "marker"
    key = f"python@3\"+__import__('os').system('touch {marker}')+\""

    proc = _set(tmp_path, key, "true")

    assert proc.returncode == 0, proc.stderr
    assert not marker.exists(), "the key was evaluated as Python instead of being stored"
    cfg = yaml.safe_load((tmp_path / "home" / ".config" / "cli-audit" / "config.yml").read_text())
    assert cfg["tools"][key] == {"auto_update": True}
