"""Tests for the `audit.py --reconcile` entrypoint and its helpers.

Covers plan shaping (active vs preferred markers), catalog candidate
resolution, and the JSON output for plan/apply/protected/divergence cases.
"""

import argparse
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import audit
from cli_audit.reconcile import BulkReconciliationResult, Installation, ReconciliationResult


def _ns(**kw):
    """Build an args namespace with reconcile defaults."""
    base = {"verbose": False, "apply": False, "yes": False, "all": False, "tools": []}
    base.update(kw)
    return argparse.Namespace(**base)


def _inst(path, version="1.0.0", method="manual", active=False):
    return Installation("demo", version, method, path, active)


class TestShapeReconcilePlan:
    def test_marks_preferred_and_active_on_same_install(self):
        a = _inst("/home/u/.local/bin/demo", active=True)
        b = _inst("/usr/local/bin/demo")
        plan = audit._shape_reconcile_plan("demo", [a, b], preferred=a, active=a, protected=False)

        assert plan["count"] == 2
        assert plan["protected"] is False
        assert plan["installations"][0]["preferred"] is True
        assert plan["installations"][0]["active"] is True
        assert plan["installations"][1]["preferred"] is False

    def test_active_differs_from_preferred(self):
        pref = _inst("/home/u/.local/bin/demo")  # preferred, not active
        act = _inst("/usr/local/bin/demo", active=True)  # active, not preferred
        plan = audit._shape_reconcile_plan("demo", [pref, act], preferred=pref, active=act, protected=False)

        assert plan["preferred"]["path"] == "/home/u/.local/bin/demo"
        assert plan["active"]["path"] == "/usr/local/bin/demo"
        # exactly one preferred, one active, and they are different installs
        prefs = [i for i in plan["installations"] if i["preferred"]]
        acts = [i for i in plan["installations"] if i["active"]]
        assert len(prefs) == 1 and len(acts) == 1
        assert prefs[0]["path"] != acts[0]["path"]

    def test_protected_flag(self):
        a = _inst("/usr/bin/demo", active=True)
        plan = audit._shape_reconcile_plan("demo", [a], preferred=a, active=a, protected=True)
        assert plan["protected"] is True


class TestResolveCandidates:
    def test_returns_catalog_candidates(self):
        from cli_audit.reconcile import _resolve_candidates

        # pip declares candidates ["pip", "pip3"] in the catalog
        cands = _resolve_candidates("pip")
        assert cands is not None
        assert "pip3" in cands

    def test_unknown_tool_returns_none(self):
        from cli_audit.reconcile import _catalog_cache, _resolve_candidates

        _catalog_cache.pop("not-a-real-tool-xyz", None)
        assert _resolve_candidates("not-a-real-tool-xyz") is None

    def test_result_is_cached(self):
        from cli_audit.reconcile import _catalog_cache, _resolve_candidates

        _resolve_candidates("pip")
        assert "pip" in _catalog_cache


class TestSafeBinaryPath:
    def test_accepts_normal_absolute_paths(self):
        from cli_audit.reconcile import _is_safe_binary_path

        assert _is_safe_binary_path("/usr/bin/rg")
        assert _is_safe_binary_path("/home/u/.cargo/bin/fd")

    def test_rejects_shell_metacharacters_and_relative(self):
        from cli_audit.reconcile import _is_safe_binary_path

        assert not _is_safe_binary_path("/opt/x; rm -rf /")
        assert not _is_safe_binary_path("/opt/a$(id)")
        assert not _is_safe_binary_path("rg")
        assert not _is_safe_binary_path("")

    def test_classify_via_queries_short_circuits_unsafe_path(self):
        # An unsafe path must never reach a package-manager OS query; it falls
        # back to path-based classification instead.
        from cli_audit.reconcile import _classify_via_queries

        assert isinstance(_classify_via_queries("/opt/x; rm -rf /", "demo", False), str)


class TestCmdReconcilePlanJSON:
    def test_single_tool_plan_json(self):
        pref = _inst("/home/u/.local/bin/demo", active=True)
        other = _inst("/usr/local/bin/demo")
        with (
            patch("cli_audit.reconcile.detect_installations", return_value=[pref, other]),
            patch.object(audit, "JSON_MODE", True),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = audit.cmd_reconcile(_ns(tools=["demo"]))
        assert rc == 0
        doc = json.loads(buf.getvalue())
        plan = doc["results"][0]
        assert plan["count"] == 2
        assert plan["installations"][0]["preferred"] is True

    def test_no_tools_and_no_all_errors(self):
        rc = audit.cmd_reconcile(_ns(tools=[]))
        assert rc == 2


class TestCmdReconcileApplyJSON:
    def test_apply_reports_removed(self):
        removed = _inst("/usr/local/bin/demo")
        kept = _inst("/home/u/.local/bin/demo", active=True)
        result = ReconciliationResult(
            tool="demo",
            installations=(kept, removed),
            preferred=kept,
            active=kept,
            path_issues=(),
            action_taken="removed",
            removed_installations=(removed,),
            success=True,
        )
        with patch("cli_audit.reconcile.reconcile_tool", return_value=result), patch.object(audit, "JSON_MODE", True):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = audit.cmd_reconcile(_ns(tools=["demo"], apply=True, yes=True))
        assert rc == 0
        doc = json.loads(buf.getvalue())
        assert doc["results"][0]["action_taken"] == "removed"
        assert doc["results"][0]["removed_installations"][0]["path"] == "/usr/local/bin/demo"

    def test_all_apply_prints_failures_and_declines_to_stderr(self):
        """Failed removals after a confirmed prompt must be visible without --verbose.

        Regression: `--all --apply` printed only the summary, so a user who
        answered "y" saw "Conflicts resolved: 0" with no per-tool error.
        """
        kept = _inst("/home/u/.local/bin/yq", active=True)
        failed = ReconciliationResult(
            tool="yq",
            installations=(kept, _inst("/usr/local/bin/yq")),
            preferred=kept,
            active=kept,
            path_issues=(),
            action_taken="removed",
            success=False,
            error_message="[Errno 2] No such file or directory: 'brew'",
        )
        kept_npm = _inst("/home/u/.local/bin/npm", active=True)
        declined = ReconciliationResult(
            tool="npm",
            installations=(kept_npm, _inst("/usr/bin/npm")),
            preferred=kept_npm,
            active=kept_npm,
            path_issues=(),
            action_taken="aborted",
            success=False,
            error_message="User declined removal",
        )
        bulk = BulkReconciliationResult(
            tools_checked=2,
            conflicts_found=2,
            conflicts_resolved=0,
            results=(failed, declined),
            duration_seconds=0.1,
        )
        with patch("cli_audit.reconcile.bulk_reconcile", return_value=bulk):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = audit.cmd_reconcile(_ns(all=True, apply=True, yes=True))
        assert rc == 1
        output = err.getvalue()
        assert "yq" in output
        assert "No such file or directory: 'brew'" in output
        assert "npm" in output
        assert "declined" in output

    def test_apply_protected_returns_nonzero(self):
        kept = _inst("/usr/bin/demo", active=True)
        result = ReconciliationResult(
            tool="demo",
            installations=(kept,),
            preferred=kept,
            active=kept,
            path_issues=(),
            action_taken="blocked",
            success=False,
            error_message="on system safelist",
        )
        with patch("cli_audit.reconcile.reconcile_tool", return_value=result), patch.object(audit, "JSON_MODE", True):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = audit.cmd_reconcile(_ns(tools=["demo"], apply=True, yes=True))
        assert rc == 1
