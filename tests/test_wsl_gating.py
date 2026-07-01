"""Tests for WSL-conditional catalog tools (the ``requires_wsl`` gate).

A tool flagged ``requires_wsl`` (currently ``wslu``/``wslview``) must only be
surfaced when running under WSL, so non-WSL machines are neither prompted to
install it nor shown it as missing.
"""

from unittest.mock import patch

from cli_audit.catalog import ToolCatalog


@patch("cli_audit.collectors.is_wsl", return_value=True)
def test_wsl_only_tool_present_on_wsl(_mock_is_wsl):
    names = {t.name for t in ToolCatalog().all_tool_definitions()}
    assert "wslu" in names


@patch("cli_audit.collectors.is_wsl", return_value=False)
def test_wsl_only_tool_hidden_off_wsl(_mock_is_wsl):
    names = {t.name for t in ToolCatalog().all_tool_definitions()}
    assert "wslu" not in names


@patch("cli_audit.collectors.is_wsl", return_value=False)
def test_non_wsl_tools_unaffected_off_wsl(_mock_is_wsl):
    """Gating a WSL-only tool must not drop ordinary tools."""
    names = {t.name for t in ToolCatalog().all_tool_definitions()}
    assert "ripgrep" in names


def test_wslu_catalog_entry_is_wsl_gated():
    """The wslu entry must stay WSL-gated, apt/skip-upstream, wslview-detected."""
    raw = ToolCatalog().get_raw_data("wslu")
    assert raw.get("requires_wsl") is True
    assert raw.get("skip_upstream") is True
    assert raw.get("binary_name") == "wslview"
    assert raw.get("install_method") == "dedicated_script"
