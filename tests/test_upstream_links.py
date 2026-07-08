"""Tests for upstream-source fixes:

- poetry (and any tool) can declare an explicit ``source_kind`` in the catalog
- release URLs use the RAW tag (``v1.7.12``) so GitHub/GitLab links resolve
- the Python-package-manager health check knows about poetry
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from cli_audit.catalog import ToolCatalog, ToolCatalogEntry
from cli_audit.collectors import collect_gitlab, collect_github
from cli_audit.tools import Tool, latest_target_url

ROOT = Path(__file__).resolve().parent.parent


class TestExplicitSourceKind:
    def test_poetry_resolves_pypi(self):
        tool = ToolCatalog().get("poetry").to_tool()
        assert tool.source_kind == "pypi"
        assert tool.source_args == ("poetry",)

    def test_explicit_source_kind_with_package_name(self):
        entry = ToolCatalogEntry(
            name="demo",
            package_name="demo-pkg",
            _raw_data={"source_kind": "pypi"},
        )
        assert entry._derive_source() == ("pypi", ("demo-pkg",))

    def test_explicit_source_args_win(self):
        entry = ToolCatalogEntry(
            name="demo",
            _raw_data={"source_kind": "gh", "source_args": ["owner", "repo"]},
        )
        assert entry._derive_source() == ("gh", ("owner", "repo"))


class TestRawTagUrls:
    def test_github_url_keeps_v_prefix(self):
        tool = Tool("actionlint", ("actionlint",), "gh", ("rhysd", "actionlint"))
        url = latest_target_url(tool, "v1.7.12", "1.7.12")
        assert url == "https://github.com/rhysd/actionlint/releases/tag/v1.7.12"

    def test_gitlab_url_keeps_raw_tag(self):
        tool = Tool("demo", ("demo",), "gitlab", ("grp", "proj"))
        url = latest_target_url(tool, "v2.0.0", "2.0.0")
        assert url == "https://gitlab.com/grp/proj/-/releases/v2.0.0"

    def test_collect_github_returns_raw_tag(self):
        # Force the redirect path to fail so the API path (http_get) is used.
        opener = MagicMock()
        opener.open.side_effect = Exception("no redirect in test")
        api_body = json.dumps({"tag_name": "v3.4.5"}).encode()
        with patch("cli_audit.collectors.urllib.request.build_opener", return_value=opener), \
                patch("cli_audit.collectors.http_get", return_value=api_body):
            raw_tag, version = collect_github("owner", "repo")
        assert raw_tag == "v3.4.5"       # raw tag preserved for the URL
        assert version == "3.4.5"        # version normalized for display/compare

    def test_collect_gitlab_returns_raw_tag(self):
        body = json.dumps([{"tag_name": "v9.9.9"}]).encode()
        with patch("cli_audit.collectors.http_get", return_value=body):
            raw_tag, version = collect_gitlab("grp", "proj")
        assert raw_tag == "v9.9.9"
        assert version == "9.9.9"


class TestReviewFixes:
    def test_merged_display_uses_normalized_version_not_raw_tag(self):
        # Regression: latest_tag holds the raw tag ("v1.7.12") for URL building;
        # the displayed "latest" must be the normalized version.
        from cli_audit.local_state import LocalState, merge_for_display
        from cli_audit.upstream_cache import UpstreamCache, UpstreamVersion

        up = UpstreamCache(versions={
            "demo": UpstreamVersion(latest_tag="v1.7.12", latest_version="1.7.12"),
        })
        merged = merge_for_display(up, LocalState())
        entry = next(t for t in merged if t["tool"] == "demo")
        assert entry["latest_upstream"] == "1.7.12"

    def test_url_strips_terminal_escape_sequences(self):
        tool = Tool("x", ("x",), "gh", ("o", "r"))
        url = latest_target_url(tool, "v1.0\x1b[31m\x07", "1.0")
        assert "\x1b" not in url and "\x07" not in url

    def test_source_args_string_not_split(self):
        entry = ToolCatalogEntry(
            name="d", _raw_data={"source_kind": "pypi", "source_args": "demo-pkg"}
        )
        assert entry._derive_source() == ("pypi", ("demo-pkg",))

    def test_collect_github_handles_non_dict_json(self):
        with patch("cli_audit.collectors.urllib.request.build_opener") as bo, \
                patch("cli_audit.collectors.http_get", return_value=b'["unexpected"]'):
            bo.return_value.open.side_effect = Exception("no redirect")
            # Must not raise AttributeError on the list response
            collect_github("owner", "repo")


class TestHealthCheckKnowsPoetry:
    def test_script_detects_poetry(self):
        script = (ROOT / "scripts" / "check_python_package_managers.sh").read_text()
        assert "has_poetry" in script
        assert "command -v poetry" in script
        # "optimal" must require the absence of poetry
        assert "! $has_poetry" in script
