"""
Tests for local installation state management (cli_audit/local_state.py).

Target coverage: 85%+
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from cli_audit.local_state import (
    LocalInstallation,
    LocalState,
    get_local_state_path,
    load_local_state,
    write_local_state,
    get_local_installation,
    update_local_installation,
    migrate_from_snapshot,
    merge_for_display,
    build_legacy_snapshot,
    DEFAULT_LOCAL_STATE_FILE,
)
from cli_audit.upstream_cache import UpstreamCache, UpstreamVersion


class TestLocalInstallation:
    """Tests for LocalInstallation dataclass."""

    def test_local_installation_defaults(self):
        """Test LocalInstallation with default values."""
        install = LocalInstallation()
        assert install.installed_version == ""
        assert install.installed_path == ""
        assert install.installed_method == ""
        assert install.status == "UNKNOWN"
        assert install.classification_reason == ""
        assert install.category == "other"
        assert install.hint == ""

    def test_local_installation_custom_values(self):
        """Test LocalInstallation with custom values."""
        install = LocalInstallation(
            installed_version="1.2.3",
            installed_path="/usr/local/bin/tool",
            installed_method="cargo",
            status="UP-TO-DATE",
            classification_reason="Detected via path analysis",
            category="rust-core",
            hint="cargo install tool",
        )
        assert install.installed_version == "1.2.3"
        assert install.installed_path == "/usr/local/bin/tool"
        assert install.installed_method == "cargo"
        assert install.status == "UP-TO-DATE"
        assert install.classification_reason == "Detected via path analysis"
        assert install.category == "rust-core"
        assert install.hint == "cargo install tool"

    def test_local_installation_to_dict(self):
        """Test LocalInstallation to_dict serialization."""
        install = LocalInstallation(
            installed_version="2.0.0",
            installed_method="pip",
            status="OUTDATED",
        )
        d = install.to_dict()
        assert d["installed_version"] == "2.0.0"
        assert d["installed_method"] == "pip"
        assert d["status"] == "OUTDATED"
        assert d["category"] == "other"  # Default
        assert d["hint"] == ""  # Default

    def test_local_installation_from_dict(self):
        """Test creating LocalInstallation from dictionary."""
        data = {
            "installed_version": "3.0.0",
            "installed_path": "/home/user/.local/bin/tool",
            "installed_method": "uv",
            "status": "UP-TO-DATE",
            "classification_reason": "User pip package",
            "category": "python-core",
            "hint": "uv tool install tool",
        }
        install = LocalInstallation.from_dict(data)
        assert install.installed_version == "3.0.0"
        assert install.installed_path == "/home/user/.local/bin/tool"
        assert install.installed_method == "uv"
        assert install.status == "UP-TO-DATE"
        assert install.classification_reason == "User pip package"
        assert install.category == "python-core"
        assert install.hint == "uv tool install tool"

    def test_local_installation_from_dict_partial(self):
        """Test creating LocalInstallation from partial dictionary."""
        data = {"installed_version": "1.0.0", "status": "OUTDATED"}
        install = LocalInstallation.from_dict(data)
        assert install.installed_version == "1.0.0"
        assert install.status == "OUTDATED"
        assert install.installed_path == ""  # Default
        assert install.installed_method == ""  # Default
        assert install.category == "other"  # Default

    def test_local_installation_from_dict_empty(self):
        """Test creating LocalInstallation from empty dictionary."""
        install = LocalInstallation.from_dict({})
        assert install.installed_version == ""
        assert install.status == "UNKNOWN"
        assert install.category == "other"


class TestLocalState:
    """Tests for LocalState dataclass."""

    def test_local_state_defaults(self):
        """Test LocalState with default values."""
        state = LocalState()
        assert state.tools == {}
        assert state.schema_version == 2
        assert state.collected_at == ""
        assert state.hostname == ""
        assert state.offline is False
        assert state.count == 0
        assert state.partial_failures == 0

    def test_local_state_custom_values(self):
        """Test LocalState with custom values."""
        tools = {"ripgrep": LocalInstallation(installed_version="15.0.0")}
        state = LocalState(
            tools=tools,
            schema_version=2,
            collected_at="2025-01-01T00:00:00Z",
            hostname="testhost",
            offline=True,
            count=1,
            partial_failures=0,
        )
        assert "ripgrep" in state.tools
        assert state.collected_at == "2025-01-01T00:00:00Z"
        assert state.hostname == "testhost"
        assert state.offline is True
        assert state.count == 1

    def test_local_state_to_dict(self):
        """Test LocalState to_dict serialization."""
        tools = {
            "fd": LocalInstallation(installed_version="10.0.0", status="UP-TO-DATE"),
        }
        state = LocalState(
            tools=tools,
            collected_at="2025-06-01T12:00:00Z",
            hostname="myhost",
            count=1,
        )
        d = state.to_dict()
        assert "__meta__" in d
        assert d["__meta__"]["schema_version"] == 2
        assert d["__meta__"]["collected_at"] == "2025-06-01T12:00:00Z"
        assert d["__meta__"]["hostname"] == "myhost"
        assert d["__meta__"]["count"] == 1
        assert "tools" in d
        assert "fd" in d["tools"]
        assert d["tools"]["fd"]["installed_version"] == "10.0.0"

    def test_local_state_from_dict(self):
        """Test creating LocalState from dictionary."""
        data = {
            "__meta__": {
                "schema_version": 2,
                "collected_at": "2025-03-15T08:30:00Z",
                "hostname": "dev-machine",
                "offline": False,
                "count": 2,
                "partial_failures": 1,
            },
            "tools": {
                "bat": {
                    "installed_version": "0.25.0",
                    "installed_method": "cargo",
                    "status": "UP-TO-DATE",
                },
                "uv": {
                    "installed_version": "0.5.0",
                    "installed_method": "pip",
                    "status": "OUTDATED",
                },
            },
        }
        state = LocalState.from_dict(data)
        assert state.schema_version == 2
        assert state.collected_at == "2025-03-15T08:30:00Z"
        assert state.hostname == "dev-machine"
        assert state.offline is False
        assert state.count == 2
        assert state.partial_failures == 1
        assert "bat" in state.tools
        assert "uv" in state.tools
        assert state.tools["bat"].installed_version == "0.25.0"

    def test_local_state_from_dict_empty(self):
        """Test creating LocalState from empty dictionary."""
        state = LocalState.from_dict({})
        assert state.tools == {}
        assert state.schema_version == 2
        assert state.collected_at == ""
        assert state.hostname == ""


class TestGetLocalStatePath:
    """Tests for get_local_state_path function."""

    def test_get_local_state_path_default(self, monkeypatch):
        """Test default path resolution."""
        monkeypatch.delenv("CLI_AUDIT_LOCAL_FILE", raising=False)
        path = get_local_state_path()
        assert path.name == DEFAULT_LOCAL_STATE_FILE
        assert path.parent == Path.cwd()

    def test_get_local_state_path_env_relative(self, monkeypatch):
        """Test relative path from environment variable."""
        monkeypatch.setenv("CLI_AUDIT_LOCAL_FILE", "custom_local.json")
        path = get_local_state_path()
        assert path.name == "custom_local.json"
        assert path.parent == Path.cwd()

    def test_get_local_state_path_env_absolute(self, monkeypatch, tmp_path):
        """Test absolute path from environment variable."""
        test_path = tmp_path / "local_state.json"
        monkeypatch.setenv("CLI_AUDIT_LOCAL_FILE", str(test_path))
        path = get_local_state_path()
        assert path == test_path


class TestLoadLocalState:
    """Tests for load_local_state function."""

    def test_load_local_state_not_found(self, tmp_path):
        """Test loading from non-existent file returns empty state."""
        path = tmp_path / "nonexistent.json"
        state = load_local_state(path)
        assert state.tools == {}

    def test_load_local_state_valid(self, tmp_path):
        """Test loading valid state file."""
        path = tmp_path / "local_state.json"
        data = {
            "__meta__": {
                "schema_version": 2,
                "collected_at": "2025-01-01T00:00:00Z",
                "hostname": "testhost",
            },
            "tools": {
                "ripgrep": {
                    "installed_version": "15.0.0",
                    "installed_method": "cargo",
                    "status": "UP-TO-DATE",
                },
            },
        }
        path.write_text(json.dumps(data))
        state = load_local_state(path)
        assert "ripgrep" in state.tools
        assert state.tools["ripgrep"].installed_version == "15.0.0"
        assert state.hostname == "testhost"

    def test_load_local_state_invalid_json(self, tmp_path):
        """Test loading invalid JSON returns empty state."""
        path = tmp_path / "invalid.json"
        path.write_text("{invalid json}")
        state = load_local_state(path)
        assert state.tools == {}

    def test_load_local_state_not_dict(self, tmp_path):
        """Test loading non-dict JSON returns empty state."""
        path = tmp_path / "array.json"
        path.write_text('["not", "a", "dict"]')
        state = load_local_state(path)
        assert state.tools == {}


class TestWriteLocalState:
    """Tests for write_local_state function."""

    def test_write_local_state_basic(self, tmp_path):
        """Test writing state file."""
        path = tmp_path / "local_state.json"
        state = LocalState(
            tools={"fd": LocalInstallation(installed_version="10.0.0")}
        )
        write_local_state(state, path)

        assert path.exists()
        data = json.loads(path.read_text())
        assert "tools" in data
        assert "fd" in data["tools"]
        assert data["tools"]["fd"]["installed_version"] == "10.0.0"

    def test_write_local_state_updates_metadata(self, tmp_path):
        """Test that write updates metadata fields."""
        path = tmp_path / "local_state.json"
        state = LocalState(
            tools={"tool": LocalInstallation(installed_version="1.0.0")}
        )

        write_local_state(state, path)

        # Check metadata was updated
        assert state.collected_at != ""
        assert "Z" in state.collected_at
        assert state.hostname != ""
        assert state.count == 1
        assert state.offline is False

    def test_write_local_state_offline_flag(self, tmp_path):
        """Test offline flag is set correctly."""
        path = tmp_path / "local_state.json"
        state = LocalState()

        write_local_state(state, path, offline=True)

        assert state.offline is True

    def test_write_local_state_counts_partial_failures(self, tmp_path):
        """Test partial failures are counted correctly."""
        path = tmp_path / "local_state.json"
        state = LocalState(
            tools={
                "good": LocalInstallation(installed_version="1.0.0", status="UP-TO-DATE"),
                "unknown1": LocalInstallation(status="UNKNOWN"),  # No version = failure
                "unknown2": LocalInstallation(installed_version="", status="UNKNOWN"),  # Empty = failure
                "unknown_with_ver": LocalInstallation(installed_version="2.0", status="UNKNOWN"),  # Has version = ok
            }
        )

        write_local_state(state, path)

        assert state.count == 4
        assert state.partial_failures == 2

    def test_write_local_state_atomic(self, tmp_path):
        """Test atomic write (no .tmp file left behind)."""
        path = tmp_path / "local_state.json"
        state = LocalState()
        write_local_state(state, path)

        # No temp file should exist
        temp_path = path.with_suffix(".tmp")
        assert not temp_path.exists()
        assert path.exists()


class TestStateHelpers:
    """Tests for state helper functions."""

    def test_get_local_installation_exists(self):
        """Test getting existing tool from state."""
        install = LocalInstallation(installed_version="5.0.0")
        state = LocalState(tools={"tool": install})
        result = get_local_installation("tool", state)
        assert result is not None
        assert result.installed_version == "5.0.0"

    def test_get_local_installation_not_exists(self):
        """Test getting non-existing tool from state."""
        state = LocalState()
        result = get_local_installation("nonexistent", state)
        assert result is None

    def test_update_local_installation(self):
        """Test updating tool in state."""
        state = LocalState()
        install = LocalInstallation(installed_version="1.0.0")
        update_local_installation("newtool", install, state)

        assert "newtool" in state.tools
        assert state.tools["newtool"].installed_version == "1.0.0"

    def test_update_local_installation_overwrite(self):
        """Test overwriting existing tool in state."""
        state = LocalState(
            tools={"tool": LocalInstallation(installed_version="1.0.0")}
        )
        new_install = LocalInstallation(installed_version="2.0.0")
        update_local_installation("tool", new_install, state)

        assert state.tools["tool"].installed_version == "2.0.0"


class TestMigrateFromSnapshot:
    """Tests for migrate_from_snapshot function."""

    def test_migrate_from_snapshot_basic(self):
        """Test basic migration from old snapshot format."""
        snapshot = {
            "__meta__": {
                "collected_at": "2025-01-01T00:00:00Z",
                "offline": True,
            },
            "tools": [
                {
                    "tool": "ripgrep",
                    "installed_version": "15.0.0",
                    "installed_path_selected": "/usr/local/bin/rg",
                    "installed_method": "cargo",
                    "status": "UP-TO-DATE",
                    "classification_reason_selected": "cargo install",
                    "category": "rust-core",
                    "hint": "cargo install ripgrep",
                },
            ],
        }
        state = migrate_from_snapshot(snapshot)

        assert "ripgrep" in state.tools
        assert state.tools["ripgrep"].installed_version == "15.0.0"
        assert state.tools["ripgrep"].installed_path == "/usr/local/bin/rg"
        assert state.tools["ripgrep"].installed_method == "cargo"
        assert state.tools["ripgrep"].status == "UP-TO-DATE"
        assert state.tools["ripgrep"].category == "rust-core"
        assert state.collected_at == "2025-01-01T00:00:00Z"
        assert state.offline is True

    def test_migrate_from_snapshot_empty(self):
        """Test migration from empty snapshot."""
        snapshot = {"tools": []}
        state = migrate_from_snapshot(snapshot)
        assert state.tools == {}

    def test_migrate_from_snapshot_missing_tool_name(self):
        """Test migration skips entries without tool name."""
        snapshot = {
            "tools": [
                {"installed_version": "1.0.0"},  # No tool name
                {"tool": "valid", "installed_version": "2.0.0"},
            ]
        }
        state = migrate_from_snapshot(snapshot)
        assert len(state.tools) == 1
        assert "valid" in state.tools

    def test_migrate_from_snapshot_multiple_tools(self):
        """Test migration of multiple tools."""
        snapshot = {
            "tools": [
                {"tool": "fd", "installed_version": "10.0.0", "status": "UP-TO-DATE"},
                {"tool": "bat", "installed_version": "0.25.0", "status": "OUTDATED"},
                {"tool": "uv", "installed_version": "0.5.0", "status": "UP-TO-DATE"},
            ]
        }
        state = migrate_from_snapshot(snapshot)
        assert len(state.tools) == 3
        assert "fd" in state.tools
        assert "bat" in state.tools
        assert "uv" in state.tools


class TestMergeForDisplay:
    """Tests for merge_for_display function."""

    def test_merge_for_display_empty(self):
        """Test merging empty cache and state."""
        upstream = UpstreamCache()
        local = LocalState()
        result = merge_for_display(upstream, local)
        assert result == []

    def test_merge_for_display_upstream_only(self):
        """Test merging with only upstream data."""
        upstream = UpstreamCache(
            versions={"fd": UpstreamVersion(latest_version="10.0.0")}
        )
        local = LocalState()
        result = merge_for_display(upstream, local)

        assert len(result) == 1
        assert result[0]["tool"] == "fd"
        assert result[0]["latest_version"] == "10.0.0"
        assert result[0]["installed_version"] == ""  # No local data

    def test_merge_for_display_local_only(self):
        """Test merging with only local data."""
        upstream = UpstreamCache()
        local = LocalState(
            tools={"bat": LocalInstallation(installed_version="0.25.0")}
        )
        result = merge_for_display(upstream, local)

        assert len(result) == 1
        assert result[0]["tool"] == "bat"
        assert result[0]["installed_version"] == "0.25.0"
        assert result[0]["latest_version"] == ""  # No upstream data

    def test_merge_for_display_both(self):
        """Test merging with both upstream and local data."""
        upstream = UpstreamCache(
            versions={
                "ripgrep": UpstreamVersion(
                    latest_tag="v15.1.0",
                    latest_version="15.1.0",
                    tool_url="https://github.com/BurntSushi/ripgrep",
                    upstream_method="gh",
                ),
            }
        )
        local = LocalState(
            tools={
                "ripgrep": LocalInstallation(
                    installed_version="15.0.0",
                    installed_method="cargo",
                    status="OUTDATED",
                    category="rust-core",
                ),
            }
        )
        result = merge_for_display(upstream, local)

        assert len(result) == 1
        tool = result[0]
        assert tool["tool"] == "ripgrep"
        # Upstream data
        assert tool["latest_upstream"] == "v15.1.0"
        assert tool["latest_version"] == "15.1.0"
        assert tool["tool_url"] == "https://github.com/BurntSushi/ripgrep"
        # Local data
        assert tool["installed_version"] == "15.0.0"
        assert tool["installed_method"] == "cargo"
        assert tool["status"] == "OUTDATED"
        assert tool["category"] == "rust-core"

    def test_merge_for_display_sorted(self):
        """Test that merged tools are sorted alphabetically."""
        upstream = UpstreamCache(
            versions={
                "zoxide": UpstreamVersion(latest_version="0.9.0"),
                "bat": UpstreamVersion(latest_version="0.25.0"),
            }
        )
        local = LocalState(
            tools={
                "fd": LocalInstallation(installed_version="10.0.0"),
                "atuin": LocalInstallation(installed_version="18.0.0"),
            }
        )
        result = merge_for_display(upstream, local)

        assert len(result) == 4
        tool_names = [t["tool"] for t in result]
        assert tool_names == ["atuin", "bat", "fd", "zoxide"]


class TestBuildLegacySnapshot:
    """Tests for build_legacy_snapshot function."""

    def test_build_legacy_snapshot_empty(self):
        """Test building legacy snapshot from empty data."""
        upstream = UpstreamCache()
        local = LocalState()
        snapshot = build_legacy_snapshot(upstream, local)

        assert "__meta__" in snapshot
        assert snapshot["__meta__"]["schema_version"] == 1
        assert snapshot["__meta__"]["count"] == 0
        assert "tools" in snapshot
        assert snapshot["tools"] == []

    def test_build_legacy_snapshot_with_data(self):
        """Test building legacy snapshot with real data."""
        upstream = UpstreamCache(
            versions={"fd": UpstreamVersion(latest_version="10.0.0")},
            baseline_updated_at="2025-01-01T00:00:00Z",
        )
        local = LocalState(
            tools={"fd": LocalInstallation(installed_version="9.0.0", status="OUTDATED")},
            collected_at="2025-01-02T00:00:00Z",
            offline=False,
            partial_failures=0,
        )
        snapshot = build_legacy_snapshot(upstream, local)

        assert snapshot["__meta__"]["schema_version"] == 1
        assert snapshot["__meta__"]["collected_at"] == "2025-01-02T00:00:00Z"
        assert snapshot["__meta__"]["offline"] is False
        assert snapshot["__meta__"]["count"] == 1
        assert len(snapshot["tools"]) == 1
        assert snapshot["tools"][0]["tool"] == "fd"
        assert snapshot["tools"][0]["installed_version"] == "9.0.0"
        assert snapshot["tools"][0]["latest_version"] == "10.0.0"

    def test_build_legacy_snapshot_uses_upstream_time_if_no_local(self):
        """Test that upstream timestamp is used if no local collected_at."""
        upstream = UpstreamCache(baseline_updated_at="2025-01-01T00:00:00Z")
        local = LocalState()
        snapshot = build_legacy_snapshot(upstream, local)

        assert snapshot["__meta__"]["created_at"] == "2025-01-01T00:00:00Z"
