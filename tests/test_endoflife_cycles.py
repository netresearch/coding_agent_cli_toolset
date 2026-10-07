# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""cli_audit.collectors.collect_endoflife — the cycles it hands on.

A cycle becomes part of tool keys (``python@3.13``), binary names and
installer environment values, so only release-number shaped cycles leave the
collector, whether they come from the API or from the file cache.
"""

import json

import pytest

from cli_audit import collectors


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(collectors, "_ENDOFLIFE_CACHE_PATH", str(tmp_path / "endoflife.json"))
    monkeypatch.setattr(collectors, "_endoflife_memo", {})
    return tmp_path


def _entry(cycle):
    return {"cycle": cycle, "eol": False, "support": False, "latest": f"{cycle}.0"}


def test_release_number_cycles_are_returned(monkeypatch):
    payload = [_entry("3.14"), _entry("24"), _entry("1.23")]
    monkeypatch.setattr(collectors, "http_get", lambda url, timeout=5: json.dumps(payload).encode())

    cycles = [e["cycle"] for e in collectors.collect_endoflife("python", max_versions=10)]

    assert cycles == ["3.14", "24", "1.23"]


def test_cycles_of_another_shape_are_dropped(monkeypatch):
    payload = [_entry("3.14"), _entry("3.13'; x"), _entry("../3"), _entry("3.12")]
    monkeypatch.setattr(collectors, "http_get", lambda url, timeout=5: json.dumps(payload).encode())

    cycles = [e["cycle"] for e in collectors.collect_endoflife("python", max_versions=10)]

    assert cycles == ["3.14", "3.12"]


def test_cached_cycles_of_another_shape_are_dropped(isolated, monkeypatch):
    cache = {"python:10": {"at": 0, "entries": [_entry("3.14"), _entry("$(x)"), _entry("3.12")]}}
    (isolated / "endoflife.json").write_text(json.dumps(cache))

    def offline(url, timeout=5):
        raise OSError("offline")

    monkeypatch.setattr(collectors, "http_get", offline)

    cycles = [e["cycle"] for e in collectors.collect_endoflife("python", max_versions=10)]

    assert cycles == ["3.14", "3.12"]
