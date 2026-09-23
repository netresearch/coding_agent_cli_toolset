"""The plugin hook that points a command-not-found failure at the catalog.

The hook input shapes follow the Claude Code hooks reference: PostToolUseFailure
carries the failure text in ``error``, PostToolUse carries ``tool_response``
with ``stdout``/``stderr``, and only ``hookSpecificOutput.additionalContext``
reaches the model.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "detect_missing_tool.py"

spec = importlib.util.spec_from_file_location("detect_missing_tool", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")


def _failure(text: str) -> dict:
    return {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "error": f"Exit code 127\n{text}"}


def _run_hook(event: dict | str) -> subprocess.CompletedProcess:
    data = event if isinstance(event, str) else json.dumps(event)
    return subprocess.run([sys.executable, str(SCRIPT)], input=data, capture_output=True, text=True)


class TestMessageForms:
    @pytest.mark.parametrize(
        "line",
        [
            "/bin/bash: line 1: zzq: command not found",
            "bash: zzq: command not found",
            "zsh: command not found: zzq",
            "(eval):1: command not found: zzq",
            "sh: 1: zzq: not found",
        ],
    )
    def test_shell_forms_name_the_command(self, line):
        assert hook.missing_commands(f"some output\n{line}\nmore") == ["zzq"]

    @pytest.mark.parametrize(
        "text",
        [
            "bash: line 1: ./zzq: No such file or directory",
            "see the 'command not found' section of the docs",
            "grep: zzq: No such file or directory",
        ],
    )
    def test_other_failures_are_ignored(self, text):
        assert hook.missing_commands(text) == []

    @skip_on_windows
    @pytest.mark.parametrize("shell", ["bash", "sh", "zsh"])
    def test_real_shell_output(self, shell):
        if shutil.which(shell) is None:
            pytest.skip(f"{shell} not installed")
        proc = subprocess.run([shell, "-c", "zzq-not-a-command --version"], capture_output=True, text=True)
        assert proc.returncode == 127
        assert hook.missing_commands(proc.stderr) == ["zzq-not-a-command"], proc.stderr


class TestContext:
    def test_failure_names_the_catalog_entry_and_the_installer(self):
        context = hook.context_for(_failure("/bin/bash: line 1: rg: command not found"))
        assert "catalog entry `ripgrep`" in context
        assert f"{PROJECT_ROOT / 'scripts' / 'install_tool.sh'} ripgrep install" in context

    def test_says_what_it_knows_not_what_it_infers(self):
        # A shell reports "not found on PATH"; the tool may still be installed
        # somewhere else, which is why the advice checks `type -P -a` first.
        context = hook.context_for(_failure("bash: rg: command not found"))
        assert "not found on PATH" in context
        assert "not installed" not in context

    def test_uncataloged_command_says_so(self):
        context = hook.context_for(_failure("bash: zzq: command not found"))
        assert "no entry in the cli-tools catalog" in context

    def test_post_tool_use_reads_stderr_only(self):
        event = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_response": {"stdout": "bash: rg: command not found", "stderr": ""},
        }
        assert hook.context_for(event) is None
        event["tool_response"] = {"stdout": "", "stderr": "bash: rg: command not found"}
        assert "ripgrep" in hook.context_for(event)

    def test_other_tools_are_ignored(self):
        event = _failure("bash: rg: command not found") | {"tool_name": "Read"}
        assert hook.context_for(event) is None


class TestMain:
    def test_emits_additional_context_for_the_event(self):
        proc = _run_hook(_failure("bash: rg: command not found"))
        assert proc.returncode == 0
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        assert out["hookEventName"] == "PostToolUseFailure"
        assert "ripgrep" in out["additionalContext"]

    @pytest.mark.parametrize("data", ["not json", "{}", json.dumps(_failure("all fine"))])
    def test_prints_nothing_and_exits_zero_otherwise(self, data):
        proc = _run_hook(data)
        assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", "")


class TestRegistration:
    def test_both_events_run_the_script(self):
        config = json.loads((PROJECT_ROOT / "hooks" / "hooks.json").read_text())["hooks"]
        for event in ("PostToolUseFailure", "PostToolUse"):
            (entry,) = config[event]
            assert entry["matcher"] == "Bash"
            (command,) = entry["hooks"]
            assert command["command"] == 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect_missing_tool.py"'
        assert SCRIPT.is_file()
