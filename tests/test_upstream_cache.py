"""
Tests for upstream version cache management (cli_audit/upstream_cache.py).

Target coverage: 85%+
"""

import json
import os
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from cli_audit.upstream_cache import (
    UpstreamVersion,
    UpstreamCache,
    get_upstream_cache_path,
    load_upstream_cache,
    write_upstream_cache,
    get_cached_upstream,
    update_cached_upstream,
    is_cache_stale,
    migrate_from_snapshot,
    DEFAULT_UPSTREAM_FILE,
    DEFAULT_MAX_AGE_HOURS,
)


class TestUpstreamVersion:
    """Tests for UpstreamVersion dataclass."""

    def test_upstream_version_defaults(self):
        """Test UpstreamVersion with default values."""
        version = UpstreamVersion()
        assert version.latest_tag == ""
        assert version.latest_version == ""
        assert version.latest_url == ""
        assert version.tool_url == ""
        assert version.upstream_method == ""

    def test_upstream_version_custom_values(self):
        """Test UpstreamVersion with custom values."""
        version = UpstreamVersion(
            latest_tag="v1.2.3",
            latest_version="1.2.3",
            latest_url="https://github.com/org/repo/releases/tag/v1.2.3",
            tool_url="https://github.com/org/repo",
            upstream_method="gh",
        )
        assert version.latest_tag == "v1.2.3"
        assert version.latest_version == "1.2.3"
        assert version.latest_url == "https://github.com/org/repo/releases/tag/v1.2.3"
        assert version.tool_url == "https://github.com/org/repo"
        assert version.upstream_method == "gh"

    def test_upstream_version_to_dict(self):
        """Test UpstreamVersion to_dict serialization."""
        version = UpstreamVersion(
            latest_tag="v2.0.0",
            latest_version="2.0.0",
            latest_url="https://example.com/release",
            tool_url="https://example.com",
            upstream_method="pypi",
        )
        d = version.to_dict()
        assert d["latest_tag"] == "v2.0.0"
        assert d["latest_version"] == "2.0.0"
        assert d["latest_url"] == "https://example.com/release"
        assert d["tool_url"] == "https://example.com"
        assert d["upstream_method"] == "pypi"

    def test_upstream_version_from_dict(self):
        """Test creating UpstreamVersion from dictionary."""
        data = {
            "latest_tag": "v3.0.0",
            "latest_version": "3.0.0",
            "latest_url": "https://test.com/v3",
            "tool_url": "https://test.com",
            "upstream_method": "npm",
        }
        version = UpstreamVersion.from_dict(data)
        assert version.latest_tag == "v3.0.0"
        assert version.latest_version == "3.0.0"
        assert version.latest_url == "https://test.com/v3"
        assert version.tool_url == "https://test.com"
        assert version.upstream_method == "npm"

    def test_upstream_version_from_dict_partial(self):
        """Test creating UpstreamVersion from partial dictionary."""
        data = {"latest_version": "1.0.0"}
        version = UpstreamVersion.from_dict(data)
        assert version.latest_tag == ""  # Default
        assert version.latest_version == "1.0.0"
        assert version.latest_url == ""  # Default
        assert version.tool_url == ""  # Default
        assert version.upstream_method == ""  # Default

    def test_upstream_version_from_dict_empty(self):
        """Test creating UpstreamVersion from empty dictionary."""
        version = UpstreamVersion.from_dict({})
        assert version.latest_tag == ""
        assert version.latest_version == ""
        assert version.latest_url == ""
        assert version.tool_url == ""
        assert version.upstream_method == ""


