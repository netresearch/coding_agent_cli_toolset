"""The Claude Code plugin shipped from this repository.

The skill in ``skills/cli-tools`` calls the repository's own scripts and names
catalog entries in its references. Those references are prose, so nothing
would notice when a script moves or a catalog entry is renamed; these tests
tie them to the files they describe.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = PROJECT_ROOT / "skills" / "cli-tools"
REFERENCES = SKILL_DIR / "references"
CATALOG = PROJECT_ROOT / "catalog"
SCRIPTS = PROJECT_ROOT / "scripts"

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")


def _catalog_names() -> set[str]:
    return {p.stem for p in CATALOG.glob("*.json")}


def _table_rows(markdown: str, heading: str) -> list[list[str]]:
    """Cells of the first table under ``heading``, header and rule excluded."""
    section = markdown.split(heading, 1)[1]
    rows = []
    for line in section.splitlines()[1:]:
        if line.startswith("#"):
            break
        if line.startswith("|") and not line.startswith("|--"):
            rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows[1:]


def _names(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


class TestManifest:
    def test_plugin_json_is_valid_and_points_at_the_skill(self):
        manifest = json.loads((PROJECT_ROOT / ".claude-plugin" / "plugin.json").read_text())
        assert manifest["name"] == "cli-tools"
        for path in manifest["skills"]:
            assert (PROJECT_ROOT / path / "SKILL.md").is_file(), path

    def test_plugin_json_sets_no_version(self):
        # Without a version, Claude Code versions the plugin by commit SHA, so
        # every merge reaches users. A pinned version would freeze them until
        # someone bumps it -- and this repository has no release flow that does.
        manifest = json.loads((PROJECT_ROOT / ".claude-plugin" / "plugin.json").read_text())
        assert "version" not in manifest

    def test_content_license_file_exists(self):
        manifest = json.loads((PROJECT_ROOT / ".claude-plugin" / "plugin.json").read_text())
        assert "CC-BY-SA-4.0" in manifest["license"]
        assert (PROJECT_ROOT / "LICENSE-CC-BY-SA-4.0").is_file()


class TestSkill:
    def test_frontmatter_name_matches_directory(self):
        text = (SKILL_DIR / "SKILL.md").read_text()
        front = text.split("---", 2)[1]
        assert re.search(r"^name: cli-tools$", front, re.M)
        assert re.search(r"^description: ", front, re.M)

    def test_every_referenced_script_exists_and_is_executable(self):
        text = (SKILL_DIR / "SKILL.md").read_text()
        scripts = set(re.findall(r"\$\{CLAUDE_SKILL_DIR\}/\.\./\.\./scripts/([\w./-]+\.sh)", text))
        assert scripts, "SKILL.md names no scripts -- the pattern no longer matches"
        for name in scripts:
            path = SCRIPTS / name
            assert path.is_file(), name
            assert os.access(path, os.X_OK), name

    def test_every_referenced_reference_exists(self):
        texts = [(SKILL_DIR / "SKILL.md").read_text(), *(p.read_text() for p in REFERENCES.glob("*.md"))]
        named = {m for t in texts for m in re.findall(r"references/([\w-]+\.md)", t)}
        assert named
        for name in named:
            assert (REFERENCES / name).is_file(), name


class TestBinaryMap:
    def test_differing_binary_names_match_the_catalog(self):
        rows = _table_rows((REFERENCES / "binary_to_tool_map.md").read_text(), "## Binary name differs")
        assert rows
        for binary_cell, entry_cell in rows:
            binary, entry = _names(binary_cell)[0], _names(entry_cell)[0]
            data = json.loads((CATALOG / f"{entry}.json").read_text())
            assert data.get("binary_name") == binary, (binary, entry)

    def test_every_catalog_entry_with_a_differing_binary_is_listed(self):
        rows = _table_rows((REFERENCES / "binary_to_tool_map.md").read_text(), "## Binary name differs")
        listed = {_names(entry)[0] for _, entry in rows}
        differing = set()
        for path in CATALOG.glob("*.json"):
            binary = json.loads(path.read_text()).get("binary_name")
            if binary and binary != path.stem:
                differing.add(path.stem)
        # compose shares the `docker` binary with the docker entry; the file
        # explains it below the table instead of listing it.
        assert differing - {"compose"} == listed


@skip_on_windows
class TestProjectTypes:
    # One marker file per detected type, as named in the reference table
    MARKERS = {
        "python": "pyproject.toml",
        "node": "package.json",
        "rust": "Cargo.toml",
        "go": "go.mod",
        "ruby": "Gemfile",
        "php": "composer.json",
        "docker": "Dockerfile",
        "terraform": "main.tf",
        "ansible": "ansible.cfg",
        "shell": "Makefile",
    }

    def _detect(self, directory: Path) -> dict:
        proc = subprocess.run(
            [str(SCRIPTS / "detect_project_type.sh"), "json", str(directory)], capture_output=True, text=True
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    def test_empty_directory_yields_empty_lists(self, tmp_path):
        assert self._detect(tmp_path) == {"project_types": [], "required_tools": [], "recommended_tools": []}

    def test_reference_table_matches_the_script(self, tmp_path):
        rows = _table_rows((REFERENCES / "project_type_requirements.md").read_text(), "## Detected types")
        table = {row[0]: (sorted(_names(row[2])), sorted(_names(row[3]))) for row in rows}
        for project_type, marker in self.MARKERS.items():
            directory = tmp_path / project_type
            directory.mkdir()
            (directory / marker).touch()
            result = self._detect(directory)
            assert result["project_types"] == [project_type], marker
            assert (result["required_tools"], result["recommended_tools"]) == table[project_type], project_type

    def test_kubernetes_is_detected_from_a_k8s_directory(self, tmp_path):
        (tmp_path / "k8s").mkdir()
        assert self._detect(tmp_path)["project_types"] == ["kubernetes"]

    def test_every_named_tool_is_cataloged(self):
        rows = _table_rows((REFERENCES / "project_type_requirements.md").read_text(), "## Detected types")
        named = {name for row in rows for name in _names(row[2]) + _names(row[3])}
        assert named - _catalog_names() == set()


@skip_on_windows
class TestCheckEnvironment:
    def test_required_tools_are_found_by_their_binary_name(self, tmp_path):
        # `rust` provides rustc, not a binary called rust: checking the catalog
        # name reported an installed toolchain as missing.
        project = tmp_path / "project"
        project.mkdir()
        (project / "Cargo.toml").touch()
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        rustc = bin_dir / "rustc"
        rustc.write_text("#!/bin/sh\necho rustc 9.9.9\n")
        rustc.chmod(0o755)
        proc = subprocess.run(
            [str(SCRIPTS / "check_environment.sh"), "project", str(project)],
            capture_output=True,
            text=True,
            env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )
        assert proc.returncode == 0, proc.stderr
        assert "rust: rustc 9.9.9" in proc.stdout
        assert "NOT INSTALLED" not in proc.stdout

    def test_one_file_reached_through_two_path_entries_is_not_a_duplicate(self, tmp_path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        cargo = bin_dir / "cargo"
        cargo.write_text("#!/bin/sh\n")
        cargo.chmod(0o755)
        link = tmp_path / "link"
        link.symlink_to(bin_dir)
        proc = subprocess.run(
            [str(SCRIPTS / "check_environment.sh"), "duplicates"],
            capture_output=True,
            text=True,
            env={**os.environ, "PATH": f"{bin_dir}:{link}:{bin_dir}:/usr/bin:/bin"},
        )
        assert "cargo has" not in proc.stdout, proc.stdout
