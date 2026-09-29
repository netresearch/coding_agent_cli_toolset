# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""The package version stated in code matches the one the release builds.

The release workflow builds the distribution with ``python -m build``, which
takes the version from ``[project].version`` in ``pyproject.toml``.
``cli_audit.__version__`` is a second copy of it; it said ``2.0.0`` while the
build produced ``2.0.0a6``.
"""

import tomllib
from pathlib import Path

import cli_audit

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_dunder_version_matches_pyproject() -> None:
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as fh:
        declared = tomllib.load(fh)["project"]["version"]
    assert cli_audit.__version__ == declared
    assert cli_audit.VERSION == declared
