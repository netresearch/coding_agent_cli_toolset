"""
Local tool detection and version extraction.

Phase 2.0: Detection and Auditing - Local Detection
"""

import os
import re
import shutil
import subprocess
from typing import Sequence

# Constants
TIMEOUT_SECONDS = int(os.environ.get("CLI_AUDIT_TIMEOUT_SECONDS", "3"))
HOME = os.path.expanduser("~")
CARGO_BIN = os.path.join(HOME, ".cargo", "bin")

VERSION_RE = re.compile(r"(\d+(?:\.\d+)+)")
DATE_VERSION_RE = re.compile(r"\b(\d{8})\b")
ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*m|\033\[[0-9;]*m')

VERSION_FLAG_SETS = (
    ("-v",),
    ("--version",),
    ("-V",),
    ("version",),
)


def find_paths(command_name: str, deep: bool = False) -> list[str]:
    """Find all paths for a command.

    Args:
        command_name: Binary name to search for
        deep: If True, find all PATH matches (slower)

    Returns:
        List of absolute paths to executables
    """
    paths: list[str] = []

    # Fast path: shutil.which
    p = shutil.which(command_name)
    if p:
        paths.append(p)

    # Deep search: all PATH matches
    if deep:
        try:
            proc = subprocess.run(
                ["which", "-a", command_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,  # Isolate stdin
                text=True,
                timeout=0.2,
                check=False,
                env={**os.environ, "TERM": "dumb"},  # Disable ANSI output
            )
            for line in (proc.stdout or "").splitlines():
                line = line.strip()
                if line and os.path.isfile(line) and os.access(line, os.X_OK):
                    if line not in paths:
                        paths.append(line)
        except Exception:
            pass

    # Check cargo bin
    cargo_path = os.path.join(CARGO_BIN, command_name)
    if os.path.isfile(cargo_path) and os.access(cargo_path, os.X_OK):
        if cargo_path not in paths:
            paths.append(cargo_path)

    return paths


def run_with_timeout(args: Sequence[str], timeout: float | None = None, capture_stderr: bool = True) -> str:
    """Run command with timeout and return output with version info.

    Args:
        args: Command and arguments
        timeout: Timeout in seconds (default: TIMEOUT_SECONDS)
        capture_stderr: If True, merge stderr into stdout

    Returns:
        Line containing version, or first line if no version found
    """
    try:
        proc = subprocess.run(
            list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if capture_stderr else subprocess.PIPE,
            stdin=subprocess.DEVNULL,  # Isolate stdin
            text=True,
            timeout=timeout or TIMEOUT_SECONDS,
            check=False,
            env={**os.environ, "TERM": "dumb"},  # Disable ANSI/color output from subprocesses
        )
        output = proc.stdout or ""
        if not capture_stderr and proc.stderr:
            output = (proc.stderr or "") + "\n" + output

        lines = output.splitlines()
        if not lines:
            return ""

        # Strip ANSI escape sequences from all lines
        cleaned_lines = [ANSI_ESCAPE_RE.sub('', line.strip()) for line in lines]

        # Search for line containing version number (prefer this over first line)
        for line in cleaned_lines:
            if line and VERSION_RE.search(line):
                return line

        # Fallback: return first non-empty line
        for line in cleaned_lines:
            if line:
                return line

        return ""
    except Exception:
        return ""


def extract_version_number(s: str) -> str:
    """Extract version number from string.

    Args:
        s: String potentially containing version

    Returns:
        Version number (e.g., "1.2.3") or empty string
    """
    if not s:
        return ""

    # Standard semantic version
    m = VERSION_RE.search(s)
    if m:
        return m.group(1)

    # Fallback: date-like versions (GNU parallel 20231122)
    m2 = DATE_VERSION_RE.search(s)
    return m2.group(1) if m2 else ""


def get_version_line(path: str, tool_name: str, version_flag: str | None = None, version_command: str | None = None) -> str:
    """Get version string for installed tool.

    Args:
        path: Path to executable
        tool_name: Tool name for special-case handling
        version_flag: Custom version flag/arg from catalog (e.g., "version", "--version")
        version_command: Custom shell command from catalog (ignores path)

    Returns:
        Version line string or empty string
    """
    # Priority 1: If catalog specifies custom shell command, run it directly
    if version_command:
        try:
            proc = subprocess.run(
                version_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=TIMEOUT_SECONDS,
                check=False,
                env={**os.environ, "TERM": "dumb"},
            )
            line = (proc.stdout or "").strip()
            if line:
                return line
        except Exception:
            pass

    # Priority 2: If catalog specifies custom version flag, use it
    if version_flag:
        line = run_with_timeout([path, version_flag])
        if line:
            return line

    # Priority 3: Special cases (only truly complex cases that can't be handled by catalog)
    if tool_name == "sponge":
        # sponge reads stdin and can block - catalog has version_command to query dpkg
        return "installed"

    if tool_name == "docker-compose":
        base = os.path.basename(path)
        if base == "docker":
            # Plugin form
            line = run_with_timeout([path, "compose", "version"])
            if line:
                return line
        # Legacy binary
        line = run_with_timeout([path, "version"])
        if line:
            return line

    if tool_name == "entr":
        # entr shows version in stderr when run with no args
        try:
            proc = subprocess.run(
                [path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=0.5,
                check=False,
                env={**os.environ, "TERM": "dumb"},
            )
            # Version is in stderr: "release: 5.7"
            stderr = proc.stderr or ""
            for line in stderr.splitlines():
                line = ANSI_ESCAPE_RE.sub('', line.strip())
                if line.startswith("release:"):
                    return line
        except Exception:
            pass


    if tool_name == "fx":
        # fx is a Node.js tool with no --version flag
        # Try to read version from package.json
        real_path = os.path.realpath(path)
        if "node_modules/fx" in real_path:
            pkg_json = real_path.replace("index.js", "package.json")
            if os.path.isfile(pkg_json):
                try:
                    import json
                    with open(pkg_json) as f:
                        data = json.load(f)
                        version = data.get("version", "")
                        if version:
                            return f"fx {version}"
                except Exception:
                    pass
        return "installed"

    # Generic version flags
    for flags in VERSION_FLAG_SETS:
        line = run_with_timeout([path, *flags])
        if not line:
            continue

        # Skip error messages
        lcline = line.lower()
        if (
            lcline.startswith("error:")
            or lcline.startswith("usage")
            or "unknown option" in lcline
            or "try --help" in lcline
        ):
            continue

        # Return if contains version
        if extract_version_number(line):
            return line

    return ""


def detect_install_method(path: str, tool_name: str) -> str:
    """Detect how a tool was installed.

    Args:
        path: Path to executable
        tool_name: Tool name

    Returns:
        Installation method string (e.g., "cargo", "apt", "pipx", "manual")
    """
    if not path or not os.path.exists(path):
        return ""

    real_path = os.path.realpath(path)

    # Cargo (Rust)
    if ".cargo/bin" in real_path:
        return "cargo"

    # UV tools
    if ".local/share/uv/tools" in real_path or "uv/tools" in real_path:
        return "uv"

    # Pipx
    if ".local/pipx" in real_path or ".local/share/pipx" in real_path:
        return "pipx"

    # System package managers
    if real_path.startswith("/usr/bin/") or real_path.startswith("/bin/"):
        return "apt"

    if real_path.startswith("/usr/local/bin/"):
        return "brew"

    # NVM (Node Version Manager)
    if ".nvm/versions" in real_path:
        return "nvm"

    # Manual installation
    if real_path.startswith(HOME):
        return "manual"

    return "system"


def choose_highest(candidates: list[tuple[str, str, str]]) -> tuple[str, str, str] | tuple[()]:
    """Choose highest version from candidates.

    Args:
        candidates: List of (version_num, version_line, path) tuples

    Returns:
        Highest version tuple or empty tuple
    """
    if not candidates:
        return ()

    # Simple lexicographic sort by version
    # For production, use packaging.version.parse() for proper semver comparison
    sorted_cands = sorted(candidates, key=lambda x: x[0], reverse=True)
    return sorted_cands[0]


def audit_tool_installation(
    tool_name: str, candidates: tuple[str, ...], deep: bool = False, version_flag: str | None = None, version_command: str | None = None
) -> tuple[str, str, str, str]:
    """Audit a single tool's installation.

    Args:
        tool_name: Tool name
        candidates: Binary names to search for
        deep: If True, find all installations
        version_flag: Custom version flag from catalog (e.g., "version", "--version")
        version_command: Custom shell command from catalog

    Returns:
        Tuple of (version_num, version_line, path, install_method)
    """
    tuples: list[tuple[str, str, str]] = []

    for cand in candidates:
        for path in find_paths(cand, deep=deep):
            line = get_version_line(path, tool_name, version_flag, version_command)
            if line:
                num = extract_version_number(line)
                tuples.append((num, line, path))

    if not tuples:
        return ("", "X", "", "")

    chosen = choose_highest(tuples)
    if not chosen:
        return ("", "X", "", "")

    version_num, version_line, path = chosen
    install_method = detect_install_method(path, tool_name)

    return (version_num, version_line, path, install_method)
