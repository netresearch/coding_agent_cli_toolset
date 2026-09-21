"""
Local tool detection and version extraction.

Phase 2.0: Detection and Auditing - Local Detection
"""

from __future__ import annotations

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
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m|\033\[[0-9;]*m")

VERSION_FLAG_SETS = (
    ("-v",),
    ("--version",),
    ("-V",),
    ("version",),
)

# Marker returned by audit_tool_installation when the binary exists on disk
# but every version probe timed out (slow binaries like opengrep need ~2.5s
# and can exceed TIMEOUT_SECONDS under parallel collection load). Callers
# fall back to the last known version instead of reporting "not installed".
VERSION_PROBE_TIMEOUT = "<probe-timeout>"

# Pseudo-path recorded when a version was detected via a standalone
# catalog version_command instead of a binary on disk.
VERSION_COMMAND_PATH = "<version_command>"

# Environment-name patterns for env managers without a pyvenv.cfg (conda etc.).
# Mirrors the venv skip list in scripts/lib/capability.sh:detect_all_installations.
_ENV_DIR_PATTERNS = (
    "/venv/bin/",
    "/.venv/bin/",
    "/env/bin/",
    "/venvs/",
    "/.venvs/",
    "/virtualenvs/",
    "/.virtualenvs/",
    "/envs/",
    "/conda/",
    "/miniconda",
    "/anaconda",
)


def _is_virtualenv_bin(bin_dir: str) -> bool:
    """True if bin_dir is a virtualenv/conda environment's bin directory.

    Environments are not installations: their binaries vanish with the env,
    and classifying them by method (e.g. `uv` because the tool also appears
    in `uv tool list`) makes removal delete a DIFFERENT installation.
    """
    # "/x/env/bin/" must behave like "/x/env/bin" (dirname would stay in bin/)
    bin_dir = os.path.normpath(bin_dir)
    # Definitive signal: PEP 405 venvs carry pyvenv.cfg next to bin/
    if os.path.isfile(os.path.join(os.path.dirname(bin_dir), "pyvenv.cfg")):
        return True
    # Name-based fallback for conda/virtualenvwrapper layouts
    normalized = bin_dir.rstrip("/") + "/"
    return any(pat in normalized for pat in _ENV_DIR_PATTERNS)


# Tool managers install each tool into a venv of its own; a binary linked
# from there (~/.local/bin/black -> ~/.local/share/uv/tools/black/bin/black)
# is an installation, not an environment. Default locations, matched as path
# fragments; relocated ones come from the managers' own variables.
_TOOL_ENV_ROOTS = (("uv", "/uv/tools/"), ("pipx", "/pipx/venvs/"))


def tool_manager_of(bin_dir: str) -> str:
    """Return "uv" or "pipx" if bin_dir belongs to that manager's per-tool venv, else ""."""
    normalized = os.path.normpath(bin_dir) + "/"
    for manager, fragment in _TOOL_ENV_ROOTS:
        if fragment in normalized:
            return manager
    relocated = (
        ("uv", os.environ.get("UV_TOOL_DIR", "")),
        ("pipx", os.path.join(os.environ["PIPX_HOME"], "venvs") if os.environ.get("PIPX_HOME") else ""),
        ("pipx", os.path.join(os.environ["PIPX_GLOBAL_HOME"], "venvs") if os.environ.get("PIPX_GLOBAL_HOME") else ""),
    )
    for manager, root in relocated:
        # bin_dir is a resolved path; resolve the root the same way (symlinked
        # home, macOS /var -> /private/var, a relative value)
        if root and normalized.startswith(os.path.realpath(root) + "/"):
            return manager
    return ""


def _is_tool_manager_env(bin_dir: str) -> bool:
    """True if bin_dir belongs to a uv-tool or pipx per-tool venv."""
    return bool(tool_manager_of(bin_dir))


def _installation_path() -> str:
    """PATH without virtualenv/conda bin dirs.

    An activated environment puts its bin dir first on PATH, so a plain
    lookup reports the environment's copy (e.g. ~/.venv/bin/black) and an
    upgrade of the real installation never shows up in the audit.
    """
    dirs = [d for d in os.environ.get("PATH", os.defpath).split(os.pathsep) if d]
    return os.pathsep.join(d for d in dirs if not _is_virtualenv_bin(d))


def _which(command_name: str) -> str | None:
    """shutil.which restricted to installation dirs (see _installation_path)."""
    return shutil.which(command_name, path=_installation_path())


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
    p = _which(command_name)
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
                # Disable ANSI output; search installation dirs only
                env={**os.environ, "TERM": "dumb", "PATH": _installation_path()},
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


def run_with_timeout(args: Sequence[str], timeout: float | None = None, capture_stderr: bool = True) -> str | None:
    """Run command with timeout and return output with version info.

    Args:
        args: Command and arguments
        timeout: Timeout in seconds (default: TIMEOUT_SECONDS)
        capture_stderr: If True, merge stderr into stdout

    Returns:
        Line containing version, or first line if no version found.
        None if the command timed out (distinct from "" for other failures).
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
        cleaned_lines = [ANSI_ESCAPE_RE.sub("", line.strip()) for line in lines]

        # Search for line containing version number (prefer this over first line)
        for line in cleaned_lines:
            if line and VERSION_RE.search(line):
                return line

        # Fallback: return first non-empty line
        for line in cleaned_lines:
            if line:
                return line

        return ""
    except subprocess.TimeoutExpired:
        return None
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


def get_version_line(
    path: str, tool_name: str, version_flag: str | None = None, version_command: str | None = None
) -> str | None:
    """Get version string for installed tool.

    Args:
        path: Path to executable
        tool_name: Tool name for special-case handling
        version_flag: Custom version flag/arg from catalog (e.g., "version", "--version")
        version_command: Custom shell command from catalog (ignores path)

    Returns:
        Version line string, or empty string if no probe produced output.
        None if at least one probe timed out and none produced a version.
    """
    timed_out = False
    line: str | None

    # Priority 1: If catalog specifies custom shell command, run it directly.
    # version_command comes from trusted catalog JSON (committed in-repo), never
    # from user input — e.g. `uv python list --only-installed | grep … | sed …`.
    # shell=True is required for the pipelines used in the catalog.
    if version_command:
        # The command names the tool, not the path: resolve that name the way
        # find_paths does, never to an activated environment's copy.
        search_path = _installation_path()
        try:
            proc = subprocess.run(  # nosec B602
                version_command,
                shell=True,  # nosec B602
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=TIMEOUT_SECONDS,
                check=False,
                env={**os.environ, "TERM": "dumb", "PATH": search_path},
            )
            line = (proc.stdout or "").strip()
            if line:
                return line
        except subprocess.TimeoutExpired:
            timed_out = True
        except Exception:
            pass

    # Priority 2: If catalog specifies custom version flag, use it
    if version_flag:
        line = run_with_timeout([path, version_flag])
        if line:
            return line
        if line is None:
            timed_out = True

    # Priority 3: Special cases (only truly complex cases that can't be handled by catalog)
    if tool_name == "sponge":
        # sponge reads stdin and can block - catalog has version_command to query dpkg
        return "installed"

    # Generic version flags
    for flags in VERSION_FLAG_SETS:
        line = run_with_timeout([path, *flags])
        if line is None:
            timed_out = True
            continue
        if not line:
            continue

        # Skip error messages
        lcline = line.lower()
        if lcline.startswith("error:") or lcline.startswith("usage") or "unknown option" in lcline or "try --help" in lcline:
            continue

        # Return if contains version
        if extract_version_number(line):
            return line

    # Fallback: fx legacy Node.js version (installed via npm)
    # Only runs if --version didn't work (old Node.js version of fx)
    if tool_name == "fx":
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

    return None if timed_out else ""


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
    tool_name: str,
    candidates: tuple[str, ...],
    deep: bool = False,
    version_flag: str | None = None,
    version_command: str | None = None,
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
    timed_out_paths: list[str] = []

    for cand in candidates:
        for path in find_paths(cand, deep=deep):
            line = get_version_line(path, tool_name, version_flag, version_command)
            if line:
                num = extract_version_number(line)
                tuples.append((num, line, path))
            elif line is None:
                timed_out_paths.append(path)

    # If no paths found but version_command exists, try standalone version detection
    if not tuples and version_command:
        line = get_version_line("", tool_name, version_flag, version_command)
        if line:
            num = extract_version_number(line)
            tuples.append((num, line, VERSION_COMMAND_PATH))
        elif line is None:
            timed_out_paths.append(VERSION_COMMAND_PATH)

    if not tuples:
        # A probe ran but timed out: signal the timeout so callers can fall
        # back to the last known version instead of misreporting the tool
        # as not installed.
        if timed_out_paths:
            path = timed_out_paths[0]
            if path == VERSION_COMMAND_PATH:
                return ("", VERSION_PROBE_TIMEOUT, path, "version_command")
            return ("", VERSION_PROBE_TIMEOUT, path, detect_install_method(path, tool_name))
        return ("", "X", "", "")

    chosen = choose_highest(tuples)
    if not chosen:
        return ("", "X", "", "")

    version_num, version_line, path = chosen

    # Handle version_command detection (no physical path)
    if path == VERSION_COMMAND_PATH:
        install_method = "version_command"
    else:
        install_method = detect_install_method(path, tool_name)

    return (version_num, version_line, path, install_method)


def scan_version_manager_dir(
    base_dir: str,
    version_prefix: str = "",
    binary_subpath: str = "bin",
    binary_name: str = "",
) -> list[tuple[str, str]]:
    """Scan a version manager directory for installed versions.

    Args:
        base_dir: Base directory (e.g., "~/.nvm/versions/node")
        version_prefix: Prefix to strip (e.g., "v" for node versions like "v22.0.0")
        binary_subpath: Subdirectory containing the binary (e.g., "bin")
        binary_name: Name of the binary to look for (e.g., "node", "ruby")

    Returns:
        List of (version, binary_path) tuples for installed versions
    """
    base_dir = os.path.expanduser(base_dir)
    if not os.path.isdir(base_dir):
        return []

    results = []
    for version_dir in sorted(os.listdir(base_dir), reverse=True):
        version_path = os.path.join(base_dir, version_dir)
        if not os.path.isdir(version_path):
            continue

        # Get version string (strip prefix if present)
        version = version_dir
        if version_prefix and version.startswith(version_prefix):
            version = version[len(version_prefix) :]

        # Find the binary
        if binary_name:
            binary_path = os.path.join(version_path, binary_subpath, binary_name)
            if os.path.isfile(binary_path) and os.access(binary_path, os.X_OK):
                results.append((version, binary_path))

    return results


def detect_multi_versions(
    tool_name: str,
    multi_version_config: dict,
    supported_versions: list[dict],
) -> list[dict]:
    """Detect multiple installed versions of a runtime.

    This function checks for version-specific binaries (e.g., php8.4, php8.3)
    or scans version manager directories (e.g., ~/.nvm/versions/node/).

    Args:
        tool_name: Base tool name (e.g., "php", "python", "go", "node")
        multi_version_config: Multi-version configuration from catalog, containing:
            - binary_pattern: Pattern like "php{cycle}" or "python{cycle}"
            - candidates: List of patterns to try
            - version_manager_dir: Directory to scan (e.g., "~/.nvm/versions/node")
            - version_prefix: Prefix to strip from directory names (e.g., "v")
            - binary_subpath: Subdirectory containing binary (default: "bin")
        supported_versions: List of supported versions from endoflife.date, each with:
            - cycle: Version cycle (e.g., "8.4", "3.12", "22")
            - latest: Latest patch version
            - status: "active" or "security"

    Returns:
        List of detected version info dicts, each containing:
        - cycle: Version cycle (e.g., "8.4")
        - latest_upstream: Latest upstream version (e.g., "8.4.17")
        - installed: Installed version or None
        - path: Path to binary or None
        - install_method: How it was installed
        - status: "active" or "security" (from endoflife.date)

    Example:
        >>> detect_multi_versions("php", {"binary_pattern": "php{cycle}"},
        ...     [{"cycle": "8.4", "latest": "8.4.17", "status": "active"}])
        [{"cycle": "8.4", "installed": "8.4.16", "path": "/usr/bin/php8.4", ...}]
    """
    results = []

    # Check if using version manager directory scanning
    version_manager_dir = multi_version_config.get("version_manager_dir")

    if version_manager_dir:
        # Scan version manager directory for installed versions
        version_prefix = multi_version_config.get("version_prefix", "")
        binary_subpath = multi_version_config.get("binary_subpath", "bin")
        binary_name = multi_version_config.get("binary_name", tool_name)

        installed_versions = scan_version_manager_dir(version_manager_dir, version_prefix, binary_subpath, binary_name)

        # Create a lookup map: major.minor -> (full_version, path)
        installed_map: dict[str, tuple[str, str]] = {}
        for version, path in installed_versions:
            # Extract major.minor from full version (e.g., "22.12.0" -> "22")
            parts = version.split(".")
            if parts:
                major = parts[0]
                # For some runtimes, use major.minor (e.g., Python 3.12)
                if len(parts) > 1 and tool_name in ("python", "ruby"):
                    key = f"{parts[0]}.{parts[1]}"
                else:
                    key = major
                # Keep the highest patch version for each major/minor
                if key not in installed_map or version > installed_map[key][0]:
                    installed_map[key] = (version, path)

        for version_info in supported_versions:
            cycle = str(version_info.get("cycle", ""))
            if not cycle:
                continue

            installed_version = None
            found_path = None

            if cycle in installed_map:
                installed_version, found_path = installed_map[cycle]

            result = {
                "cycle": cycle,
                "latest_upstream": version_info.get("latest", ""),
                "installed": installed_version,
                "path": found_path,
                "install_method": detect_install_method(found_path, tool_name) if found_path else None,
                "status": version_info.get("status", "unknown"),
                "eol": version_info.get("eol"),
                "lts": version_info.get("lts", False),
            }
            results.append(result)

    else:
        # Use binary pattern matching (original behavior)
        binary_pattern = multi_version_config.get("binary_pattern", f"{tool_name}{{cycle}}")
        candidate_patterns = multi_version_config.get("candidates", [binary_pattern])

        # For Go: detect the default 'go' binary version as a fallback
        # (used only when no version-specific binary like go1.25 is found)
        go_default_info = None
        if tool_name == "go":
            default_go = _which("go")
            if default_go:
                version_line = get_version_line(default_go, "go", version_flag="version")
                default_version = extract_version_number(version_line or "")
                if default_version:
                    parts = default_version.split(".")
                    if len(parts) >= 2:
                        go_default_info = {
                            "cycle": f"{parts[0]}.{parts[1]}",
                            "version": default_version,
                            "path": default_go,
                        }

        for version_info in supported_versions:
            cycle = version_info.get("cycle", "")
            if not cycle:
                continue

            # Try each candidate pattern
            found_path = None
            installed_version = None

            for pattern in candidate_patterns:
                # Replace {cycle} with actual version cycle
                binary_name = pattern.replace("{cycle}", str(cycle))

                # Check if absolute path
                if binary_name.startswith("/"):
                    if os.path.isfile(binary_name) and os.access(binary_name, os.X_OK):
                        found_path = binary_name
                else:
                    # Search in PATH
                    path = _which(binary_name)
                    if path:
                        found_path = path

                if found_path:
                    # Get version info
                    version_line = get_version_line(found_path, tool_name)
                    installed_version = extract_version_number(version_line or "")
                    break

            # Go fallback: if no version-specific binary found, check if default
            # 'go' binary belongs to this cycle (e.g., /usr/local/go/bin/go)
            if not found_path and go_default_info and str(cycle) == go_default_info["cycle"]:
                found_path = go_default_info["path"]
                installed_version = go_default_info["version"]

            result = {
                "cycle": cycle,
                "latest_upstream": version_info.get("latest", ""),
                "installed": installed_version,
                "path": found_path,
                "install_method": detect_install_method(found_path, tool_name) if found_path else None,
                "status": version_info.get("status", "unknown"),
                "eol": version_info.get("eol"),
                "lts": version_info.get("lts", False),
            }
            results.append(result)

    return results
