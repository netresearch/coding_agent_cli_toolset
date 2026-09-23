#!/usr/bin/env python3
"""Claude Code hook: point a failed command at the cli-tools catalog.

Registered in hooks/hooks.json for PostToolUseFailure and PostToolUse on Bash.
A command that is not installed makes the shell print a "command not found"
line; this hook finds it, looks the binary up in catalog/*.json and adds the
install command to Claude's context.

- PostToolUseFailure carries the text in ``error`` ("Exit code 127" and then
  the command's interleaved output). A missing command usually ends up here.
- PostToolUse carries ``tool_response.stderr``; it matters when the failing
  command is not the last one in a pipeline or list, so the call as a whole
  still succeeded.

Plain stdout from these events never reaches the model; the text has to go
into ``hookSpecificOutput.additionalContext``. Standard library only, and any
failure is silent: a hook must never break the tool call it observes.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The forms shells print, one per line:
#   bash: line 1: rg: command not found      /bin/bash: rg: command not found
#   zsh: command not found: rg               (eval):1: command not found: rg
#   sh: 1: rg: not found                     (dash)
_NAME = r"(?P<name>[A-Za-z0-9][A-Za-z0-9._+-]*)"
PATTERNS = [
    re.compile(rf"^\S*sh(?:: line \d+)?: {_NAME}: command not found$", re.M),
    re.compile(rf"command not found: {_NAME}$", re.M),
    re.compile(rf"^\S*sh: \d+: {_NAME}: not found$", re.M),
]


def missing_commands(text: str) -> list[str]:
    """Command names the shell reported as not found, in order, de-duplicated."""
    found: list[str] = []
    for pattern in PATTERNS:
        for match in pattern.finditer(text):
            if match.group("name") not in found:
                found.append(match.group("name"))
    return found


def catalog_entry(binary: str, catalog: Path) -> str | None:
    """The catalog entry that provides ``binary``, or None."""
    if (catalog / f"{binary}.json").is_file():
        return binary
    for path in sorted(catalog.glob("*.json")):
        try:
            if json.loads(path.read_text()).get("binary_name") == binary:
                return path.stem
        except (OSError, ValueError, AttributeError):
            continue
    return None


def advice(binary: str, root: Path) -> str:
    entry = catalog_entry(binary, root / "catalog")
    if entry is None:
        return (
            f"`{binary}` is not installed and has no entry in the cli-tools catalog. "
            "Check `type -P -a` and `hash -r` first; the cli-tools skill lists alternatives "
            "and troubleshooting."
        )
    install = root / "scripts" / "install_tool.sh"
    via = "" if entry == binary else f" (provided by catalog entry `{entry}`)"
    return (
        f"`{binary}` is not installed{via}. Check `type -P -a {binary}` and `hash -r` first "
        f"in case it is only off PATH; otherwise install it with `{install} {entry} install`. "
        "The cli-tools skill covers the rest of the workflow."
    )


def context_for(event: dict, root: Path = ROOT) -> str | None:
    if event.get("tool_name") != "Bash":
        return None
    name = event.get("hook_event_name")
    if name == "PostToolUseFailure":
        text = event.get("error") or ""
    elif name == "PostToolUse":
        response = event.get("tool_response") or {}
        text = (response.get("stderr") or "") if isinstance(response, dict) else ""
    else:
        return None
    binaries = missing_commands(text)
    if not binaries:
        return None
    return "\n".join(advice(b, root) for b in binaries)


def main() -> int:
    try:
        event = json.load(sys.stdin)
        context = context_for(event)
    except Exception:  # noqa: BLE001 - a hook must fail open
        return 0
    if context:
        json.dump(
            {"hookSpecificOutput": {"hookEventName": event["hook_event_name"], "additionalContext": context}},
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
