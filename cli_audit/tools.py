"""
Tool definitions and metadata management.

Phase 2.0: Detection and Auditing - Tool Definitions
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class Tool:
    """Tool definition with source and detection metadata."""
    name: str
    candidates: tuple[str, ...]  # Binary names to search for
    source_kind: str  # "gh" | "gitlab" | "pypi" | "crates" | "npm" | "gnu" | "skip"
    source_args: tuple[str, ...]  # Source-specific args (owner, repo) or (package,)
    category: str = "other"
    hint: str = ""


# Hardcoded tool definitions (fallback when catalog incomplete)
TOOLS: tuple[Tool, ...] = (
    # Language runtimes & package managers
    Tool("go", ("go",), "gh", ("golang", "go"), "runtimes", "make install-go"),
    Tool("uv", ("uv",), "gh", ("astral-sh", "uv"), "runtimes", ""),
    Tool("python", ("python3", "python"), "gh", ("python", "cpython"), "runtimes", "make install-python"),
    Tool("pip", ("pip3", "pip"), "pypi", ("pip",), "runtimes", "make install-python"),
    Tool("pipx", ("pipx",), "pypi", ("pipx",), "runtimes", "make install-python"),
    Tool("poetry", ("poetry",), "pypi", ("poetry",), "runtimes", "make install-python"),
    Tool("rust", ("rustc",), "gh", ("rust-lang", "rust"), "runtimes", "make install-rust"),
    Tool("node", ("node",), "gh", ("nodejs", "node"), "runtimes", "make install-node"),
    Tool("npm", ("npm",), "npm", ("npm",), "runtimes", "make install-node"),
    Tool("pnpm", ("pnpm",), "npm", ("pnpm",), "runtimes", "make install-node"),
    Tool("yarn", ("yarn",), "npm", ("yarn",), "runtimes", "make install-node"),
    Tool("composer", ("composer",), "gh", ("composer", "composer"), "runtimes", ""),
    Tool("ruby", ("ruby",), "gh", ("ruby", "ruby"), "runtimes", ""),
    Tool("gem", ("gem",), "gh", ("rubygems", "rubygems"), "runtimes", ""),
    # Core developer tools
    Tool("fd", ("fd", "fdfind"), "gh", ("sharkdp", "fd"), "search", "make install-core"),
    Tool("fzf", ("fzf",), "gh", ("junegunn", "fzf"), "search", "make install-core"),
    Tool("ctags", ("ctags",), "gh", ("universal-ctags", "ctags"), "editors", "make install-core"),
    Tool("rga", ("rga",), "gh", ("phiresky", "ripgrep-all"), "search", ""),
    Tool("jq", ("jq",), "gh", ("jqlang", "jq"), "json-yaml", "make install-core"),
    Tool("yq", ("yq",), "gh", ("mikefarah", "yq"), "json-yaml", "make install-core"),
    Tool("dasel", ("dasel",), "gh", ("TomWright", "dasel"), "json-yaml", "make install-core"),
    Tool("sd", ("sd",), "crates", ("sd",), "editors", "make install-core"),
    Tool("prename", ("file-rename", "rename"), "skip", (), "editors", ""),
    Tool("rename.ul", ("rename.ul",), "skip", (), "editors", ""),
    Tool("sponge", ("sponge",), "skip", (), "editors", ""),
    Tool("xsv", ("xsv",), "crates", ("xsv",), "data", "make install-core"),
    Tool("bat", ("bat", "batcat"), "gh", ("sharkdp", "bat"), "editors", "make install-core"),
    Tool("delta", ("delta",), "gh", ("dandavison", "delta"), "editors", "make install-core"),
    Tool("entr", ("entr",), "gh", ("eradman", "entr"), "automation", "make install-core"),
    Tool("watchexec", ("watchexec", "watchexec-cli"), "gh", ("watchexec", "watchexec"), "automation", ""),
    Tool("parallel", ("parallel",), "gnu", ("parallel",), "automation", ""),
    Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"), "search", "make install-core"),
    Tool("ast-grep", ("ast-grep", "sg"), "gh", ("ast-grep", "ast-grep"), "search", ""),
    Tool("httpie", ("http",), "pypi", ("httpie",), "http", "make install-python"),
    Tool("curlie", ("curlie",), "gh", ("rs", "curlie"), "http", ""),
    Tool("direnv", ("direnv",), "gh", ("direnv", "direnv"), "automation", "make install-core"),
    Tool("dive", ("dive",), "gh", ("wagoodman", "dive"), "cloud-infra", "make install-core"),
    Tool("trivy", ("trivy",), "gh", ("aquasecurity", "trivy"), "security", "make install-core"),
    Tool("gitleaks", ("gitleaks",), "gh", ("gitleaks", "gitleaks"), "security", "make install-core"),
    Tool("pre-commit", ("pre-commit",), "pypi", ("pre-commit",), "security", "make install-python"),
    Tool("bandit", ("bandit",), "pypi", ("bandit",), "security", "make install-python"),
    Tool("semgrep", ("semgrep",), "pypi", ("semgrep",), "security", "make install-python"),
    Tool("ansible", ("ansible", "ansible-community"), "pypi", ("ansible-core",), "automation", "make install-ansible"),
    Tool("ansible-core", ("ansible", "ansible-core"), "pypi", ("ansible-core",), "automation", "make install-ansible"),
    Tool("git-absorb", ("git-absorb",), "gh", ("tummychow", "git-absorb"), "git-helpers", ""),
    Tool("git-branchless", ("git-branchless",), "gh", ("arxanas", "git-branchless"), "git-helpers", ""),
    Tool("git-lfs", ("git-lfs",), "gh", ("git-lfs", "git-lfs"), "git-helpers", ""),
    Tool("tfsec", ("tfsec",), "gh", ("aquasecurity", "tfsec"), "security", ""),
    # Formatters & linters
    Tool("black", ("black",), "pypi", ("black",), "formatters", "make install-python"),
    Tool("isort", ("isort",), "pypi", ("isort",), "formatters", "make install-python"),
    Tool("flake8", ("flake8",), "pypi", ("flake8",), "formatters", "make install-python"),
    Tool("eslint", ("eslint",), "gh", ("eslint", "eslint"), "formatters", "make install-node"),
    Tool("prettier", ("prettier",), "gh", ("prettier", "prettier"), "formatters", "make install-node"),
    Tool("shfmt", ("shfmt",), "gh", ("mvdan", "sh"), "formatters", ""),
    Tool("shellcheck", ("shellcheck",), "gh", ("koalaman", "shellcheck"), "formatters", ""),
    Tool("golangci-lint", ("golangci-lint",), "gh", ("golangci", "golangci-lint"), "formatters", ""),
    # JSON/YAML viewers
    Tool("fx", ("fx",), "gh", ("antonmedv", "fx"), "json-yaml", ""),
    # AI assistants
    Tool("codex", ("codex",), "pypi", ("codex",), "ai-assistants", ""),
    Tool("claude", ("claude",), "npm", ("@anthropic-ai/claude-code",), "ai-assistants", ""),
    # VCS & platforms
    Tool("git", ("git",), "gh", ("git", "git"), "vcs", "make install-core"),
    Tool("gh", ("gh",), "gh", ("cli", "cli"), "vcs", "make install-core"),
    Tool("glab", ("glab",), "gitlab", ("gitlab-org", "cli"), "vcs", "make install-core"),
    Tool("gam", ("gam",), "pypi", ("gam7",), "vcs", ""),
    # Task runners & build systems
    Tool("just", ("just",), "gh", ("casey", "just"), "task-runners", "make install-core"),
    Tool("ninja", ("ninja",), "gh", ("ninja-build", "ninja"), "task-runners", ""),
    # Cloud / infra
    Tool("aws", ("aws",), "gh", ("aws", "aws-cli"), "cloud-infra", "make install-aws"),
    Tool("kubectl", ("kubectl",), "gh", ("kubernetes", "kubernetes"), "cloud-infra", "make install-kubectl"),
    Tool("terraform", ("terraform",), "gh", ("hashicorp", "terraform"), "cloud-infra", "make install-terraform"),
    Tool("docker", ("docker",), "gh", ("docker", "cli"), "cloud-infra", "make install-docker"),
    Tool("compose", ("docker",), "gh", ("docker", "compose"), "cloud-infra", ""),
)

# Tool lookup map for fast access
TOOL_MAP: dict[str, Tool] = {t.name: t for t in TOOLS}

# Category order for grouping
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
    "ai-assistants",
    "other",
)


def get_tool(name: str) -> Tool | None:
    """Get tool definition by name.

    Args:
        name: Tool name

    Returns:
        Tool or None if not found
    """
    return TOOL_MAP.get(name)


def all_tools() -> list[Tool]:
    """Get all tool definitions.

    Returns:
        List of all tools in defined order
    """
    return list(TOOLS)


def filter_tools(names: list[str]) -> list[Tool]:
    """Filter tools by name list.

    Args:
        names: List of tool names (case-insensitive)

    Returns:
        List of matching tools in original order
    """
    name_set = {n.lower() for n in names}
    return [t for t in TOOLS if t.name.lower() in name_set]


def tool_homepage_url(tool: Tool) -> str:
    """Get homepage URL for a tool.

    Args:
        tool: Tool definition

    Returns:
        Homepage URL string
    """
    if tool.source_kind == "gh" and len(tool.source_args) >= 2:
        owner, repo = tool.source_args[0], tool.source_args[1]
        return f"https://github.com/{owner}/{repo}"
    elif tool.source_kind == "gitlab" and len(tool.source_args) >= 2:
        group, project = tool.source_args[0], tool.source_args[1]
        return f"https://gitlab.com/{group}/{project}"
    elif tool.source_kind == "pypi" and tool.source_args:
        package = tool.source_args[0]
        return f"https://pypi.org/project/{package}/"
    elif tool.source_kind == "npm" and tool.source_args:
        package = tool.source_args[0]
        return f"https://www.npmjs.com/package/{package}"
    elif tool.source_kind == "crates" and tool.source_args:
        crate = tool.source_args[0]
        return f"https://crates.io/crates/{crate}"
    return ""


def latest_target_url(tool: Tool, latest_tag: str, latest_num: str) -> str:
    """Get URL for latest release.

    Args:
        tool: Tool definition
        latest_tag: Latest version tag
        latest_num: Latest version number

    Returns:
        Release URL string
    """
    if tool.source_kind == "gh" and len(tool.source_args) >= 2:
        owner, repo = tool.source_args[0], tool.source_args[1]
        if latest_tag:
            return f"https://github.com/{owner}/{repo}/releases/tag/{latest_tag}"
        return f"https://github.com/{owner}/{repo}/releases"
    elif tool.source_kind == "gitlab" and len(tool.source_args) >= 2:
        group, project = tool.source_args[0], tool.source_args[1]
        if latest_tag:
            return f"https://gitlab.com/{group}/{project}/-/releases/{latest_tag}"
        return f"https://gitlab.com/{group}/{project}/-/releases"
    elif tool.source_kind == "pypi" and tool.source_args:
        package = tool.source_args[0]
        return f"https://pypi.org/project/{package}/"
    elif tool.source_kind == "npm" and tool.source_args:
        package = tool.source_args[0]
        return f"https://www.npmjs.com/package/{package}"
    elif tool.source_kind == "crates" and tool.source_args:
        crate = tool.source_args[0]
        return f"https://crates.io/crates/{crate}"
    return ""