class TestUpstreamCache:
    """Tests for UpstreamCache dataclass."""

    def test_upstream_cache_defaults(self):
        """Test UpstreamCache with default values."""
        cache = UpstreamCache()
        assert cache.versions == {}
        assert cache.schema_version == 2
        assert cache.baseline_updated_at == ""
        assert cache.source == "github/pypi/npm/crates API"

    def test_upstream_cache_custom_values(self):
        """Test UpstreamCache with custom values."""
        versions = {"ripgrep": UpstreamVersion(latest_version="15.0.0")}
        cache = UpstreamCache(
            versions=versions,
            schema_version=2,
            baseline_updated_at="2025-01-01T00:00:00Z",
            source="custom source",
        )
        assert "ripgrep" in cache.versions
        assert cache.schema_version == 2
        assert cache.baseline_updated_at == "2025-01-01T00:00:00Z"
        assert cache.source == "custom source"

    def test_upstream_cache_to_dict(self):
        """Test UpstreamCache to_dict serialization."""
        versions = {
            "fd": UpstreamVersion(latest_version="10.0.0", upstream_method="gh"),
        }
        cache = UpstreamCache(
            versions=versions,
            baseline_updated_at="2025-06-01T12:00:00Z",
        )
        d = cache.to_dict()
        assert "__meta__" in d
        assert d["__meta__"]["schema_version"] == 2
        assert d["__meta__"]["baseline_updated_at"] == "2025-06-01T12:00:00Z"
        assert "versions" in d
        assert "fd" in d["versions"]
        assert d["versions"]["fd"]["latest_version"] == "10.0.0"

    def test_upstream_cache_from_dict(self):
        """Test creating UpstreamCache from dictionary."""
        data = {
            "__meta__": {
                "schema_version": 2,
                "baseline_updated_at": "2025-03-15T08:30:00Z",
                "source": "test source",
            },
            "versions": {
                "bat": {
                    "latest_tag": "v0.25.0",
                    "latest_version": "0.25.0",
                    "upstream_method": "gh",
                },
            },
        }
        cache = UpstreamCache.from_dict(data)
        assert cache.schema_version == 2
        assert cache.baseline_updated_at == "2025-03-15T08:30:00Z"
        assert cache.source == "test source"
        assert "bat" in cache.versions
        assert cache.versions["bat"].latest_version == "0.25.0"

    def test_upstream_cache_from_dict_empty(self):
        """Test creating UpstreamCache from empty dictionary."""
        cache = UpstreamCache.from_dict({})
        assert cache.versions == {}
        assert cache.schema_version == 2
        assert cache.baseline_updated_at == ""
        assert cache.source == ""


class TestGetUpstreamCachePath:
    """Tests for get_upstream_cache_path function."""

    def test_get_upstream_cache_path_default(self, monkeypatch):
        """Test default path resolution."""
        monkeypatch.delenv("CLI_AUDIT_UPSTREAM_FILE", raising=False)
        path = get_upstream_cache_path()
        assert path.name == DEFAULT_UPSTREAM_FILE
        assert path.parent == Path.cwd()

    def test_get_upstream_cache_path_env_relative(self, monkeypatch):
        """Test relative path from environment variable."""
        monkeypatch.setenv("CLI_AUDIT_UPSTREAM_FILE", "custom_upstream.json")
        path = get_upstream_cache_path()
        assert path.name == "custom_upstream.json"
        assert path.parent == Path.cwd()

    def test_get_upstream_cache_path_env_absolute(self, monkeypatch, tmp_path):
        """Test absolute path from environment variable."""
        test_path = tmp_path / "upstream.json"
        monkeypatch.setenv("CLI_AUDIT_UPSTREAM_FILE", str(test_path))
        path = get_upstream_cache_path()
        assert path == test_path


