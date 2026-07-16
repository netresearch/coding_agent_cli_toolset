"""Tests for reconcile venv exclusion and prompt serialization.

`make reconcile-all` flagged binaries inside an activated virtualenv
(~/.venv/bin/black) as duplicate installations, classified them as `uv`
(black appears in `uv tool list` — a different install), and then removed
the real uv tool instead of the displayed venv path. Virtualenvs are
environments, not installations — the shell layer (capability.sh) already
skips them; detection here must too.

Additionally, bulk_reconcile prompts from ThreadPool workers interleaved:
all confirmation prompts printed at once before any input was consumed.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Uses Unix-style paths and PATH separator (:)"
)

from cli_audit.reconcile import (  # noqa: E402
    _confirm_removal,
    clear_detection_cache,
    detect_installations,
)


def _make_bin(bin_dir: Path, name: str) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    binary = bin_dir / name
    binary.write_text("#!/bin/sh\necho 'faketool 1.0.0'\n")
    binary.chmod(0o755)
    return binary


@skip_on_windows
class TestDetectSkipsVirtualenvs:
    def _detect(self, monkeypatch, path_dirs: list[Path], tool: str):
        clear_detection_cache()
        monkeypatch.setenv("PATH", os.pathsep.join(str(d) for d in path_dirs))
        return detect_installations(tool)

    def test_dot_venv_bin_is_skipped(self, tmp_path, monkeypatch):
        venv_bin = tmp_path / ".venv" / "bin"
        _make_bin(venv_bin, "faketool_venv_a")
        (tmp_path / ".venv" / "pyvenv.cfg").write_text("home = /usr\n")
        plain_bin = tmp_path / "tools" / "bin"
        plain = _make_bin(plain_bin, "faketool_venv_a")

        installs = self._detect(monkeypatch, [venv_bin, plain_bin], "faketool_venv_a")
        paths = [i.path for i in installs]
        assert str(plain) in paths
        assert not any(".venv" in p for p in paths), (
            "virtualenv binaries are environments, not installations"
        )

    def test_pyvenv_cfg_detected_regardless_of_dir_name(self, tmp_path, monkeypatch):
        # A venv named anything (not just venv/.venv) carries pyvenv.cfg
        env_bin = tmp_path / "myproject-env" / "bin"
        _make_bin(env_bin, "faketool_venv_b")
        (tmp_path / "myproject-env" / "pyvenv.cfg").write_text("home = /usr\n")

        installs = self._detect(monkeypatch, [env_bin], "faketool_venv_b")
        assert installs == []

    def test_conda_env_bin_is_skipped_by_name(self, tmp_path, monkeypatch):
        conda_bin = tmp_path / "miniconda3" / "envs" / "dev" / "bin"
        _make_bin(conda_bin, "faketool_venv_c")

        installs = self._detect(monkeypatch, [conda_bin], "faketool_venv_c")
        assert installs == []

    def test_symlink_into_venv_is_skipped(self, tmp_path, monkeypatch):
        venv_bin = tmp_path / ".venv" / "bin"
        real = _make_bin(venv_bin, "faketool_venv_d")
        (tmp_path / ".venv" / "pyvenv.cfg").write_text("home = /usr\n")
        link_dir = tmp_path / "linkbin"
        link_dir.mkdir()
        (link_dir / "faketool_venv_d").symlink_to(real)

        installs = self._detect(monkeypatch, [link_dir], "faketool_venv_d")
        assert installs == []

    def test_non_venv_installs_still_detected(self, tmp_path, monkeypatch):
        bin_a = tmp_path / "a" / "bin"
        bin_b = tmp_path / "b" / "bin"
        _make_bin(bin_a, "faketool_venv_e")
        _make_bin(bin_b, "faketool_venv_e")

        installs = self._detect(monkeypatch, [bin_a, bin_b], "faketool_venv_e")
        assert len(installs) == 2


@skip_on_windows
class TestConfirmRemovalSerialized:
    def test_concurrent_prompts_do_not_interleave(self):
        """With bulk_reconcile's ThreadPool, every worker's prompt printed
        before any input was read. Prompts must be serialized: while one
        prompt awaits input, another thread's prompt must not appear."""
        from cli_audit.reconcile import Installation

        events: list[str] = []
        first_prompt_shown = threading.Event()
        release_first_input = threading.Event()

        def fake_print(*args, **kwargs):
            text = " ".join(str(a) for a in args)
            if "About to remove" in text:
                events.append(f"prompt:{threading.current_thread().name}")
                first_prompt_shown.set()

        def fake_input():
            events.append(f"input:{threading.current_thread().name}")
            release_first_input.wait(timeout=5)
            return "n"

        inst = Installation(
            tool="faketool", version="1.0", method="uv",
            path="/tmp/faketool", active=False, valid=True,
        )

        def worker():
            _confirm_removal("faketool", [inst])

        with patch("cli_audit.reconcile.sys.stdin") as stdin_mock, \
                patch("builtins.print", side_effect=fake_print), \
                patch("builtins.input", side_effect=fake_input):
            stdin_mock.isatty.return_value = True
            t1 = threading.Thread(target=worker, name="w1")
            t2 = threading.Thread(target=worker, name="w2")
            t1.start()
            first_prompt_shown.wait(timeout=5)
            t2.start()
            # give w2 a chance to (incorrectly) print its prompt while w1
            # still awaits input
            time.sleep(0.3)
            interleaved = [e for e in events if e.startswith("prompt")]
            release_first_input.set()
            t1.join(timeout=5)
            t2.join(timeout=5)

        assert len(interleaved) == 1, (
            f"second prompt appeared while first awaited input: {events}"
        )
        # both prompts eventually happened, strictly prompt->input->prompt->input
        kinds = [e.split(":")[0] for e in events]
        assert kinds == ["prompt", "input", "prompt", "input"], events
