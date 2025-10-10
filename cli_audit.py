#!/usr/bin/env python3
"""
CLI audit: detect installed versions of common developer tools and compare
against latest upstream releases (GitHub/PyPI/crates.io).

Outputs a pipe-delimited table:
  tool|installed|latest_upstream|status

Notes
- Installed: first version line from the selected binary, or "X" if not found.
- Latest: latest tag/version from upstream. Empty when unknown.
- Status: UP-TO-DATE, OUTDATED, NOT INSTALLED, or UNKNOWN.

Behavior
- Searches PATH for all candidates and also checks ~/.cargo/bin for cargo tools.
- Picks the highest installed version when multiple candidates exist.
- Uses short timeouts to avoid hangs.
- Falls back for tools with non-standard version flags (e.g., entr, sponge).
"""

from __future__ import annotations

import json
import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import datetime
import urllib.error
import urllib.request
from urllib.parse import urlparse
import random
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Sequence, Tuple
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


TIMEOUT_SECONDS: int = int(os.environ.get("CLI_AUDIT_TIMEOUT_SECONDS", "3"))
CARGO_BIN: str = os.path.expanduser("~/.cargo/bin")
USER_AGENT_HEADERS = {"User-Agent": "cli-audit/1.0"}
NPM_REGISTRY_URL = "https://registry.npmjs.org"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Manual cache lock for updating the committed latest_versions.json
MANUAL_LOCK = threading.Lock()

# Output rendering options
STDOUT_IS_TTY: bool = sys.stdout.isatty()
# Respect env flags regardless of TTY so links/icons can be used with pipes (e.g., column)
ENABLE_LINKS: bool = os.environ.get("CLI_AUDIT_LINKS", "1") == "1"
USE_EMOJI_ICONS: bool = os.environ.get("CLI_AUDIT_EMOJI", "1") == "1"
OFFLINE_MODE: bool = os.environ.get("CLI_AUDIT_OFFLINE", "0") == "1"
MAX_WORKERS: int = int(os.environ.get("CLI_AUDIT_MAX_WORKERS", "4"))  # Reduced from 8 to avoid network congestion
DOCKER_INFO_ENABLED: bool = os.environ.get("CLI_AUDIT_DOCKER_INFO", "1") == "1"
PROGRESS: bool = os.environ.get("CLI_AUDIT_PROGRESS", "0") == "1"
OFFLINE_USE_CACHE: bool = os.environ.get("CLI_AUDIT_OFFLINE_USE_CACHE", "1") == "1"  # kept for compatibility, no effect
SHOW_TIMINGS: bool = os.environ.get("CLI_AUDIT_TIMINGS", "1") == "1"
MANUAL_FIRST: bool = os.environ.get("CLI_AUDIT_MANUAL_FIRST", "0") == "1"
DPKG_CACHE: dict[str, bool] = {}
DPKG_OWNER_CACHE: dict[str, str] = {}
DPKG_VERSION_CACHE: dict[str, str] = {}
SORT_MODE: str = os.environ.get("CLI_AUDIT_SORT", "order")  # 'order' or 'alpha'
AUDIT_DEBUG: bool = os.environ.get("CLI_AUDIT_DEBUG", "0") == "1"
DPKG_CACHE_LIMIT: int = int(os.environ.get("CLI_AUDIT_DPKG_CACHE_LIMIT", "1024"))
VALIDATE_MANUAL: bool = os.environ.get("CLI_AUDIT_VALIDATE_MANUAL", "1") == "1"

# Local-readiness UX toggles
HINTS_ENABLED: bool = os.environ.get("CLI_AUDIT_HINTS", "1") == "1"
GROUP_BY_CATEGORY: bool = os.environ.get("CLI_AUDIT_GROUP", "1") == "1"
FAST_MODE: bool = os.environ.get("CLI_AUDIT_FAST", "0") == "1"
STREAM_OUTPUT: bool = os.environ.get("CLI_AUDIT_STREAM", "0") == "1"

# Snapshot / mode toggles (decouple collection from rendering)
COLLECT_ONLY: bool = os.environ.get("CLI_AUDIT_COLLECT", "0") == "1"
RENDER_ONLY: bool = os.environ.get("CLI_AUDIT_RENDER", "0") == "1"
SNAPSHOT_FILE: str = os.environ.get(
    "CLI_AUDIT_SNAPSHOT_FILE",
    os.path.join(os.path.dirname(__file__), "tools_snapshot.json"),
)

# HTTP behavior controls
HTTP_RETRIES: int = int(os.environ.get("CLI_AUDIT_HTTP_RETRIES", "2"))
HTTP_BACKOFF_BASE: float = float(os.environ.get("CLI_AUDIT_BACKOFF_BASE", "0.2"))
HTTP_BACKOFF_JITTER: float = float(os.environ.get("CLI_AUDIT_BACKOFF_JITTER", "0.1"))

# Ultra-verbose tracing
TRACE: bool = os.environ.get("CLI_AUDIT_TRACE", "0") == "1"
TRACE_NET: bool = os.environ.get("CLI_AUDIT_TRACE_NET", "0") == "1" or AUDIT_DEBUG  # Auto-enable with DEBUG
SLOW_MS: int = int(os.environ.get("CLI_AUDIT_SLOW_MS", "2000"))

def _vlog(msg: str) -> None:
    if PROGRESS or TRACE:
        try:
            print(msg, file=sys.stderr)
        except Exception:
            pass

def _tlog(msg: str) -> None:
    if TRACE:
        try:
            print(msg, file=sys.stderr)
        except Exception:
            pass

def _now_iso() -> str:
    try:
        return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    except Exception:
        return ""

def _atomic_write_json(path: str, obj: Any) -> None:
    try:
        base = os.path.dirname(path) or "."
        tmp = os.path.join(base, ".tmp_" + os.path.basename(path))
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=True)
        os.replace(tmp, path)
    except Exception as e:
        if AUDIT_DEBUG:
            print(f"# DEBUG: atomic write failed for {path}: {e}", file=sys.stderr)