class TestLoadUpstreamCache:
    """Tests for load_upstream_cache function."""

    def test_load_upstream_cache_not_found(self, tmp_path):
        """Test loading from non-existent file returns empty cache."""
        path = tmp_path / "nonexistent.json"
        cache = load_upstream_cache(path)
        assert cache.versions == {}

    def test_load_upstream_cache_valid(self, tmp_path):
        """Test loading valid cache file."""
        path = tmp_path / "upstream.json"
        data = {
            "__meta__": {
                "schema_version": 2,
                "baseline_updated_at": "2025-01-01T00:00:00Z",
            },
            "versions": {
                "ripgrep": {
                    "latest_version": "15.0.0",
                    "upstream_method": "gh",
                },
            },
        }
        path.write_text(json.dumps(data))
        cache = load_upstream_cache(path)
        assert "ripgrep" in cache.versions
        assert cache.versions["ripgrep"].latest_version == "15.0.0"

    def test_load_upstream_cache_invalid_json(self, tmp_path):
        """Test loading invalid JSON returns empty cache."""
        path = tmp_path / "invalid.json"
        path.write_text("{invalid json}")
        cache = load_upstream_cache(path)
        assert cache.versions == {}

    def test_load_upstream_cache_not_dict(self, tmp_path):
        """Test loading non-dict JSON returns empty cache."""
        path = tmp_path / "array.json"
        path.write_text('["not", "a", "dict"]')
        cache = load_upstream_cache(path)
        assert cache.versions == {}


class TestWriteUpstreamCache:
    """Tests for write_upstream_cache function."""

    def test_write_upstream_cache_basic(self, tmp_path):
        """Test writing cache file."""
        path = tmp_path / "upstream.json"
        cache = UpstreamCache(
            versions={"fd": UpstreamVersion(latest_version="10.0.0")}
        )
        write_upstream_cache(cache, path)

        assert path.exists()
        data = json.loads(path.read_text())
        assert "versions" in data
        assert "fd" in data["versions"]
        assert data["versions"]["fd"]["latest_version"] == "10.0.0"

    def test_write_upstream_cache_updates_timestamp(self, tmp_path):
        """Test that write updates baseline_updated_at timestamp."""
        path = tmp_path / "upstream.json"
        cache = UpstreamCache()
        assert cache.baseline_updated_at == ""

        write_upstream_cache(cache, path)

        # Timestamp should be set after write
        assert cache.baseline_updated_at != ""
        assert "Z" in cache.baseline_updated_at

    def test_write_upstream_cache_atomic(self, tmp_path):
        """Test atomic write (no .tmp file left behind)."""
        path = tmp_path / "upstream.json"
        cache = UpstreamCache()
        write_upstream_cache(cache, path)

        # No temp file should exist
        temp_path = path.with_suffix(".tmp")
        assert not temp_path.exists()
        assert path.exists()


class TestCacheHelpers:
    """Tests for cache helper functions."""

    def test_get_cached_upstream_exists(self):
        """Test getting existing tool from cache."""
        version = UpstreamVersion(latest_version="5.0.0")
        cache = UpstreamCache(versions={"tool": version})
        result = get_cached_upstream("tool", cache)
        assert result is not None
        assert result.latest_version == "5.0.0"

    def test_get_cached_upstream_not_exists(self):
        """Test getting non-existing tool from cache."""
        cache = UpstreamCache()
        result = get_cached_upstream("nonexistent", cache)
        assert result is None

    def test_update_cached_upstream(self):
        """Test updating tool in cache."""
        cache = UpstreamCache()
        version = UpstreamVersion(latest_version="1.0.0")
        update_cached_upstream("newtool", version, cache)

        assert "newtool" in cache.versions
        assert cache.versions["newtool"].latest_version == "1.0.0"

    def test_update_cached_upstream_overwrite(self):
        """Test overwriting existing tool in cache."""
        cache = UpstreamCache(
            versions={"tool": UpstreamVersion(latest_version="1.0.0")}
        )
        new_version = UpstreamVersion(latest_version="2.0.0")
        update_cached_upstream("tool", new_version, cache)

        assert cache.versions["tool"].latest_version == "2.0.0"


