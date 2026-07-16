"""Tests for auto_update.sh run_cmd: hidden-prompt protection, slow-command
notice, and failure output.

`composer global update` hung for hours inside `make upgrade-managed`: run_cmd
discarded stdout/stderr but left stdin attached to the terminal, so composer's
interactive prompt was invisible and waited forever. run_cmd must detach stdin,
announce long-running commands, and surface output of failed commands.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason="Shell script tests require POSIX shell"
)

SCRIPT = Path(__file__).parent.parent / "scripts" / "auto_update.sh"


def _run_cmd(bash_code: str, timeout: int = 15) -> subprocess.CompletedProcess:
    """Extract log()/run_cmd() from auto_update.sh (sourcing it would execute
    its CLI dispatch) and run bash_code against them."""
    full_code = f"""
set -euo pipefail
DRY_RUN=0
VERBOSE=0
SLOW_SECS="${{SLOW_SECS:-10}}"
TAIL_LINES="${{TAIL_LINES:-5}}"
eval "$(sed -n '/^log()/,/^}}/p' "{SCRIPT}")"
eval "$(sed -n '/^run_cmd()/,/^}}/p' "{SCRIPT}")"
{bash_code}
"""
    return subprocess.run(
        ["bash", "-c", full_code],
        capture_output=True, text=True, timeout=timeout,
        stdin=subprocess.PIPE,  # a held-open stdin, like an attached terminal
    )


@skip_on_windows
class TestRunCmdStdin:
    def _assert_completes_with_held_stdin(self, bash_code: str) -> None:
        """Run bash_code with a stdin pipe that stays OPEN (like an attached
        terminal). A run_cmd that leaks stdin makes `read` block forever."""
        full_code = f"""
set -euo pipefail
DRY_RUN=0
VERBOSE=0
SLOW_SECS=10
TAIL_LINES=5
eval "$(sed -n '/^log()/,/^}}/p' "{SCRIPT}")"
eval "$(sed -n '/^run_cmd()/,/^}}/p' "{SCRIPT}")"
{bash_code}
"""
        proc = subprocess.Popen(
            ["bash", "-c", full_code],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("run_cmd blocked on the caller's stdin (composer hang)")
        finally:
            if proc.stdin:
                proc.stdin.close()
        assert proc.returncode == 0

    def test_command_reading_stdin_does_not_hang(self):
        """A hidden interactive prompt must hit EOF instead of blocking on the
        caller's terminal (the composer hang)."""
        self._assert_completes_with_held_stdin(
            'run_cmd "Prompting tool" bash -c \'read -r answer; echo done\''
        )

    def test_verbose_mode_also_detaches_stdin(self):
        self._assert_completes_with_held_stdin(
            'VERBOSE=1\n'
            'run_cmd "Prompting tool" bash -c \'read -r answer\' || true'
        )


@skip_on_windows
class TestRunCmdSlowNotice:
    def test_slow_command_prints_actual_command(self):
        result = _run_cmd("""
SLOW_SECS=1
run_cmd "Slow step" sleep 3
""")
        assert "sleep 3" in result.stderr, (
            f"slow-command notice must show the real command: {result.stderr}"
        )

    def test_fast_command_stays_quiet(self):
        result = _run_cmd("""
SLOW_SECS=2
run_cmd "Fast step" true
""")
        assert "running" not in result.stderr.lower().replace(
            "[auto-update]", ""
        ).replace("fast step", "")
        assert "true" not in [
            line.strip() for line in result.stderr.splitlines()
        ]


@skip_on_windows
class TestRunCmdFailureOutput:
    def test_failed_command_surfaces_output_and_exit_code(self):
        result = _run_cmd("""
run_cmd "Broken step" bash -c 'echo boom-stdout; echo boom-stderr >&2; exit 3'
echo "SCRIPT_CONTINUED"
""")
        # failures stay non-fatal (legacy || true semantics) ...
        assert "SCRIPT_CONTINUED" in result.stdout
        # ... but are no longer silent
        assert "exit 3" in result.stderr
        assert "boom-stdout" in result.stderr
        assert "boom-stderr" in result.stderr

    def test_successful_command_output_stays_quiet(self):
        result = _run_cmd("""
run_cmd "Chatty step" bash -c 'echo lots-of-noise'
""")
        assert "lots-of-noise" not in result.stderr
        assert "lots-of-noise" not in result.stdout


@skip_on_windows
class TestRunCmdDryRun:
    def test_dry_run_prints_command_without_running(self):
        result = _run_cmd("""
DRY_RUN=1
marker="$(mktemp -u)"
run_cmd "Dry step" touch "$marker"
[ ! -e "$marker" ] && echo "NOT_EXECUTED"
""")
        assert "NOT_EXECUTED" in result.stdout
        assert "touch" in result.stderr