def _read_json_safe(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def load_snapshot(paths: Sequence[str] | None = None) -> dict[str, Any]:
    """Load snapshot from the first existing path among provided or defaults.

    Tries SNAPSHOT_FILE, then legacy latest_versions.json.
    """
    candidates: list[str] = []
    if paths:
        candidates.extend(list(paths))
    else:
        candidates.append(SNAPSHOT_FILE)
        legacy = os.path.join(os.path.dirname(__file__), "latest_versions.json")
        if legacy not in candidates:
            candidates.append(legacy)
    for p in candidates:
        if os.path.isfile(p):
            d = _read_json_safe(p)
            if d:
                return d
    return {}

def write_snapshot(tools_payload: list[dict[str, Any]], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = {
        "schema_version": 1,
        "created_at": _now_iso(),
        "offline": OFFLINE_MODE,
        "count": len(tools_payload),
        "partial_failures": sum(1 for t in tools_payload if (t.get("status") == "UNKNOWN" and not t.get("installed"))),
    }
    if extra:
        try:
            meta.update(extra)
        except Exception:
            pass
    doc = {"__meta__": meta, "tools": tools_payload}
    _atomic_write_json(SNAPSHOT_FILE, doc)
    return meta

def render_from_snapshot(doc: dict[str, Any], selected: set[str] | None = None) -> list[tuple[str, str, str, str, str, str, str, str]]:
    items = doc.get("tools", [])
    out: list[tuple[str, str, str, str, str, str, str, str]] = []
    try:
        for it in items:
            name = str(it.get("tool", "")).strip()
            if not name:
                continue
            if selected and name.lower() not in selected:
                continue
            installed = str(it.get("installed", ""))
            installed_method = str(it.get("installed_method", ""))
            latest = str(it.get("latest_upstream", it.get("latest_version", "")))
            upstream_method = str(it.get("upstream_method", ""))
            status = str(it.get("status", "UNKNOWN"))
            tool_url = str(it.get("tool_url", ""))
            latest_url = str(it.get("latest_url", ""))
            # Reconstruct display tuple (state icon computed at print time)
            out.append((name, installed, installed_method, latest, upstream_method, status, tool_url, latest_url))
    except Exception:
        pass
    return out

# Cache of uv-managed tools (populated lazily)
UV_TOOLS_LOADED: bool = False
UV_TOOLS: set[str] = set()

# Manual versions file (committed to repo) used as base/offline source
MANUAL_FILE: str = os.environ.get(
    "CLI_AUDIT_MANUAL_FILE",
    os.path.join(os.path.dirname(__file__), "latest_versions.json"),
)
MANUAL_VERSIONS: dict[str, Any] = {}
# Disable incremental writes during parallel execution to avoid file locking deadlocks
# With MAX_WORKERS > 1, multiple threads compete for MANUAL_LOCK causing severe contention
# Incremental writes are unnecessary since snapshot/results are finalized at the end
WRITE_MANUAL: bool = os.environ.get("CLI_AUDIT_WRITE_MANUAL", "1") == "1" and MAX_WORKERS == 1
MANUAL_USED: dict[str, bool] = {}

# Selected-path tracking for JSON output (populated by audit_tool)
SELECTED_PATHS: dict[str, str] = {}
SELECTED_REASON: dict[str, str] = {}

# Per-origin concurrency caps for network requests
SEMAPHORES: dict[str, threading.BoundedSemaphore] = {
    "github.com": threading.BoundedSemaphore(value=int(os.environ.get("CLI_AUDIT_HOST_CAP_GITHUB", "4"))),
    "api.github.com": threading.BoundedSemaphore(value=int(os.environ.get("CLI_AUDIT_HOST_CAP_GITHUB_API", "4"))),
    "registry.npmjs.org": threading.BoundedSemaphore(value=int(os.environ.get("CLI_AUDIT_HOST_CAP_NPM", "4"))),
    "crates.io": threading.BoundedSemaphore(value=int(os.environ.get("CLI_AUDIT_HOST_CAP_CRATES", "4"))),
    "ftp.gnu.org": threading.BoundedSemaphore(value=int(os.environ.get("CLI_AUDIT_HOST_CAP_GNU", "2"))),
    "ftpmirror.gnu.org": threading.BoundedSemaphore(value=int(os.environ.get("CLI_AUDIT_HOST_CAP_GNU", "2"))),
    "mirrors.kernel.org": threading.BoundedSemaphore(value=int(os.environ.get("CLI_AUDIT_HOST_CAP_GNU", "2"))),
}


def _accept_header_for_host(host: str) -> str:
    try:
        if host == "api.github.com":
            return "application/vnd.github+json"
        if host in ("registry.npmjs.org", "crates.io"):
            return "application/json"
        if host.endswith("gnu.org") or host.endswith("kernel.org"):
            return "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        return "*/*"
    except Exception:
        return "*/*"


def http_fetch(
    url: str,
    timeout: float | int = TIMEOUT_SECONDS,
    headers: dict[str, str] | None = None,
    retries: int = None,
    backoff_base: float = None,
    jitter: float = None,
    method: str | None = None,
) -> bytes:
    """Fetch URL with retries, jitter, and per-origin concurrency caps.

    Raises on final failure; callers are expected to catch.
    """
    parsed = urlparse(url)
    host = parsed.netloc
    sem = SEMAPHORES.get(host)
    # Build headers
    req_headers = dict(USER_AGENT_HEADERS)
    req_headers["Accept"] = _accept_header_for_host(host)
    if headers:
        try:
            req_headers.update(headers)
        except Exception:
            pass
    # GitHub token only for API host
    if GITHUB_TOKEN and host == "api.github.com":
        req_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    if retries is None:
        retries = HTTP_RETRIES
    if backoff_base is None:
        backoff_base = HTTP_BACKOFF_BASE
    if jitter is None:
        jitter = HTTP_BACKOFF_JITTER
    last_exc: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            # Debug: show HTTP request details
            if AUDIT_DEBUG:
                method_str = method or "GET"
                print(f"# DEBUG: HTTP {method_str} {url} (timeout={timeout}s, attempt={attempt+1}/{retries})", file=sys.stderr, flush=True)

            if sem is None:
                req = urllib.request.Request(url, headers=req_headers, method=method)
                req_start = time.time()
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read()
                    req_dur = int((time.time() - req_start) * 1000)
                    if TRACE_NET:
                        _tlog(f"# http_open host={host} code={getattr(resp, 'status', 0)} url={url}")
                    if AUDIT_DEBUG:
                        status = getattr(resp, 'status', 0)
                        content_len = len(data)
                        print(f"# DEBUG: HTTP {status} {url} ({req_dur}ms, {content_len} bytes)", file=sys.stderr, flush=True)
                    return data
            with sem:
                req = urllib.request.Request(url, headers=req_headers, method=method)
                req_start = time.time()
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read()
                    req_dur = int((time.time() - req_start) * 1000)
                    if TRACE_NET:
                        _tlog(f"# http_open host={host} code={getattr(resp, 'status', 0)} url={url}")
                    if AUDIT_DEBUG:
                        status = getattr(resp, 'status', 0)
                        content_len = len(data)
                        print(f"# DEBUG: HTTP {status} {url} ({req_dur}ms, {content_len} bytes)", file=sys.stderr, flush=True)
                    return data
        except urllib.error.HTTPError as e:
            last_exc = e
            code = getattr(e, "code", 0) or 0
            retryable = (code == 429) or (500 <= code <= 599) or (host == "api.github.com" and code == 403)
            if TRACE_NET:
                _tlog(f"# http_error host={host} code={code} retryable={retryable} url={url}")
            if AUDIT_DEBUG:
                print(f"# DEBUG: HTTP ERROR {code} {url} (retryable={retryable}, attempt={attempt+1}/{retries})", file=sys.stderr, flush=True)
            if attempt >= retries - 1 or not retryable:
                raise
        except Exception as e:
            last_exc = e
            exc_type = type(e).__name__
            exc_msg = str(e)[:100]  # Truncate long error messages
            if TRACE_NET:
                _tlog(f"# http_exc host={host} type={exc_type} attempt={attempt+1}/{retries} url={url}")
            if AUDIT_DEBUG:
                print(f"# DEBUG: HTTP EXCEPTION {exc_type}: {exc_msg} on {url} (attempt={attempt+1}/{retries})", file=sys.stderr, flush=True)
            if attempt >= retries - 1:
                raise
        # backoff with jitter
        try:
            delay = (backoff_base or 0) * (2 ** attempt) + random.random() * (jitter or 0)
            if delay > 0 and (PROGRESS or TRACE_NET):
                _tlog(f"# http_backoff host={host} attempt={attempt+1}/{retries} delay={delay:.2f}s url={url}")
                time.sleep(delay)
        except Exception:
            pass
    if last_exc:
        raise last_exc
    return b""

# Hints: persisted inside latest_versions.json under a special key "__hints__"
HINTS: dict[str, str] = {}
HINTS_LOCK = threading.Lock()

def load_manual_versions() -> None:
    global MANUAL_VERSIONS
    try:
        with open(MANUAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                # normalize keys to str; keep dict values (e.g., __hints__) intact
                mv: dict[str, Any] = {}
                for k, v in data.items():
                    if isinstance(v, dict):
                        mv[str(k)] = v
                    else:
                        mv[str(k)] = str(v)
                MANUAL_VERSIONS = mv
                try:
                    if VALIDATE_MANUAL:
                        _normalize_manual_versions_if_needed()
                except Exception as e:
                    if AUDIT_DEBUG:
                        print(f"# DEBUG: manual normalize failed: {e}", file=sys.stderr)
            else:
                MANUAL_VERSIONS = {}
    except Exception:
        MANUAL_VERSIONS = {}

def _normalize_manual_versions_if_needed() -> None:
    """Validate/normalize MANUAL_VERSIONS values; migrate odd shapes into __hints__.

    This function performs in-place normalization and persists to MANUAL_FILE
    when changes are detected. It is tolerant and only rewrites on change.
    """
    try:
        if not isinstance(MANUAL_VERSIONS, dict) or not MANUAL_VERSIONS:
            return
        original = dict(MANUAL_VERSIONS)
        hints = original.get("__hints__", {})
        if not isinstance(hints, dict):
            hints = {}
        changed = False
        normalized: dict[str, Any] = {}
        for k, v in original.items():
            sk = str(k)
            if sk.startswith("__"):
                normalized[sk] = v
                continue
            sv = v if isinstance(v, str) else str(v)
            # If the stored value isn't a clean version string, try to extract a numeric version
            ver = extract_version_number(sv)
            if ver and ver != sv.strip():
                # record migration of original value
                hints[f"migrated:{sk}"] = sv
                normalized[sk] = ver
                changed = True
            else:
                normalized[sk] = sv
        if changed:
            normalized["__hints__"] = hints
            with MANUAL_LOCK:
                try:
                    with open(MANUAL_FILE, "w", encoding="utf-8") as f:
                        json.dump(normalized, f, indent=2, ensure_ascii=False, sort_keys=True)
                    MANUAL_VERSIONS.clear()
                    MANUAL_VERSIONS.update(normalized)
                except Exception as e:
                    if AUDIT_DEBUG:
                        print(f"# DEBUG: failed writing normalized manual file: {e}", file=sys.stderr)
    except Exception as e:
        if AUDIT_DEBUG:
            print(f"# DEBUG: normalize error: {e}", file=sys.stderr)

def get_manual_latest(tool_name: str) -> tuple[str, str]:
    if not MANUAL_VERSIONS:
        load_manual_versions()
    tag = MANUAL_VERSIONS.get(tool_name, "").strip()
    if not tag:
        return "", ""
    return tag, extract_version_number(tag) or tag

def load_hints() -> None:
    global HINTS
    if HINTS:
        return
    try:
        load_manual_versions()
        data = MANUAL_VERSIONS.get("__hints__", {})
        if isinstance(data, dict):
            HINTS = {str(k): str(v) for k, v in data.items()}
        else:
            HINTS = {}
        # Ensure MANUAL_VERSIONS conforms to normalization after hints are loaded
        if VALIDATE_MANUAL:
            _normalize_manual_versions_if_needed()
    except Exception:
        HINTS = {}

def get_hint(key: str) -> str:
    if not HINTS:
        load_hints()
    return HINTS.get(key, "")

def set_hint(key: str, value: str) -> None:
    try:
        # Enforce lock ordering: MANUAL_LOCK -> HINTS_LOCK
        with MANUAL_LOCK:
            with HINTS_LOCK:
                load_hints()
                if HINTS.get(key) == value:
                    return
                HINTS[key] = value
                # persist inside manual file under "__hints__"
                mv = dict(MANUAL_VERSIONS)
                mv["__hints__"] = HINTS
                with open(MANUAL_FILE, "w", encoding="utf-8") as f:
                    json.dump(mv, f, indent=2, ensure_ascii=False, sort_keys=True)
    except Exception:
        pass

def get_local_flag_hint(tool_name: str) -> str:
    return get_hint(f"local_flag:{tool_name}")

def set_local_flag_hint(tool_name: str, flag: str) -> None:
    if flag:
        set_hint(f"local_flag:{tool_name}", flag)

def get_local_dc_hint() -> str:
    return get_hint("local_dc:docker-compose")

def set_local_dc_hint(mode: str) -> None:
    if mode in ("plugin", "legacy"):
        set_hint("local_dc:docker-compose", mode)

# Known Python-console CLIs -> distribution names for importlib.metadata
PYCLI_DISTS: dict[str, str] = {
    # core
    "pip": "pip",
    "pipx": "pipx",
    "poetry": "poetry",
    "httpie": "httpie",
    "pre-commit": "pre-commit",
    "bandit": "bandit",
    "semgrep": "semgrep",
    "black": "black",
    "isort": "isort",
    "flake8": "flake8",
    # ansible-core handled specially below but keep here for fast path
    "ansible-core": "ansible-core",
}

# Prefer faster flags for some CLIs on first run (can be overridden by learned hints)
FAST_FLAG_DEFAULTS: dict[str, tuple[str, ...]] = {
    # Node package managers
    "npm": ("-v", "--version", "version"),
    "pnpm": ("-v", "--version", "version"),
    "yarn": ("-v", "--version", "version"),
    # sd (stream editor) – prefer --version first to avoid Clap error output
    "sd": ("--version",),
    # Prefer known-good flags for common tools that reject -v
    "jq": ("--version",),
    "fzf": ("--version",),
    "ctags": ("--version", "-V"),
    "ripgrep": ("-V", "--version"),
    "ast-grep": ("--version", "-V", "version"),
}

def _dpkg_owner_for_path(path: str) -> str:
    try:
        if path in DPKG_OWNER_CACHE:
            return DPKG_OWNER_CACHE[path]
        line = run_with_timeout(["dpkg", "-S", path])
        # Format: 'pkg: /usr/bin/tool'
        # Ignore dpkg error messages (e.g., 'dpkg-query: no path found ...')
        if not line or line.startswith("dpkg-query:"):
            DPKG_OWNER_CACHE[path] = ""
            return ""
        pkg = line.split(":", 1)[0].strip()
        if pkg == "dpkg-query":
            DPKG_OWNER_CACHE[path] = ""
            return ""
        DPKG_OWNER_CACHE[path] = pkg
        # bound cache
        if len(DPKG_OWNER_CACHE) > DPKG_CACHE_LIMIT:
            try:
                DPKG_OWNER_CACHE.pop(next(iter(DPKG_OWNER_CACHE)))
            except Exception:
                pass
        return pkg
    except Exception:
        return ""

def _dpkg_version_for_pkg(pkg: str) -> str:
    try:
        if not pkg:
            return ""
        if pkg in DPKG_VERSION_CACHE:
            return DPKG_VERSION_CACHE[pkg]
        # Use dpkg-query with format for speed
        line = run_with_timeout(["dpkg-query", "-W", f"-f=${{Version}}", pkg])
        ver = (line or "").strip()
        # Filter out dpkg error outputs; accept only version-like strings
        if not ver or ver.startswith("dpkg-query:") or not re.search(r"\d", ver):
            DPKG_VERSION_CACHE[pkg] = ""
            return ""
        DPKG_VERSION_CACHE[pkg] = ver
        if len(DPKG_VERSION_CACHE) > DPKG_CACHE_LIMIT:
            try:
                DPKG_VERSION_CACHE.pop(next(iter(DPKG_VERSION_CACHE)))
            except Exception:
                pass
        return ver
    except Exception:
        return ""

def _dpkg_version_line_for_path(tool_name: str, path: str) -> str:
    try:
        if not (path.startswith("/usr/") or path.startswith("/bin/")):
            return ""
        # Exclude local prefixes which are not owned by dpkg (e.g., /usr/local/...)
        if path.startswith("/usr/local/"):
            return ""
        pkg = _dpkg_owner_for_path(path)
        if not pkg:
            return ""
        ver = _dpkg_version_for_pkg(pkg)
        if ver:
            return f"{tool_name} {ver}"
        return ""
    except Exception:
        return ""

def _read_json(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        if AUDIT_DEBUG:
            print(f"# DEBUG: _read_json failed for {path}: {e}", file=sys.stderr)
        return {}


def _load_uv_tools() -> None:
    """Populate UV_TOOLS with names managed by `uv tool` (best-effort, fast)."""
    global UV_TOOLS_LOADED, UV_TOOLS
    if UV_TOOLS_LOADED:
        return
    UV_TOOLS_LOADED = True
    try:
        if not shutil.which("uv"):
            return
        # Prefer JSON output when supported
        out = run_with_timeout(["uv", "tool", "list", "--json"]) or ""
        names: set[str] = set()
        parsed: Any = None
        try:
            parsed = json.loads(out) if out else None
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    # Common keys: name/package/id
                    for key in ("name", "package", "id"):
                        v = str(item.get(key, "")).strip()
                        if v:
                            names.add(v)
        elif isinstance(parsed, dict):
            # Some formats may return a dict of tools
            for k in parsed.keys():
                names.add(str(k))
        else:
            # Fallback: plain text list, one name per line (best-effort)
            for line in (out or "").splitlines():
                tok = line.strip().split()[0:1]
                if tok:
                    names.add(tok[0])
        # Normalize to lower-case tool invocation names
        UV_TOOLS = {n.strip().lower() for n in names if n.strip()}
    except Exception as e:
        # Best-effort only
        if AUDIT_DEBUG:
            print(f"# DEBUG: _load_uv_tools error: {e}", file=sys.stderr)
        pass


def _is_uv_tool(tool_name: str) -> bool:
    try:
        _load_uv_tools()
        return tool_name.lower() in UV_TOOLS
    except Exception:
        return False

def _node_pkg_version_from_path(tool_name: str, exe_path: str) -> str:
    """Try to resolve Node CLI version by scanning nearby package.json files.

    Works for npm/pnpm/yarn installed via nvm/corepack or global npm.
    """
    try:
        real = os.path.realpath(exe_path)
        # Corepack shims live under paths that include 'corepack' and have their
        # own package.json (version ~0.34.x). That version is NOT the actual
        # pnpm/yarn version. In that case, skip the adjacent package.json fast
        # path so we fall back to running the CLI with --version/-v.
        if "corepack" in real or "/.corepack" in real or "/.cache/corepack" in real:
            return ""
        cur = os.path.dirname(real)
        # Check up to 3 levels up for package.json
        for _ in range(4):
            pkg = os.path.join(cur, "package.json")
            if os.path.isfile(pkg):
                data = _read_json(pkg)
                v = str(data.get("version", "")).strip()
                if v:
                    return f"{tool_name} {v}"
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    except Exception:
        pass
    return ""

def _python_dist_version_from_venv(tool_name: str, exe_path: str, dist_name: str) -> str:
    """Resolve Python package version by reading dist-info in the venv.

    Handles pipx/virtualenv layouts; avoids spawning Python.
    """
    try:
        real = os.path.realpath(exe_path)
        # Expect .../venv/bin/<tool> or .../bin/<tool>
        bin_dir = os.path.dirname(real)
        venv_root = os.path.dirname(bin_dir)
        lib_dir = os.path.join(venv_root, "lib")
        if not os.path.isdir(lib_dir):
            return ""
        # Find pythonX.Y dir
        py_dirs = [d for d in os.listdir(lib_dir) if d.startswith("python")]
        for py in py_dirs:
            sp = os.path.join(lib_dir, py, "site-packages")
            if not os.path.isdir(sp):
                continue
            # Look for dist-info
            prefix = f"{dist_name}-"
            try:
                for entry in os.listdir(sp):
                    if not entry.startswith(prefix) or not entry.endswith(".dist-info"):
                        continue
                    meta = os.path.join(sp, entry, "METADATA")
                    if os.path.isfile(meta):
                        with open(meta, "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                if line.startswith("Version:"):
                                    ver = line.split(":", 1)[1].strip()
                                    if ver:
                                        return f"{tool_name} {ver}"
            except Exception:
                continue
        return ""
    except Exception:
        return ""

def set_manual_latest(tool_name: str, tag_or_version: str) -> None:
    if AUDIT_DEBUG:
        print(f"# DEBUG: set_manual_latest({tool_name}, {tag_or_version[:50] if tag_or_version else ''}) WRITE_MANUAL={WRITE_MANUAL}", file=sys.stderr, flush=True)
    if not WRITE_MANUAL:
        return
    s = (tag_or_version or "").strip()
    if not s:
        return
    with MANUAL_LOCK:
        load_manual_versions()
        if MANUAL_VERSIONS.get(tool_name) == s:
            return
        MANUAL_VERSIONS[tool_name] = s
        try:
            with open(MANUAL_FILE, "w", encoding="utf-8") as f:
                json.dump(MANUAL_VERSIONS, f, indent=2, ensure_ascii=False, sort_keys=True)
        except Exception:
            pass

def set_manual_method(tool_name: str, method: str) -> None:
    """Persist the upstream lookup method used for a tool into latest_versions.json.

    Stored under the special key "__methods__" as a mapping of tool_name -> method.
    Safe to call repeatedly; only writes when a change is detected.
    """
    try:
        if not method:
            return
        with MANUAL_LOCK:
            load_manual_versions()
            mv = dict(MANUAL_VERSIONS)
            methods = mv.get("__methods__", {})
            if not isinstance(methods, dict):
                methods = {}
            if methods.get(tool_name) == method:
                return
            methods[tool_name] = method
            mv["__methods__"] = methods
            with open(MANUAL_FILE, "w", encoding="utf-8") as f:
                json.dump(mv, f, indent=2, ensure_ascii=False, sort_keys=True)
            MANUAL_VERSIONS.clear()
            MANUAL_VERSIONS.update(mv)
    except Exception:
        pass

# (removed) LATEST_FOR_ALL was unused

try:
    from wcwidth import wcswidth as _wcswidth
except Exception:
    def _wcswidth(s: str) -> int:
        return len(s)


# Removed disk cache in favor of committed manual file updates


@dataclass(frozen=True)
class Tool:
    name: str
    candidates: tuple[str, ...]
    source_kind: str  # "gh" | "pypi" | "crates" | "npm" | "gnu" | "skip"
    source_args: tuple[str, ...]  # e.g., (owner, repo) or (package,) or (crate,) or (npm_pkg,) or (gnu_project,)


# Tools to audit (name, candidates on PATH, source kind and args) in curated order
TOOLS: tuple[Tool, ...] = (
    # 1) Language runtimes & package managers (runtimes first)
    Tool("go", ("go",), "gh", ("golang", "go")),
    Tool("uv", ("uv",), "gh", ("astral-sh", "uv")),
    Tool("python", ("python3", "python"), "gh", ("python", "cpython")),
    Tool("pip", ("pip3", "pip"), "pypi", ("pip",)),
    Tool("pipx", ("pipx",), "pypi", ("pipx",)),
    Tool("poetry", ("poetry",), "pypi", ("poetry",)),
    Tool("rust", ("rustc",), "gh", ("rust-lang", "rust")),
    Tool("node", ("node",), "gh", ("nodejs", "node")),
    Tool("npm", ("npm",), "npm", ("npm",)),
    Tool("pnpm", ("pnpm",), "npm", ("pnpm",)),
    Tool("yarn", ("yarn",), "npm", ("yarn",)),
    # 2) Core developer tools and utilities
    Tool("fd", ("fd", "fdfind"), "gh", ("sharkdp", "fd")),
    Tool("fzf", ("fzf",), "gh", ("junegunn", "fzf")),
    Tool("ctags", ("ctags",), "gh", ("universal-ctags", "ctags")),
    Tool("rga", ("rga",), "gh", ("phiresky", "ripgrep-all")),
    Tool("jq", ("jq",), "gh", ("jqlang", "jq")),
    Tool("yq", ("yq",), "gh", ("mikefarah", "yq")),
    Tool("dasel", ("dasel",), "gh", ("TomWright", "dasel")),
    Tool("sd", ("sd",), "crates", ("sd",)),
    # Distinguish between perl 'prename' (file-rename) and util-linux 'rename.ul'
    Tool("prename", ("file-rename", "rename"), "skip", ()),
    Tool("rename.ul", ("rename.ul",), "skip", ()),
    Tool("sponge", ("sponge",), "skip", ()),
    Tool("xsv", ("xsv",), "crates", ("xsv",)),
    Tool("bat", ("bat", "batcat"), "gh", ("sharkdp", "bat")),
    Tool("delta", ("delta",), "gh", ("dandavison", "delta")),
    Tool("entr", ("entr",), "gh", ("eradman", "entr")),
    Tool("watchexec", ("watchexec", "watchexec-cli"), "gh", ("watchexec", "watchexec")),
    Tool("parallel", ("parallel",), "gnu", ("parallel",)),
    Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep")),
    Tool("ast-grep", ("ast-grep", "sg"), "gh", ("ast-grep", "ast-grep")),
    Tool("httpie", ("http",), "pypi", ("httpie",)),
    Tool("curlie", ("curlie",), "gh", ("rs", "curlie")),
    Tool("direnv", ("direnv",), "gh", ("direnv", "direnv")),
    Tool("dive", ("dive",), "gh", ("wagoodman", "dive")),
    Tool("trivy", ("trivy",), "gh", ("aquasecurity", "trivy")),
    Tool("gitleaks", ("gitleaks",), "gh", ("gitleaks", "gitleaks")),
    Tool("pre-commit", ("pre-commit",), "pypi", ("pre-commit",)),
    Tool("bandit", ("bandit",), "pypi", ("bandit",)),
    Tool("semgrep", ("semgrep",), "pypi", ("semgrep",)),
    # Prefer community package when available; include 'ansible-community' as a candidate
    Tool("ansible", ("ansible", "ansible-community"), "pypi", ("ansible",)),
    Tool("ansible-core", ("ansible", "ansible-core"), "pypi", ("ansible-core",)),
    Tool("git-absorb", ("git-absorb",), "gh", ("tummychow", "git-absorb")),
    Tool("git-branchless", ("git-branchless",), "gh", ("arxanas", "git-branchless")),
    # 3) Formatters & linters
    Tool("black", ("black",), "pypi", ("black",)),
    Tool("isort", ("isort",), "pypi", ("isort",)),
    Tool("flake8", ("flake8",), "pypi", ("flake8",)),
    Tool("eslint", ("eslint",), "gh", ("eslint", "eslint")),
    Tool("prettier", ("prettier",), "gh", ("prettier", "prettier")),
    Tool("shfmt", ("shfmt",), "gh", ("mvdan", "sh")),
    Tool("shellcheck", ("shellcheck",), "gh", ("koalaman", "shellcheck")),
    # 4) JSON/YAML viewers
    Tool("fx", ("fx",), "gh", ("antonmedv", "fx")),
    # 5) VCS & platforms
    Tool("git", ("git",), "gh", ("git", "git")),
    Tool("gh", ("gh",), "gh", ("cli", "cli")),
    Tool("glab", ("glab",), "gh", ("profclems", "glab")),
    # 6) Task runners
    Tool("just", ("just",), "gh", ("casey", "just")),
    # 7) Cloud / infra
    Tool("aws", ("aws",), "gh", ("aws", "aws-cli")),
    Tool("kubectl", ("kubectl",), "gh", ("kubernetes", "kubernetes")),
    Tool("terraform", ("terraform",), "gh", ("hashicorp", "terraform")),
    Tool("docker", ("docker",), "gh", ("docker", "cli")),
    Tool("docker-compose", ("docker-compose", "docker"), "gh", ("docker", "compose")),
)


# Category mapping for table grouping and JSON filtering (local-only UX)
CATEGORY_MAP: dict[str, str] = {
    # Runtimes & package managers
    "go": "runtimes",
    "uv": "runtimes",
    "python": "runtimes",
    "pip": "runtimes",
    "pipx": "runtimes",
    "poetry": "runtimes",
    "rust": "runtimes",
    "node": "runtimes",
    "npm": "runtimes",
    "pnpm": "runtimes",
    "yarn": "runtimes",
    # Search & code-aware tools
    "ripgrep": "search",
    "ast-grep": "search",
    "fzf": "search",
    "fd": "search",
    "rga": "search",
    # Editors/helpers and diffs
    "ctags": "editors",
    "delta": "editors",
    "bat": "editors",
    "just": "task-runners",
    # JSON/YAML processors & viewers
    "jq": "json-yaml",
    "yq": "json-yaml",
    "dasel": "json-yaml",
    "fx": "json-yaml",
    # HTTP/CLI clients
    "httpie": "http",
    "curlie": "http",
    # Watch/run automation
    "entr": "automation",
    "watchexec": "automation",
    "direnv": "automation",
    # Security & compliance
    "semgrep": "security",
    "bandit": "security",
    "gitleaks": "security",
    "trivy": "security",
    # Git helpers
    "git-absorb": "git-helpers",
    "git-branchless": "git-helpers",
    # Formatters & linters
    "black": "formatters",
    "isort": "formatters",
    "flake8": "formatters",
    "eslint": "formatters",
    "prettier": "formatters",
    "shfmt": "formatters",
    "shellcheck": "formatters",
    # VCS & platforms
    "git": "vcs",
    "gh": "vcs",
    "glab": "vcs",
    # Cloud & infra
    "aws": "cloud-infra",
    "kubectl": "cloud-infra",
    "terraform": "cloud-infra",
    "docker": "cloud-infra",
    "docker-compose": "cloud-infra",
    # Others / special
    "xsv": "data",
    "sd": "editors",
    "prename": "editors",
    "rename.ul": "editors",
    "sponge": "editors",
    "ansible": "automation",
    "ansible-core": "automation",
    "dive": "cloud-infra",
}

CATEGORY_ORDER: tuple[str, ...] = (
    "runtimes",
    "search",
    "editors",
    "json-yaml",
    "http",
    "automation",
    "security",
    "git-helpers",
    "formatters",
    "vcs",
    "cloud-infra",
    "task-runners",
    "data",
    "other",
)

HINT_MAP: dict[str, str] = {
    # Python stack
    "python": "make install-python",
    "pip": "make install-python",
    "pipx": "make install-python",
    "poetry": "make install-python",
    "black": "make install-python",
    "isort": "make install-python",
    "flake8": "make install-python",
    "bandit": "make install-python",
    "httpie": "make install-python",
    "pre-commit": "make install-python",
    "semgrep": "make install-python",
    # Node stack
    "node": "make install-node",
    "npm": "make install-node",
    "pnpm": "make install-node",
    "yarn": "make install-node",
    "eslint": "make install-node",
    "prettier": "make install-node",
    # Go
    "go": "make install-go",
    # Rust / core simple tools
    "rust": "make install-rust",
    "fd": "make install-core",
    "fzf": "make install-core",
    "ripgrep": "make install-core",
    "jq": "make install-core",
    "yq": "make install-core",
    "bat": "make install-core",
    "delta": "make install-core",
    "ctags": "make install-core",
    "just": "make install-core",
    "xsv": "make install-core",
    "dasel": "make install-core",
    "sd": "make install-core",
    "entr": "make install-core",
    "watchexec": "make install-core",
    # Cloud/Infra
    "aws": "make install-aws",
    "kubectl": "make install-kubectl",
    "terraform": "make install-terraform",
    "docker": "make install-docker",
    "docker-compose": "make install-docker",
    # Security
    "gitleaks": "make install-core",
    "trivy": "make install-core",
    # Automation / config
    "ansible": "make install-ansible",
    "ansible-core": "make install-ansible",
    # VCS/platforms
    "git": "make install-core",
    "gh": "make install-core",
    "glab": "make install-core",
    # Misc
    "direnv": "make install-core",
    "dive": "make install-core",
}

ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "agent-core": ("ripgrep", "ast-grep", "fd", "fzf", "jq", "yq", "bat", "delta", "just", "ctags", "direnv", "httpie"),
    "python-core": ("python", "pip", "pipx", "poetry", "black", "isort", "flake8", "httpie", "pre-commit", "bandit", "semgrep"),
    "node-core": ("node", "npm", "pnpm", "yarn", "eslint", "prettier"),
    "go-core": ("go",),
    "infra-core": ("aws", "kubectl", "terraform", "docker", "docker-compose", "trivy", "gitleaks", "dive"),
    "data-core": ("jq", "yq", "xsv", "dasel", "fx", "httpie"),
    "security-core": ("semgrep", "bandit", "gitleaks", "trivy"),
    "onboarding-core": ("fd", "fzf", "ripgrep", "jq", "yq", "bat", "delta", "just", "git", "gh"),
}

def category_for(tool_name: str) -> str:
    try:
        return CATEGORY_MAP.get(tool_name, "other")
    except Exception:
        return "other"

def hint_for(tool_name: str) -> str:
    try:
        return HINT_MAP.get(tool_name, "")
    except Exception:
        return ""

def find_paths(command_name: str, deep: bool) -> list[str]:
    paths: list[str] = []
    p = shutil.which(command_name)
    if p:
        paths.append(p)
    # Deep search optionally: enumerate all PATH matches (slower)
    if deep:
        try:
            proc = subprocess.run(
                ["which", "-a", command_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=min(0.2, TIMEOUT_SECONDS),
                check=False,
            )
            for line in (proc.stdout or "").splitlines():
                line = line.strip()
                if line and os.path.isfile(line) and os.access(line, os.X_OK):
                    if line not in paths:
                        paths.append(line)
        except Exception:
            pass
    cargo_path = os.path.join(CARGO_BIN, command_name)
    if os.path.isfile(cargo_path) and os.access(cargo_path, os.X_OK):
        if cargo_path not in paths:
            paths.append(cargo_path)
    return paths


VERSION_FLAG_SETS: tuple[tuple[str, ...], ...] = (
    ("-v",),           # often fastest and prints just the number
    ("--version",),
    ("-V",),
    ("version",),
)


def run_with_timeout(args: Sequence[str]) -> str:
    try:
        proc = subprocess.run(
            list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        return (proc.stdout or "").splitlines()[0].strip()
    except Exception:
        return ""


def get_version_line(path: str, tool_name: str) -> str:
    # Fast-paths first (avoid spawning heavy CLIs where possible)
    # Special-case docker-compose plugin before dpkg checks to avoid misattributing
    # the docker engine version (e.g., 28.x) to compose (2.x).
    if tool_name == "docker-compose":
        try:
            base = os.path.basename(path)
        except Exception:
            base = os.path.basename(path) if path else ""
        # Prefer plugin form when the candidate is the docker binary
        if base == "docker":
            line = run_with_timeout([path, "compose", "version"])
            if line:
                set_local_dc_hint("plugin")
                return line
        # Legacy binary
        line = run_with_timeout([path, "version"])
        if line:
            set_local_dc_hint("legacy")
            return line
    # Special-case rename variants: perl prename (file-rename) and util-linux rename.ul
    if tool_name in ("prename", "rename.ul"):
        try:
            real = os.path.realpath(path)
        except Exception:
            real = path
        base = os.path.basename(real)
        # Perl File::Rename variant (often /usr/bin/file-rename)
        if tool_name == "prename" or base == "file-rename" or "file-rename" in real:
            # Prefer -V, fallback to --version; extract 'File::Rename version X.Y[.Z]'
            for flags in (("-V",), ("--version",)):
                line = run_with_timeout([path, *flags]) or run_with_timeout(["file-rename", *flags]) or run_with_timeout(["rename", *flags])
                if line:
                    m = re.search(r"File::Rename version (\d+(?:\.\d+)+)", line)
                    if m:
                        return f"prename {m.group(1)}"
            # As a last resort, return the first line if it contains a version
            line = run_with_timeout([path, "-V"]) or run_with_timeout(["file-rename", "-V"]) or run_with_timeout(["rename", "-V"]) or ""
            if extract_version_number(line):
                return line
        # util-linux variant (rename.ul)
        if tool_name == "rename.ul" or base == "rename.ul" or "rename.ul" in real:
            for flags in (("--version",), ("-V",), ("-v",), ("version",)):
                line = run_with_timeout([path, *flags])
                if line and extract_version_number(line):
                    return line
        # Otherwise fall through to generic handling (dpkg/etc.)
    # 0) Try dpkg metadata for system-managed binaries
    try:
        dpkg_line = _dpkg_version_line_for_path(tool_name, path)
        if dpkg_line:
            return dpkg_line
    except Exception:
        pass

    # 1) Node package managers: read adjacent package.json when possible
    if tool_name in ("npm", "pnpm", "yarn"):
        line = _node_pkg_version_from_path(tool_name, path)
        if line:
            return line

    # 2) Python console scripts from pipx/venv: read dist-info METADATA
    dist = PYCLI_DISTS.get(tool_name, "")
    if dist:
        line = _python_dist_version_from_venv(tool_name, path, dist)
        if line:
            return line

    # Special cases next
    if tool_name == "shellcheck":
        # ShellCheck prints multi-line banner with a dedicated 'version: X.Y.Z' line when using -V
        # Prefer -V, then --version; return the whole first matching line for consistent display.
        for flags in (("-V",), ("--version",)):
            try:
                proc = subprocess.run(
                    [path, *flags], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=TIMEOUT_SECONDS, check=False
                )
            except Exception:
                continue
            out = (proc.stdout or "").splitlines()
            for line in out:
                if line.lower().startswith("version:"):
                    return line.strip()
            # Fallback: if any line contains a semantic version, return that line
            for line in out:
                if extract_version_number(line):
                    return line.strip()
        return ""
    if tool_name == "go":
        # 'go' reports version via 'go version' (no dashes)
        line = run_with_timeout([path, "version"]) or ""
        if line:
            set_local_flag_hint("go", "version")
            return line
        return ""
    if tool_name == "curlie":
        # Avoid reporting curl's version; try to find curlie version text
        # 1) curlie version
        line = run_with_timeout([path, "version"])
        if line and "curlie" in line.lower() and extract_version_number(line):
            set_local_flag_hint("curlie", "version")
            return line
        # 2) --help/-h: sometimes prints a banner with curlie <ver>
        for flags in (["--help"], ["-h"]):
            line = run_with_timeout([path, *flags])
            if line and "curlie" in line.lower() and extract_version_number(line):
                set_local_flag_hint("curlie", flags[0])
                return line
        # 3) --version: accept only if it mentions curlie; otherwise ignore (it's curl's version)
        line = run_with_timeout([path, "--version"]) or run_with_timeout([path, "-V"]) or ""
        lcline = (line or "").lower()
        if line and "curlie" in lcline and extract_version_number(line):
            set_local_flag_hint("curlie", "--version")
            return line
        # Otherwise, no trustworthy local version string
        return ""
    if tool_name == "sd":
        # Some sd versions do not support -v and print an error like
        # "missing before, after, path" when invoked without required args.
        # Prefer --version and filter out error/usage lines.
        for flags in (("--version",), ("-V",), ("-v",), ("version",)):
            line = run_with_timeout([path, *flags])
            lcline = (line or "").lower()
            if not line:
                continue
            if "missing before, after, path" in lcline or lcline.startswith("error:") or lcline.startswith("usage"):
                continue
            if extract_version_number(line):
                return line
        return ""
    if tool_name == "uv":
        # uv without subcommand prints an error; prefer --version
        line = run_with_timeout([path, "--version"]) or ""
        if line:
            return line
        # Fallback: calling bare uv returns error; ignore error text, not a version
        return ""
    if tool_name == "ansible-core":
        # Extract core version from 'ansible --version' output
        line = run_with_timeout([path, "--version"]) if os.path.basename(path).startswith("ansible") else ""
        # Try 'ansible --version' if path is ansible-core or other
        if not line:
            line = run_with_timeout(["ansible", "--version"]) if shutil.which("ansible") else ""
        if line:
            m = re.search(r"core\s+(\d+\.\d+\.\d+)", line)
            if m:
                return f"ansible-core {m.group(1)}"
        return line
    if tool_name == "fx":
        # Prefer adjacent package.json (Node variant) for instant version read
        try:
            real = os.path.realpath(path)
            pkg = os.path.join(os.path.dirname(real), "package.json")
            if os.path.isfile(pkg):
                with open(pkg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    v = str(data.get("version", "")).strip()
                    if v:
                        return f"fx {v}"
        except Exception:
            pass
        # Fallback to CLI flags (Go variant supports --version/-v or 'version') with a shorter timeout
        pref = get_local_flag_hint("fx")
        ordered: list[list[str]] = []
        if pref in ("--version", "-v", "version"):
            ordered = [[path, pref]]
        else:
            ordered = [[path, "--version"], [path, "-v"], [path, "version"]]
        for args in ordered:
            try:
                proc = subprocess.run(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=min(0.5, TIMEOUT_SECONDS),
                    check=False,
                )
                line = (proc.stdout or "").splitlines()[0].strip()
            except Exception:
                line = ""
            if line and extract_version_number(line):
                if len(args) == 2:
                    set_local_flag_hint("fx", args[1])
                return line
        return ""
    if tool_name == "ansible":
        # Try to get Community package version via the interpreter behind the script
        try:
            py = ""
            try:
                with open(path, "rb") as f:
                    first = f.readline().decode("utf-8", "ignore").strip()
                if first.startswith("#!"):
                    py = first[2:].strip().split()[0]
            except Exception:
                py = ""
            candidates: list[list[str]] = []
            if py:
                candidates.append([py, "-c", "import importlib.metadata as md; print(md.version('ansible'))"])
            # Fallback to current python3 environment
            if shutil.which("python3"):
                candidates.append(["python3", "-c", "import importlib.metadata as md; print(md.version('ansible'))"])
            for args in candidates:
                v = run_with_timeout(args)
                if v and re.match(r"\d+\.\d+\.\d+", v):
                    return f"ansible {v}"
        except Exception:
            pass
        # Last resort: return core line
        line = run_with_timeout([path, "--version"]) or (run_with_timeout(["ansible", "--version"]) if shutil.which("ansible") else "")
        return line
    if tool_name == "sponge":
        # Do not attempt any flags; sponge reads stdin and can block
        return "installed"
    if tool_name == "entr":
        # Prefer -v, then -V, then bare; ignore error/usage and require a version token
        local = get_local_flag_hint("entr")
        order = [[path, "-v"], [path, "-V"], [path]]
        if local == "-V":
            order = [[path, "-V"], [path, "-v"], [path]]
        for args in order:
            line = run_with_timeout(args)
            lcline = (line or "").lower()
            if not line:
                continue
            if lcline.startswith("error:") or "invalid option" in lcline or lcline.startswith("usage"):
                continue
            if extract_version_number(line):
                # remember working flag
                if len(args) == 2:
                    set_local_flag_hint("entr", args[1])
                return line
        return ""
    if tool_name == "kubectl":
        # Prefer client-only flags to avoid contacting the cluster; ignore error lines
        pref = get_local_flag_hint("kubectl")
        candidates = [
            [path, "version", "--client", "--short"],
            [path, "version", "--client"],
            [path, "version", "--client=true"],
            [path, "version"],
        ]
        if pref:
            # move preferred to front
            candidates.sort(key=lambda a: 0 if " ".join(a[1:]) == pref else 1)
        for args in candidates:
            line = run_with_timeout(args)
            lcline = (line or "").lower()
            if not line:
                continue
            if lcline.startswith("error:") or "unknown flag" in lcline or "invalid option" in lcline:
                continue
            # Accept if it looks like a client version line or contains a version
            if "client version" in lcline or VERSION_RE.search(line):
                set_local_flag_hint("kubectl", " ".join(args[1:]))
                return line
    if tool_name == "docker-compose":
        # Fallbacks already attempted above; return empty to continue generic flags if needed
        return ""
    for flags in VERSION_FLAG_SETS:
        local = get_local_flag_hint(tool_name)
        ordered = list(VERSION_FLAG_SETS)
        # Prefer known fast flags for some CLIs
        fast = [tuple([f]) for f in FAST_FLAG_DEFAULTS.get(tool_name, ())]
        if fast:
            # de-duplicate while preserving order
            seen = set()
            pref_order = []
            for t in fast + ordered:
                if t not in seen:
                    seen.add(t)
                    pref_order.append(t)
            ordered = pref_order
        # Learned local flag has highest priority
        if local in ("--version", "-V", "-v", "version"):
            ordered = [tuple([local])] + [t for t in ordered if t != tuple([local])]
        for flags in ordered:
            line = run_with_timeout([path, *flags])
            if not line:
                continue
            lcline = (line or "").lower()
            # Skip obvious error/usage outputs and try next flag
            if (
                lcline.startswith("error:") or
                lcline.startswith("usage") or
                "unknown option" in lcline or
                "unexpected argument" in lcline or
                "requires at least one pattern" in lcline or
                "try --help" in lcline
            ):
                continue
            ver = extract_version_number(line)
            if ver:
                set_local_flag_hint(tool_name, flags[0])
                return line
    return ""


VERSION_RE = re.compile(r"(\d+(?:\.\d+)+)")
DATE_VERSION_RE = re.compile(r"\b(\d{8})\b")


def extract_version_number(s: str) -> str:
    # For kubectl --short, line looks like: 'Client Version: v1.34.0'
    # For typical tools: 'tool v1.2.3' or JSON/YAML; grab first semantic version
    m = VERSION_RE.search(s or "")
    if m:
        return m.group(1)
    # Fallback: handle date-like versions such as 'GNU parallel 20231122'
    m2 = DATE_VERSION_RE.search(s or "")
    return m2.group(1) if m2 else ""


def _format_duration(seconds: float) -> str:
    try:
        if seconds < 1:
            ms = int(seconds * 1000)
            return f"{ms}ms"
        return f"{int(round(seconds))}s"
    except Exception:
        return ""


def status_icon(status: str, installed_line: str) -> str:
    """Return a single-character icon for the installed state/status.

    - ✅ installed and up-to-date
    - ⬆️ installed but outdated
    - ❌ not installed
    - ❓ unknown
    """
    # Prefer fixed-width ASCII to avoid column drift. Emoji can be enabled via CLI_AUDIT_EMOJI=1
    if not USE_EMOJI_ICONS:
        if installed_line == "X" or status == "NOT INSTALLED":
            return "x"
        if status == "UP-TO-DATE":
            return "+"
        if status == "OUTDATED":
            return "!"
        return "?"
    # Emoji mode (may affect width in some terminals)
    if installed_line == "X" or status == "NOT INSTALLED":
        return "❌"
    if status == "UP-TO-DATE":
        return "✅"
    if status == "OUTDATED":
        return "🔼"
    return "❓"


def _classify_install_method(path: str, tool_name: str) -> tuple[str, str]:
    """Return (method, reason) for install classification."""
    try:
        home = os.path.expanduser("~")
        if not path:
            return "", "no-path"
        try:
            real = os.path.realpath(path)
        except Exception:
            real = path
        p = real or path
        if tool_name == "python":
            if "/.venvs/" in p:
                return "uv venv", "shebang-in-~/.venvs"
            if any(t in p for t in ("/.local/share/uv/", "/.cache/uv/", "/.uv/")):
                return "uv python", "path-contains-uv-python"
        if tool_name and _is_uv_tool(tool_name):
            return "uv tool", "uv-list-match"
        if any(t in p for t in ("/.local/share/uv/", "/.cache/uv/", "/.uv/")):
            return "uv tool", "path-contains-uv"
        if tool_name == "docker" and DOCKER_INFO_ENABLED:
            wsl = bool(os.environ.get("WSL_DISTRO_NAME", ""))
            info = run_with_timeout(["docker", "info", "--format", "{{.OperatingSystem}}"])
            if info and "Docker Desktop" in info:
                return ("docker-desktop (WSL)" if wsl else "docker-desktop"), "docker-info-os"
        if p.startswith(os.path.join(home, ".nvm")):
            return "nvm/npm", "path-under-~/.nvm"
        if "/.cache/corepack" in p or "/.corepack" in p:
            return "corepack", "path-corepack"
        if tool_name == "docker-compose" and DOCKER_INFO_ENABLED:
            wsl = bool(os.environ.get("WSL_DISTRO_NAME", ""))
            info = run_with_timeout(["docker", "info", "--format", "{{.OperatingSystem}}"])
            if info and "Docker Desktop" in info:
                return ("docker-desktop (WSL)" if wsl else "docker-desktop"), "docker-info-os"
        if tool_name == "uv":
            try:
                real = os.path.realpath(path)
            except Exception:
                real = path
            official_bin = os.path.join(home, ".local", "bin", "uv")
            if real == official_bin:
                return "github binary", "official-installer"
            if "/pipx/venvs/uv/" in real or real.startswith(os.path.join(home, ".local", "pipx", "venvs", "uv")):
                return "pipx/user", "pipx-uv-venv"
        if p.startswith(os.path.join(home, ".pnpm")):
            return "pnpm", "path-under-~/.pnpm"
        if p.startswith(os.path.join(home, ".yarn")):
            return "yarn", "path-under-~/.yarn"
        # asdf shims/installs
        if p.startswith(os.path.join(home, ".asdf", "shims")) or "/.asdf/installs/" in p:
            return "asdf", "asdf-shim-or-install"
        # nodenv shims/versions
        if p.startswith(os.path.join(home, ".nodenv", "shims")) or "/.nodenv/versions/" in p:
            return "nodenv", "nodenv-shim-or-version"
        # pyenv shims/versions
        if p.startswith(os.path.join(home, ".pyenv", "shims")) or "/.pyenv/versions/" in p:
            return "pyenv", "pyenv-shim-or-version"
        # rbenv shims/versions
        if p.startswith(os.path.join(home, ".rbenv", "shims")) or "/.rbenv/versions/" in p:
            return "rbenv", "rbenv-shim-or-version"
        # Volta (Node toolchain manager)
        if p.startswith(os.path.join(home, ".volta")) or "/.volta/" in p:
            return "volta", "path-under-~/.volta"
        # SDKMAN!
        if "/.sdkman/" in p:
            return "sdkman", "path-contains-~/.sdkman"
        # nodist (Windows node manager; rare under WSL)
        if "/.nodist/" in p or "/Nodist/" in p or "/NODIST/" in p:
            return "nodist", "path-contains-nodist"
        if "/lib/node_modules/" in p:
            if p.startswith(os.path.join(home, ".local", "lib", "node_modules")):
                return "npm (user)", "path-under-~/.local/lib/node_modules"
            if p.startswith("/usr/local/lib/node_modules") or p.startswith("/usr/lib/node_modules"):
                return "npm (global)", "path-under-/usr/local/lib/node_modules"
        gobin = os.environ.get("GOBIN", "").strip()
        if gobin and p.startswith(gobin):
            return "go install", "path-under-GOBIN"
        gopath = os.environ.get("GOPATH", os.path.join(home, "go"))
        if p.startswith(os.path.join(gopath, "bin")):
            return "go install", "path-under-GOPATH/bin"
        if p.startswith(os.path.join(home, ".cargo", "bin")):
            return "rustup/cargo", "path-under-~/.cargo/bin"
        if any(t in p for t in ("/.local/share/pipx/venvs/", "/.local/pipx/venvs/")):
            return "pipx/user", "path-under-pipx-venvs"
        if p.startswith(os.path.join(home, ".local", "bin")):
            # Refine ~/.local/bin classification via shebang to detect pipx/uv venv wrappers
            try:
                with open(p, "rb") as f:
                    first = f.readline().decode("utf-8", "ignore").strip()
                if first.startswith("#!"):
                    py = first[2:].strip().split()[0]
                else:
                    py = ""
            except Exception:
                py = ""
            if py:
                if "/pipx/venvs/" in py or "/.local/pipx/venvs/" in py:
                    return "pipx/user", "shebang-pipx-venv"
                if "/.venvs/" in py:
                    return "uv venv", "shebang-in-~/.venvs"
                if any(t in py for t in ("/.local/share/uv/", "/.cache/uv/", "/.uv/")):
                    return "uv tool", "shebang-uv"
            return os.path.join(home, ".local", "bin"), "path-under-~/.local/bin"
        if "/snap/" in p:
            return "snap", "path-contains-snap"
        # Homebrew (macOS and Linuxbrew). Prefer env hints when available.
        hb_prefix = os.environ.get("HOMEBREW_PREFIX", "").strip()
        hb_cellar = os.environ.get("HOMEBREW_CELLAR", "").strip()
        if (hb_prefix and p.startswith(hb_prefix)) or (hb_cellar and hb_cellar in p) or \
           ("/home/linuxbrew/.linuxbrew" in p) or ("/opt/homebrew" in p) or ("/usr/local/Cellar" in p):
            return "homebrew", "brew-prefix-or-cellar"
        if p.startswith("/usr/local/bin"):
            return "/usr/local/bin", "path-under-/usr/local/bin"
        if p.startswith("/usr/bin") or p.startswith("/bin"):
            global DPKG_CACHE
            if p in DPKG_CACHE:
                return ("apt/dpkg" if DPKG_CACHE[p] else "/usr/bin"), "dpkg-cache-hit"
            line = run_with_timeout(["dpkg", "-S", p])
            owned = bool(line)
            DPKG_CACHE[p] = owned
            if len(DPKG_CACHE) > DPKG_CACHE_LIMIT:
                try:
                    DPKG_CACHE.pop(next(iter(DPKG_CACHE)))
                except Exception:
                    pass
            return ("apt/dpkg" if owned else "/usr/bin"), "dpkg-query"
        return "unknown", "no-match"
    except Exception as e:
        if AUDIT_DEBUG:
            print(f"# DEBUG: detect_install_method error for {tool_name} at {path}: {e}", file=sys.stderr)
        return "unknown", "error"


def detect_install_method(path: str, tool_name: str) -> str:
    method, _reason = _classify_install_method(path, tool_name)
    return method


def upstream_method_for(tool: Tool) -> str:
    # Special-case Yarn: use Yarn's official tags feed rather than npm package
    if tool.name == "yarn":
        return "yarn-tags"
    kind = tool.source_kind
    if kind == "pypi":
        # Prefer uv tool as the standard for Python CLIs
        return "uv tool"
    if kind == "crates":
        return "cargo"
    if kind == "npm":
        return "npm (nvm)"
    if kind == "gh":
        return "github"
    if kind == "gnu":
        return "gnu-ftp"
    return ""


def tool_homepage_url(tool: Tool) -> str:
    kind = tool.source_kind
    args = tool.source_args
    try:
        if kind == "gh":
            owner, repo = args  # type: ignore[misc]
            return f"https://github.com/{owner}/{repo}"
        if kind == "pypi":
            (pkg,) = args  # type: ignore[misc]
            return f"https://pypi.org/project/{pkg}/"
        if kind == "crates":
            (crate,) = args  # type: ignore[misc]
            return f"https://crates.io/crates/{crate}"
        if kind == "npm":
            (pkg,) = args  # type: ignore[misc]
            return f"https://www.npmjs.com/package/{pkg}"
        if kind == "gnu":
            (proj,) = args  # type: ignore[misc]
            return f"https://ftp.gnu.org/gnu/{proj}/"
        return ""
    except Exception:
        return ""


def latest_target_url(tool: Tool, latest_tag: str, latest_num: str) -> str:
    kind = tool.source_kind
    args = tool.source_args
    try:
        if kind == "gh":
            owner, repo = args  # type: ignore[misc]
            if latest_tag:
                return f"https://github.com/{owner}/{repo}/releases/tag/{latest_tag}"
            return f"https://github.com/{owner}/{repo}/releases/latest"
        if kind == "pypi":
            (pkg,) = args  # type: ignore[misc]
            return f"https://pypi.org/project/{pkg}/"
        if kind == "crates":
            (crate,) = args  # type: ignore[misc]
            return f"https://crates.io/crates/{crate}"
        if kind == "npm":
            (pkg,) = args  # type: ignore[misc]
            return f"https://www.npmjs.com/package/{pkg}"
        if kind == "gnu":
            (proj,) = args  # type: ignore[misc]
            return f"https://ftp.gnu.org/gnu/{proj}/"
        return ""
    except Exception:
        return ""


def osc8(url: str, text: str) -> str:
    """Wrap text in OSC 8 hyperlink if url is provided and links are enabled."""
    if not url or not ENABLE_LINKS:
        return text
    # ESC ]8;;URI ESC \ TEXT ESC ]8;; ESC \
    return f"\x1b]8;;{url}\x1b\\{text}\x1b]8;;\x1b\\"


def choose_highest(installed: list[tuple[str, str, str]]) -> tuple[str, str, str] | tuple[()]:
    """
    installed: list of (num, line, path). Return the tuple with highest numeric version.
    If none have a numeric version, return the first non-empty tuple, else ().
    """
    with_nums = [(tuple(map(int, n.split("."))), n, line, p) for n, line, p in installed if n]
    if with_nums:
        # Choose earliest discovery for the highest version (preserves PATH order)
        max_tuple = max(t[0] for t in with_nums)
        for num_tuple, n, line, p in with_nums:
            if num_tuple == max_tuple:
                return n, line, p
    for n, line, p in installed:
        if line:
            return n, line, p
    return ()


def choose_node_preferred(installed: list[tuple[str, str, str]]) -> tuple[str, str, str] | tuple[()]:
    """Prefer the Node.js binary a user would actually execute.

    Strategy:
    - If any candidate path lives under ~/.nvm, pick the first such entry (PATH order).
    - Else, pick the first entry with a non-empty line (PATH order).
    - Fallback to highest numeric version if nothing matched.
    """
    try:
        home = os.path.expanduser("~")
        nvm_root = os.path.join(home, ".nvm")
        for n, line, path in installed:
            if path and path.startswith(nvm_root) and line:
                return n, line, path
        for n, line, path in installed:
            if line:
                return n, line, path
        # Last resort
        return choose_highest(installed)
    except Exception:
        return choose_highest(installed)


def http_get(url: str) -> bytes:
    """Compatibility wrapper that delegates to http_fetch with sensible defaults."""
    return http_fetch(url, timeout=TIMEOUT_SECONDS)


def latest_github(owner: str, repo: str) -> tuple[str, str]:
    if OFFLINE_MODE:
        return "", ""
    # Always prefer the releases/latest redirect (skips pre-releases)
    try:
        url = f"https://github.com/{owner}/{repo}/releases/latest"
        if AUDIT_DEBUG:
            print(f"# DEBUG: GitHub HEAD {url} (timeout={TIMEOUT_SECONDS}s)", file=sys.stderr, flush=True)
        req = urllib.request.Request(url, headers=USER_AGENT_HEADERS, method="HEAD")
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
        req_start = time.time()
        resp = opener.open(req, timeout=TIMEOUT_SECONDS)
        req_dur = int((time.time() - req_start) * 1000)
        if AUDIT_DEBUG:
            print(f"# DEBUG: GitHub HEAD response ({req_dur}ms, redirect to {resp.geturl()})", file=sys.stderr, flush=True)
        final = resp.geturl()
        last = final.rsplit("/", 1)[-1]
        if last and last.lower() not in ("releases", "latest"):
            tag = last.strip()
            result = (tag, extract_version_number(tag))
            set_manual_latest(repo, tag)
            set_hint(f"gh:{owner}/{repo}", "latest_redirect")
            return result
    except Exception:
        pass
    # Fallback to GitHub API releases/latest (also non-prerelease)
    try:
        data = json.loads(http_get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest"))
        tag = (data.get("tag_name") or "").strip()
        if tag and tag.lower() not in ("releases", "latest"):
            result = (tag, extract_version_number(tag))
            set_manual_latest(repo, tag)
            set_hint(f"gh:{owner}/{repo}", "releases_api")
            return result
    except Exception:
        pass
    # Special-case: golang/go has no GitHub releases; filter stable tags only
    try:
        if owner == "golang" and repo == "go":
            if AUDIT_DEBUG:
                print(f"# DEBUG: Processing golang/go tags (special case)", file=sys.stderr, flush=True)
            # Fetch up to 200 tags (2 pages) and choose the highest stable goX[.Y][.Z] tag
            best: tuple[tuple[int, ...], str, str] | None = None
            for page in (1, 2):
                data = json.loads(http_get(f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=100&page={page}"))
                if not isinstance(data, list):
                    break
                if AUDIT_DEBUG:
                    print(f"# DEBUG: Processing page {page} with {len(data)} tags", file=sys.stderr, flush=True)
                for item in data:
                    name = (item.get("name") or "").strip()
                    # Accept only stable tags like go1.25 or go1.25.1; exclude weekly/beta/rc
                    if not re.match(r"^go\d+(?:\.\d+){1,2}$", name):
                        continue
                    ver = extract_version_number(name)
                    if not ver:
                        continue
                    try:
                        nums = tuple(int(x) for x in ver.split("."))
                    except Exception:
                        continue
                    tup = (nums, name, ver)
                    if best is None or tup[0] > best[0]:
                        best = tup
                # If we already found a good candidate on the first page, stop early
                if best is not None:
                    break
            if AUDIT_DEBUG:
                print(f"# DEBUG: Best go tag found: {best}", file=sys.stderr, flush=True)
            if best is not None:
                _, tag_name, ver_num = best
                result = (tag_name, ver_num)
                if AUDIT_DEBUG:
                    print(f"# DEBUG: Calling set_manual_latest({repo}, {tag_name})", file=sys.stderr, flush=True)
                set_manual_latest(repo, tag_name)
                if AUDIT_DEBUG:
                    print(f"# DEBUG: Calling set_hint(gh:{owner}/{repo}, tags_api)", file=sys.stderr, flush=True)
                set_hint(f"gh:{owner}/{repo}", "tags_api")
                if AUDIT_DEBUG:
                    print(f"# DEBUG: Returning result for go: {result}", file=sys.stderr, flush=True)
                return result
    except Exception:
        pass
    # Fallbacks for rare cases
    try:
        data = json.loads(http_get(f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=1"))
        if isinstance(data, list) and data:
            tag = (data[0].get("name") or "").strip()
            if tag:
                result = (tag, extract_version_number(tag))
                set_manual_latest(repo, tag)
                set_hint(f"gh:{owner}/{repo}", "tags_api")
                return result
    except Exception:
        pass
    try:
        atom = http_get(f"https://github.com/{owner}/{repo}/releases.atom").decode("utf-8", "ignore")
        m = re.search(r"/releases/tag/([^<\"]+)", atom)
        if m:
            tag = m.group(1).strip()
            if tag and tag.lower() not in ("releases", "latest"):
                result = (tag, extract_version_number(tag))
                set_manual_latest(repo, tag)
                set_hint(f"gh:{owner}/{repo}", "atom")
                return result
    except Exception:
        pass
    return "", ""


def latest_pypi(package: str) -> tuple[str, str]:
    if OFFLINE_MODE:
        return "", ""
    try:
        data = json.loads(http_get(f"https://pypi.org/pypi/{package}/json"))
        v = data.get("info", {}).get("version", "")
        result = (v, extract_version_number(v))
        set_manual_latest(package, v)
        return result
    except Exception:
        return "", ""


def latest_crates(crate: str) -> tuple[str, str]:
    if OFFLINE_MODE:
        return "", ""
    try:
        data = json.loads(http_get(f"https://crates.io/api/v1/crates/{crate}"))
        v = data.get("crate", {}).get("max_version", "")
        result = (v, extract_version_number(v))
        set_manual_latest(crate, v)
        return result
    except Exception:
        return "", ""


def latest_npm(package: str) -> tuple[str, str]:
    """Return (tag, version) for latest from npm registry.

    Uses the dist-tags.latest and falls back to time/latest if available.
    """
    if OFFLINE_MODE:
        return "", ""
    # Yarn is distributed via Yarn's own tag feed for modern releases; prefer that
    if package == "yarn":
        tag, num = latest_yarn()
        if tag or num:
            return tag, num
    try:
        data = json.loads(http_get(f"{NPM_REGISTRY_URL}/{package}"))
        # Prefer 'stable' for yarn (Berry v4+) and 'latest' for others
        dist_tags = data.get("dist-tags", {})
        if package == "yarn":
            preferred = dist_tags.get("stable") or dist_tags.get("latest", "")
        else:
            preferred = dist_tags.get("latest", "")
        if preferred:
            result = (preferred, extract_version_number(preferred))
            set_manual_latest(package, preferred)
            return result
        # Fallback: engines or versions keys are large; refrain to keep it light
        return "", ""
    except Exception:
        return "", ""


def latest_yarn() -> tuple[str, str]:
    """Get latest Yarn (Berry) version from official tags feed, fallback to GitHub.

    Primary source: https://repo.yarnpkg.com/tags (JSON or simple text)
    Fallback: GitHub releases for yarnpkg/berry.
    """
    if OFFLINE_MODE:
        return "", ""
    try:
        raw = http_get("https://repo.yarnpkg.com/tags")
        text = raw.decode("utf-8", "ignore").strip()
        v = ""
        # Try JSON first
        try:
            data = json.loads(text)
            v = str(data.get("stable", "") or data.get("latest", "")).strip()
        except Exception:
            pass
        if not v:
            # Fallback: regex parse for 'stable: 4.9.4' or '"stable": "4.9.4"'
            m = re.search(r'"?stable"?\s*[:=]\s*"?([0-9]+(?:\.[0-9]+)+)"?', text)
            if m:
                v = m.group(1)
        if v:
            set_manual_latest("yarn", v)
            return v, extract_version_number(v)
    except Exception:
        pass
    # Fallback: GitHub releases
    tag, num = latest_github("yarnpkg", "berry")
    return tag, num


def latest_gnu(project: str) -> tuple[str, str]:
    """Return latest tarball version by listing GNU FTP directory.

    Example for GNU parallel: https://ftp.gnu.org/gnu/parallel/
    We parse filenames like parallel-YYYYMMDD.tar.bz2 or project-X.Y.tar.*
    """
    if OFFLINE_MODE:
        return "", ""
    try:
        def parse_dir(html: str) -> tuple[str, str]:
            # 1) LATEST-IS-* marker
            m_latest = re.search(r"LATEST-IS-((?:\d+(?:\.\d+)+)|\d{8})", html)
            if m_latest:
                tag = m_latest.group(1)
                return tag, (extract_version_number(tag) or tag)
            # 2) tarball names
            versions = re.findall(
                rf"{re.escape(project)}-((?:\d+(?:\.\d+)+)|\d{{8}})\.tar\.(?:gz|bz2|xz|zst)(?:\.sig)?",
                html,
            )
            if not versions:
                return "", ""
            def keyify(v: str):
                if re.fullmatch(r"[0-9]{8}", v):
                    return (0, (int(v),))
                parts = tuple(int(x) for x in v.split("."))
                return (1, parts)
            versions.sort(key=lambda v: keyify(v))
            latest_v = versions[-1]
            return latest_v, (extract_version_number(latest_v) or latest_v)

        # Try canonical directory
        html = http_get(f"https://ftp.gnu.org/gnu/{project}/").decode("utf-8", "ignore")
        # 1) Prefer LATEST-IS-* hint if present
        tag, num = parse_dir(html)
        if not tag:
            # Try sorted listing query
            html = http_get(f"https://ftp.gnu.org/gnu/{project}/?C=M;O=D").decode("utf-8", "ignore")
            tag, num = parse_dir(html)
        if not tag:
            # Try mirror
            html = http_get(f"https://ftpmirror.gnu.org/gnu/{project}/").decode("utf-8", "ignore")
            tag, num = parse_dir(html)
        if not tag:
            # Try kernel mirror
            html = http_get(f"https://mirrors.kernel.org/gnu/{project}/").decode("utf-8", "ignore")
            tag, num = parse_dir(html)
        if not tag:
            return "", ""
        result = (tag, num)
        set_manual_latest(project, tag)
        return result
    except Exception:
        return "", ""


def _uv_primary_python() -> tuple[str, str, str] | tuple[()]:
    """Prefer the uv-managed Python interpreter if available.

    Order of preference:
    1) ~/.venvs/dev/bin/python (created by scripts/install_python.sh)
    2) Interpreter resolved by `uv python find 3`
    Returns a tuple (num, line, path) matching the audit format, or () if not found.
    """
    try:
        if not shutil.which("uv"):
            return ()
        home = os.path.expanduser("~")
        # 1) Preferred dev venv interpreter
        venv_py = os.path.join(home, ".venvs", "dev", "bin", "python")
        if os.path.isfile(venv_py) and os.access(venv_py, os.X_OK):
            line = run_with_timeout([venv_py, "--version"]) or ""
            num = extract_version_number(line)
            if num:
                return num, line, venv_py
        # 2) Fallback to uv's resolved Python for the 3.x line
        py_path = run_with_timeout(["uv", "python", "find", "3"]) or ""
        if py_path and os.path.isabs(py_path) and os.path.exists(py_path):
            line = run_with_timeout([py_path, "--version"]) or ""
            num = extract_version_number(line)
            if num:
                return num, line, py_path
    except Exception:
        pass
    return ()


def get_latest(tool: Tool) -> tuple[str, str]:
    kind = tool.source_kind
    args = tool.source_args
    # Manual file baseline first
    man_tag, man_num = get_manual_latest(tool.name)
    manual_available = bool(man_tag or man_num)
    used_manual = False
    if OFFLINE_MODE:
        # Offline: return manual if present, else empty
        if manual_available:
            MANUAL_USED[tool.name] = True
            return man_tag, man_num
        MANUAL_USED[tool.name] = True
        return "", ""
    # Manual-first mode: always return manual if available
    if MANUAL_FIRST and manual_available and not OFFLINE_MODE:
        MANUAL_USED[tool.name] = True
        return man_tag, man_num
    # Online: if manual exists use it as baseline when network fails
    if kind == "gh":
        owner, repo = args  # type: ignore[misc]
        tag, num = latest_github(owner, repo)
        if tag or num:
            MANUAL_USED[tool.name] = False
            set_manual_method(tool.name, "github")
            return tag, num
        if manual_available:
            MANUAL_USED[tool.name] = True
            return man_tag, man_num
        MANUAL_USED[tool.name] = False
        return tag, num
    if kind == "pypi":
        (pkg,) = args  # type: ignore[misc]
        tag, num = latest_pypi(pkg)
        if tag or num:
            MANUAL_USED[tool.name] = False
            set_manual_method(tool.name, "pypi")
            return tag, num
        if manual_available:
            MANUAL_USED[tool.name] = True
            return man_tag, man_num
        MANUAL_USED[tool.name] = False
        return tag, num
    if kind == "crates":
        (crate,) = args  # type: ignore[misc]
        tag, num = latest_crates(crate)
        if tag or num:
            MANUAL_USED[tool.name] = False
            set_manual_method(tool.name, "crates")
            return tag, num
        if manual_available:
            MANUAL_USED[tool.name] = True
            return man_tag, man_num
        MANUAL_USED[tool.name] = False
        return tag, num
    if kind == "npm":
        (pkg,) = args  # type: ignore[misc]
        tag, num = latest_npm(pkg)
        if tag or num:
            MANUAL_USED[tool.name] = False
            # yarn uses yarn-tags via latest_npm() fallback logic
            meth = "yarn-tags" if pkg == "yarn" else "npm"
            set_manual_method(tool.name, meth)
            return tag, num
        if manual_available:
            MANUAL_USED[tool.name] = True
            return man_tag, man_num
        MANUAL_USED[tool.name] = False
        return tag, num
    if kind == "gnu":
        (proj,) = args  # type: ignore[misc]
        tag, num = latest_gnu(proj)
        if tag or num:
            MANUAL_USED[tool.name] = False
            set_manual_method(tool.name, "gnu-ftp")
            return tag, num
        if manual_available:
            MANUAL_USED[tool.name] = True
            return man_tag, man_num
        MANUAL_USED[tool.name] = False
        return tag, num
    return "", ""


def audit_tool(tool: Tool) -> tuple[str, str, str, str, str, str, str, str]:
    # Debug: show when tool audit starts
    if AUDIT_DEBUG:
        print(f"# DEBUG: START audit_tool({tool.name}) source={tool.source_kind} offline={OFFLINE_MODE}", file=sys.stderr, flush=True)

    # Detect installed candidates
    t0_inst = time.time()
    candidates = tool.candidates
    tuples: list[tuple[str, str, str]] = []  # (num, line, path)
    any_found = False
    # Use shallow discovery for most tools (first match); deep only for special cases
    deep_scan = (tool.name == "node")  # prefer to find both system and nvm variants
    chosen: tuple[str, str, str] | tuple[()] = ()
    # Prefer uv-managed Python as the authoritative interpreter when available
    if tool.name == "python":
        uv_choice = _uv_primary_python()
        if uv_choice:
            chosen = uv_choice
    # Only fall back to PATH scanning if we didn't select a uv choice
    if not chosen:
        if AUDIT_DEBUG:
            print(f"# DEBUG: Scanning PATH for {tool.name} candidates: {candidates}", file=sys.stderr, flush=True)
        for cand in candidates:
            if AUDIT_DEBUG:
                print(f"# DEBUG: Searching for candidate: {cand}", file=sys.stderr, flush=True)
            for path in find_paths(cand, deep=deep_scan):
                any_found = True
                if AUDIT_DEBUG:
                    print(f"# DEBUG: Found path: {path}, getting version...", file=sys.stderr, flush=True)
                line = get_version_line(path, tool.name)
                if AUDIT_DEBUG:
                    print(f"# DEBUG: Version line: {line}", file=sys.stderr, flush=True)
                num = extract_version_number(line)
                tuples.append((num, line, path))
                # Fast exit for fx once we have a version line
                if tool.name == "fx" and num:
                    break
            if tool.name == "fx" and tuples:
                break
        if any_found:
            if tool.name == "node":
                chosen = choose_node_preferred(tuples)
            else:
                chosen = choose_highest(tuples)
        else:
            chosen = ()
    if not chosen:
        installed_line = "X"
        installed_num = ""
        installed_path = ""
    else:
        installed_num, installed_line, installed_path = chosen

    t1_inst = time.time()
    latest_start = time.time()

    # Debug: show network call about to happen
    if AUDIT_DEBUG:
        print(f"# DEBUG: NETWORK get_latest({tool.name}) source={tool.source_kind} offline={OFFLINE_MODE}", file=sys.stderr, flush=True)

    latest_tag, latest_num = get_latest(tool)
    latest_end = time.time()

    # Debug: show network call completed
    if AUDIT_DEBUG:
        dur_ms = int((latest_end - latest_start) * 1000)
        print(f"# DEBUG: DONE get_latest({tool.name}) dur={dur_ms}ms tag='{latest_tag}' num='{latest_num}'", file=sys.stderr, flush=True)
    # Slow operation trace
    dur_ms = int((latest_end - latest_start) * 1000)
    if dur_ms >= SLOW_MS:
        _vlog(f"# slow latest tool={tool.name} dur={dur_ms}ms method={upstream_method_for(tool)} offline={OFFLINE_MODE}")

    if installed_line == "X":
        status = "NOT INSTALLED"
    else:
        inst_num = extract_version_number(installed_line)
        if inst_num and latest_num:
            status = "UP-TO-DATE" if inst_num == latest_num else "OUTDATED"
        elif inst_num and not latest_num:
            status = "UNKNOWN"
        else:
            status = "UNKNOWN"

    # Sanitize latest display to numeric (like installed)
    if latest_num:
        latest_display = latest_num
    elif latest_tag:
        latest_display = extract_version_number(latest_tag) or ("" if latest_tag.lower() in ("releases", "latest") else latest_tag)
    else:
        latest_display = ""
    latest_url = latest_target_url(tool, latest_tag, latest_num)
    # Determine install method and remember selected path/reason for JSON
    if installed_line != "X":
        try:
            method, reason = _classify_install_method(installed_path, tool.name)
        except Exception:
            method, reason = detect_install_method(installed_path, tool.name), ""
        installed_method = method
        SELECTED_PATHS[tool.name] = installed_path
        SELECTED_REASON[tool.name] = reason
    else:
        installed_method = ""
        SELECTED_PATHS[tool.name] = ""
        SELECTED_REASON[tool.name] = ""
    upstream_method = "manual" if MANUAL_USED.get(tool.name) else upstream_method_for(tool)
    homepage_url = tool_homepage_url(tool)
    # Shorten installed column to numeric version if available; empty if not installed
    if installed_line == "X":
        installed_display = ""
    elif installed_num:
        installed_display = installed_num
    else:
        installed_display = installed_line
    if SHOW_TIMINGS:
        # Show timing even when not installed
        if installed_display:
            installed_display = installed_display + f" ({_format_duration(t1_inst - t0_inst)})"
        else:
            installed_display = f"({ _format_duration(t1_inst - t0_inst) })".strip()
        latest_display = (latest_display + f" ({_format_duration(latest_end - latest_start)})") if latest_display else latest_display
    return tool.name, installed_display, installed_method, latest_display, upstream_method, status, homepage_url, latest_url


def _parse_tool_filter(argv: Sequence[str]) -> list[str]:
    """Parse optional tool filters from CLI args or env.

    Supports:
    - positional tool names: cli_audit.py jq yq
    - --only / --tool flags with one or more names
    - env CLI_AUDIT_ONLY (comma or space separated)
    """
    try:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("tools", nargs="*")
        parser.add_argument("--only", dest="only", nargs="+")
        parser.add_argument("--tool", dest="only", nargs="+")
        ns, _ = parser.parse_known_args(list(argv))
        names: list[str] = []
        if getattr(ns, "only", None):
            names.extend(ns.only)
        if getattr(ns, "tools", None):
            names.extend(ns.tools)
        env = os.environ.get("CLI_AUDIT_ONLY", "").strip()
        if env:
            # allow comma and/or whitespace separated
            for part in re.split(r"[\s,]+", env):
                part = part.strip()
                if part:
                    names.append(part)
        # FAST_MODE: default to a small subset when no filters provided
        if FAST_MODE and not names:
            names = ["agent-core"]
        # Expand friendly aliases like 'python-core' into explicit tool lists
        expanded: list[str] = []
        for n in names:
            key = n.lower()
            if key in ALIAS_MAP:
                expanded.extend(ALIAS_MAP[key])
            else:
                expanded.append(key)
        # normalize and de-duplicate preserving order
        seen = set()
        filtered: list[str] = []
        for n in expanded:
            key = n.lower()
            if key not in seen:
                seen.add(key)
                filtered.append(key)
        return filtered
    except Exception:
        return []


def _render_only_mode() -> int:
    """Fast path: render audit results from snapshot without live checks."""
    # Friendly startup message for UX
    snap_file = os.environ.get("CLI_AUDIT_SNAPSHOT_FILE", "tools_snapshot.json")
    if os.path.exists(snap_file):
        meta = {}
        try:
            with open(snap_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                meta = data.get("__meta__", {})
        except Exception:
            pass
        tool_count = meta.get("count", "~50")
        age = meta.get("collected_at", "")
        if age:
            try:
                from datetime import datetime
                collected_dt = datetime.fromisoformat(age)
                now = datetime.now(collected_dt.tzinfo)
                age_seconds = (now - collected_dt).total_seconds()
                if age_seconds < 60:
                    age_str = "just now"
                elif age_seconds < 3600:
                    age_str = f"{int(age_seconds / 60)}m ago"
                elif age_seconds < 86400:
                    age_str = f"{int(age_seconds / 3600)}h ago"
                else:
                    age_str = f"{int(age_seconds / 86400)}d ago"
            except Exception:
                age_str = "cached"
        else:
            age_str = "cached"
        print(f"# Auditing {tool_count} development tools from snapshot ({age_str})...", file=sys.stderr)
    else:
        print(f"# No snapshot found - run 'make update' to collect fresh data", file=sys.stderr)
    print("", file=sys.stderr)  # Blank line to separate informational message from table output

    snap = load_snapshot()
    selected_names = _parse_tool_filter(sys.argv[1:])
    selected_set = set(selected_names) if selected_names else None
    rows = render_from_snapshot(snap, selected_set)

    # JSON output from snapshot
    if os.environ.get("CLI_AUDIT_JSON", "0") == "1":
        payload = []
        for name, installed, installed_method, latest, upstream_method, status, tool_url, latest_url in rows:
            payload.append({
                "tool": name,
                "category": category_for(name),
                "installed": installed,
                "installed_method": installed_method,
                "installed_version": extract_version_number(installed),
                "latest_version": extract_version_number(latest),
                "latest_upstream": latest,
                "upstream_method": upstream_method,
                "status": status,
                "tool_url": tool_url,
                "latest_url": latest_url,
                "state_icon": status_icon(status, installed),
                "is_up_to_date": (status == "UP-TO-DATE"),
            })
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    # Table output from snapshot
    headers = (" ", "tool", "installed", "installed_method", "latest_upstream", "upstream_method")
    print("|".join(headers))
    for name, installed, installed_method, latest, upstream_method, status, tool_url, latest_url in rows:
        icon = status_icon(status, installed)
        print("|".join((icon, name, installed, installed_method, latest, upstream_method)))

    # Summary line from snapshot meta if present
    try:
        meta = snap.get("__meta__", {})
        total = meta.get("count", len(rows))
        missing = sum(1 for r in rows if r[5] == "NOT INSTALLED")
        outdated = sum(1 for r in rows if r[5] == "OUTDATED")
        unknown = sum(1 for r in rows if r[5] == "UNKNOWN")
        offline_tag = " (offline)" if meta.get("offline") else ""
        print(f"\nReadiness{offline_tag}: {total} tools, {outdated} outdated, {missing} missing, {unknown} unknown", file=sys.stderr)
    except Exception:
        pass
    return 0


def main() -> int:
    # RENDER-ONLY mode: bypass live audit entirely, render from snapshot (FAST PATH)
    if RENDER_ONLY:
        return _render_only_mode()

    # Determine selected tools (optional filtering)
    selected_names = _parse_tool_filter(sys.argv[1:])
    # Optional alphabetical sort for output stability when desired
    tools_seq: Sequence[Tool] = TOOLS
    if SORT_MODE == "alpha":
        tools_seq = tuple(sorted(TOOLS, key=lambda t: t.name.lower()))
    if selected_names:
        name_set = set(selected_names)
        tools_seq = tuple(t for t in tools_seq if t.name.lower() in name_set)
    results: list[tuple[str, str, str, str, str, str, str, str]] = [None] * len(tools_seq)  # type: ignore[assignment]
    # Guard: empty selection (unknown --only names)
    if len(tools_seq) == 0:
        if os.environ.get("CLI_AUDIT_JSON", "0") == "1":
            print("[]")
            return 0
        headers = ("state", "tool", "installed", "installed_method", "latest_upstream", "upstream_method")
        print("|".join(headers))
        return 0
    # If streaming mode and not JSON, print header first to show immediate output
    streamed_header_printed = False
    if os.environ.get("CLI_AUDIT_JSON", "0") != "1" and STREAM_OUTPUT:
        headers = (" ", "tool", "installed", "installed_method", "latest_upstream", "upstream_method")
        print("|".join(headers))
        streamed_header_printed = True

    total_tools = len(tools_seq)
    completed_tools = 0

    # Always show friendly startup message (not just when PROGRESS=1)
    if COLLECT_ONLY:
        offline_note = " (offline mode)" if OFFLINE_MODE else ""
        print(f"# Collecting fresh data for {total_tools} tools{offline_note}...", file=sys.stderr)
        estimated_time = int((total_tools / MAX_WORKERS) * TIMEOUT_SECONDS * 1.5)
        print(f"# Estimated time: ~{estimated_time}s (timeout={TIMEOUT_SECONDS}s per tool, {MAX_WORKERS} workers)", file=sys.stderr)
        if not OFFLINE_MODE:
            print(f"# Note: Network issues may cause hangs. Press Ctrl-C to cancel, or use 'make audit-offline' for faster results.", file=sys.stderr)

    # Detailed progress for debugging (only when PROGRESS=1)
    print(f"# start collect: tools={total_tools} timeout={TIMEOUT_SECONDS}s retries={HTTP_RETRIES} offline={OFFLINE_MODE}", file=sys.stderr) if PROGRESS else None

    # Debug: show thread pool configuration
    if AUDIT_DEBUG:
        actual_workers = min(MAX_WORKERS, total_tools)
        print(f"# DEBUG: ThreadPoolExecutor starting with max_workers={actual_workers}", file=sys.stderr, flush=True)

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, total_tools)) as executor:
        future_to_idx = {}
        for idx, tool in enumerate(tools_seq):
            if PROGRESS:
                print(f"# auditing {tool.name}...", file=sys.stderr)
            if AUDIT_DEBUG:
                print(f"# DEBUG: SUBMIT future for tool={tool.name} idx={idx}", file=sys.stderr, flush=True)
            future_to_idx[executor.submit(audit_tool, tool)] = idx
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]

            # Debug: show future completion
            if AUDIT_DEBUG:
                tool_name = tools_seq[idx].name
                print(f"# DEBUG: COMPLETE future for tool={tool_name} idx={idx}", file=sys.stderr, flush=True)

            try:
                row = future.result()
            except Exception as e:
                t = tools_seq[idx]
                if AUDIT_DEBUG:
                    print(f"# DEBUG: EXCEPTION in future for tool={t.name}: {e}", file=sys.stderr, flush=True)
                row = (t.name, "X", "", "", upstream_method_for(t), "UNKNOWN", tool_homepage_url(t), latest_target_url(t, "", ""))
            results[idx] = row
            completed_tools += 1

            # Always show basic progress counter during parallel execution (not just PROGRESS=1)
            # Show progress for both COLLECT_ONLY (make update) and live audit (make upgrade)
            if COLLECT_ONLY or MAX_WORKERS > 1:
                try:
                    name, installed, _im, latest, _um, status, _tu, _lu = row
                    # Clear status indicator: ✓ (success), ⚠ (warning), ✗ (failed)
                    if status in ("UP-TO-DATE", "OUTDATED"):
                        indicator = "✓"
                    elif status == "NOT INSTALLED":
                        indicator = "⚠"
                    elif status == "UNKNOWN":
                        indicator = "✗"
                    else:
                        indicator = "?"
                    # Show: "# ✓ [15/60] git (installed: 2.51.0, latest: 2.51.0)"
                    version_info = f"installed: {installed}" if installed and installed != "X" else "not installed"
                    if latest and latest != installed and status == "OUTDATED":
                        version_info += f", latest: {latest}"
                    print(f"# {indicator} [{completed_tools}/{total_tools}] {name} ({version_info})", file=sys.stderr, flush=True)
                except Exception:
                    # Fallback to simple message if row parsing fails
                    name = row[0] if row and len(row) > 0 else "?"
                    print(f"# [{completed_tools}/{total_tools}] {name}", file=sys.stderr, flush=True)

            # Detailed progress for debugging (only when PROGRESS=1)
            if PROGRESS:
                try:
                    name, installed, _installed_method, latest, upstream_method, status, _tool_url, _latest_url = row
                    print(f"# done {name} ({completed_tools}/{total_tools}) status={status} installed='{installed}' latest='{latest}' upstream={upstream_method}", file=sys.stderr)
                except Exception:
                    pass
            # In streaming mode, print each row as soon as available (no grouping)
            if STREAM_OUTPUT and os.environ.get("CLI_AUDIT_JSON", "0") != "1":
                name, installed, installed_method, latest, upstream_method, status, tool_url, latest_url = row
                icon = status_icon(status, installed)
                name_render = osc8(tool_url, name)
                latest_render = osc8(latest_url, latest)
                hint = hint_for(name) if HINTS_ENABLED and status in ("NOT INSTALLED", "OUTDATED") else ""
                latest_with_hint = latest_render if not hint else (latest_render + f"  [{hint}]")
                print("|".join((icon, name_render, installed, installed_method, latest_with_hint, upstream_method)))

    if os.environ.get("CLI_AUDIT_JSON", "0") == "1":
        payload = []
        for name, installed, installed_method, latest, upstream_method, status, tool_url, latest_url in results:
            payload.append({
                "tool": name,
                "category": category_for(name),
                "installed": installed if installed != "X" else "",
                "installed_method": installed_method,
                "installed_path_resolved": detect_install_method.__name__ and (os.path.realpath(shutil.which(name) or "") if installed else ""),
                "classification_reason": (_classify_install_method(os.path.realpath(shutil.which(name) or ""), name)[1] if installed else ""),
                # New fields: actual selected path/reason used during this run
                "installed_path_selected": SELECTED_PATHS.get(name, ""),
                "classification_reason_selected": SELECTED_REASON.get(name, ""),
                "installed_version": extract_version_number(installed),
                "latest_version": extract_version_number(latest),
                "latest_upstream": latest,
                "upstream_method": upstream_method,
                "status": status,
                "tool_url": tool_url,
                "latest_url": latest_url,
                "state_icon": status_icon(status, installed),
                "is_up_to_date": (status == "UP-TO-DATE"),
            })
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    # Always print raw (with OSC8 + emoji if enabled). When piped to column, OSC8 should be transparent.
    # In streaming mode, we've already printed lines; skip re-printing body
    if not STREAM_OUTPUT:
        headers = (" ", "tool", "installed", "installed_method", "latest_upstream", "upstream_method")
        print("|".join(headers))

    # Optionally group rows by category for faster scanning
    def _category_key(row: tuple[str, ...]) -> tuple[int, str]:
        nm = row[0]
        cat = category_for(nm)
        try:
            order = CATEGORY_ORDER.index(cat)
        except Exception:
            order = len(CATEGORY_ORDER)
        return (order, nm)

    if not STREAM_OUTPUT:
        rows = results
        if GROUP_BY_CATEGORY:
            rows = sorted(results, key=_category_key)
        elif SORT_MODE == "alpha":
            rows = sorted(results, key=lambda r: r[0].lower())

        for name, installed, installed_method, latest, upstream_method, status, tool_url, latest_url in rows:
            icon = status_icon(status, installed)
            name_render = osc8(tool_url, name)
            latest_render = osc8(latest_url, latest)
            hint = hint_for(name) if HINTS_ENABLED and status in ("NOT INSTALLED", "OUTDATED") else ""
            latest_with_hint = latest_render if not hint else (latest_render + f"  [{hint}]")
            print("|".join((icon, name_render, installed, installed_method, latest_with_hint, upstream_method)))
    # Readiness summary (human-only; local UX)
    try:
        total = len(results)
        missing = sum(1 for r in results if r[5] == "NOT INSTALLED")
        outdated = sum(1 for r in results if r[5] == "OUTDATED")
        unknown = sum(1 for r in results if r[5] == "UNKNOWN")
        offline_tag = " (offline)" if OFFLINE_MODE else ""
        print(f"\nReadiness{offline_tag}: {total} tools, {outdated} outdated, {missing} missing, {unknown} unknown", file=sys.stderr)
    except Exception:
        pass

    # COLLECT-ONLY: write snapshot at end and exit
    if COLLECT_ONLY:
        try:
            # Reuse JSON payload builder to form snapshot document
            payload = []
            for name, installed, installed_method, latest, upstream_method, status, tool_url, latest_url in results:
                payload.append({
                    "tool": name,
                    "category": category_for(name),
                    "installed": installed if installed != "X" else "",
                    "installed_method": installed_method,
                    "installed_path_selected": SELECTED_PATHS.get(name, ""),
                    "classification_reason_selected": SELECTED_REASON.get(name, ""),
                    "installed_version": extract_version_number(installed),
                    "latest_version": extract_version_number(latest),
                    "latest_upstream": latest,
                    "upstream_method": upstream_method,
                    "status": status,
                    "tool_url": tool_url,
                    "latest_url": latest_url,
                })
            # Always show completion message (not just when PROGRESS=1)
            print(f"# Writing snapshot to {SNAPSHOT_FILE}...", file=sys.stderr)
            meta = write_snapshot(payload)
            try:
                count = meta.get('count', len(payload))
                print(f"# ✓ Snapshot saved: {count} tools audited", file=sys.stderr)
                print(f"# Run 'make audit' to view results", file=sys.stderr)
            except Exception:
                print(f"# ✓ Snapshot saved to {SNAPSHOT_FILE}", file=sys.stderr)

            # Detailed debug info (only when PROGRESS=1)
            if PROGRESS:
                try:
                    print(
                        f"# snapshot written: path={SNAPSHOT_FILE} count={meta.get('count')} created_at={meta.get('created_at')} offline={meta.get('offline')}",
                        file=sys.stderr,
                    )
                except Exception:
                    pass
        except Exception as e:
            if AUDIT_DEBUG:
                print(f"# DEBUG: failed to write snapshot: {e}", file=sys.stderr)
        return 0

    # Optional footer (disabled by default to avoid breaking table layout)
    if os.environ.get("CLI_AUDIT_FOOTER", "0") == "1":
        path_has_cargo = CARGO_BIN in os.environ.get("PATH", "").split(":")
        print(f"# cargo_bin: {'yes' if path_has_cargo else 'no'}")
    return 0


def _sigint_handler(signum, frame):
    """Handle SIGINT (Ctrl-C) with immediate clean exit."""
    # Suppress threading shutdown errors by forcing immediate exit
    print("", file=sys.stderr)
    os._exit(130)  # Standard Unix exit code for SIGINT, immediate exit


if __name__ == "__main__":
    # Install signal handler for clean Ctrl-C behavior
    signal.signal(signal.SIGINT, _sigint_handler)
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        # Fallback: clean exit on Ctrl-C without stack trace
        print("", file=sys.stderr)
        os._exit(130)  # Standard Unix exit code for SIGINT, immediate exit