class TestIsCacheStale:
    """Tests for is_cache_stale function."""

    def test_is_cache_stale_no_timestamp(self):
        """Test cache without timestamp is considered stale."""
        cache = UpstreamCache()
        assert is_cache_stale(cache) is True

    def test_is_cache_stale_recent(self):
        """Test cache with recent timestamp is not stale."""
        now = datetime.now(timezone.utc)
        timestamp = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        cache = UpstreamCache(baseline_updated_at=timestamp)
        assert is_cache_stale(cache) is False

    def test_is_cache_stale_old(self):
        """Test cache with old timestamp is stale."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=DEFAULT_MAX_AGE_HOURS + 1)
        timestamp = old_time.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        cache = UpstreamCache(baseline_updated_at=timestamp)
        assert is_cache_stale(cache) is True

    def test_is_cache_stale_custom_max_age(self):
        """Test cache staleness with custom max age."""
        # 2 hours ago
        two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        timestamp = two_hours_ago.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        cache = UpstreamCache(baseline_updated_at=timestamp)

        # With 1 hour max, should be stale
        assert is_cache_stale(cache, max_age_hours=1) is True

        # With 3 hour max, should not be stale
        assert is_cache_stale(cache, max_age_hours=3) is False

    def test_is_cache_stale_invalid_timestamp(self):
        """Test cache with invalid timestamp is considered stale."""
        cache = UpstreamCache(baseline_updated_at="not-a-timestamp")
        assert is_cache_stale(cache) is True


class TestMigrateFromSnapshot:
    """Tests for migrate_from_snapshot function."""

    def test_migrate_from_snapshot_basic(self):
        """Test basic migration from old snapshot format."""
        snapshot = {
            "__meta__": {"collected_at": "2025-01-01T00:00:00Z"},
            "tools": [
                {
                    "tool": "ripgrep",
                    "latest_upstream": "v15.0.0",
                    "latest_version": "15.0.0",
                    "latest_url": "https://github.com/BurntSushi/ripgrep/releases",
                    "tool_url": "https://github.com/BurntSushi/ripgrep",
                    "upstream_method": "gh",
                },
            ],
        }
        cache = migrate_from_snapshot(snapshot)

        assert "ripgrep" in cache.versions
        assert cache.versions["ripgrep"].latest_tag == "v15.0.0"
        assert cache.versions["ripgrep"].latest_version == "15.0.0"
        assert cache.versions["ripgrep"].upstream_method == "gh"
        assert cache.baseline_updated_at == "2025-01-01T00:00:00Z"

    def test_migrate_from_snapshot_empty(self):
        """Test migration from empty snapshot."""
        snapshot = {"tools": []}
        cache = migrate_from_snapshot(snapshot)
        assert cache.versions == {}

    def test_migrate_from_snapshot_missing_tool_name(self):
        """Test migration skips entries without tool name."""
        snapshot = {
            "tools": [
                {"latest_version": "1.0.0"},  # No tool name
                {"tool": "valid", "latest_version": "2.0.0"},
            ]
        }
        cache = migrate_from_snapshot(snapshot)
        assert len(cache.versions) == 1
        assert "valid" in cache.versions

    def test_migrate_from_snapshot_preserves_timestamp(self):
        """Test that migration preserves collected_at timestamp."""
        snapshot = {
            "__meta__": {"collected_at": "2025-06-15T10:30:00Z"},
            "tools": [],
        }
        cache = migrate_from_snapshot(snapshot)
        assert cache.baseline_updated_at == "2025-06-15T10:30:00Z"

    def test_migrate_from_snapshot_multiple_tools(self):
        """Test migration of multiple tools."""
        snapshot = {
            "tools": [
                {"tool": "fd", "latest_version": "10.0.0", "upstream_method": "gh"},
                {"tool": "bat", "latest_version": "0.25.0", "upstream_method": "gh"},
                {"tool": "uv", "latest_version": "0.5.0", "upstream_method": "pypi"},
            ]
        }
        cache = migrate_from_snapshot(snapshot)
        assert len(cache.versions) == 3
        assert "fd" in cache.versions
        assert "bat" in cache.versions
        assert "uv" in cache.versions
