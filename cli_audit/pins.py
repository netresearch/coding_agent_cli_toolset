"""
Version-pin reader for ``~/.config/cli-audit/pins.json``.

Pins are managed by the shell scripts (``scripts/pin_version.sh``,
``scripts/unpin_version.sh``, ``scripts/reset_pins.sh``) and stored in a
user-local JSON file. The Python code only reads them.

File format::

    {
        "ripgrep":     "14.1.0",                 # single-version tool
        "php":         {"8.5": "8.5.3",          # multi-version tool
                        "8.4": "8.4.18",
                        "8.2": "never"},
        "node":        {"24": "never"}
    }

A value of ``"never"`` means "do not install or update" — effectively a
hard skip. Any other string is the pinned version. An empty/missing value
means not pinned.

Tool names may arrive as ``"python@3.13"`` (multi-version runtime) or a
plain single-version name. :func:`lookup_pin` handles both.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any


logger = logging.getLogger(__name__)


DEFAULT_PINS_PATH = os.path.expanduser(
    os.environ.get(
        "CLI_AUDIT_PINS_PATH",
        os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
            "cli-audit",
            "pins.json",
        ),
    )
)


@lru_cache(maxsize=1)
def _load_pins_cached(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.warning(
            "pins file %s is not valid JSON (%s); treating as empty. "
            "Run `scripts/reset_pins.sh` to rewrite, or edit the file by hand.",
            path,
            e,
        )
        return {}
    except OSError as e:
        logger.warning("cannot read pins file %s: %s; treating as empty.", path, e)
        return {}
    if not isinstance(data, dict):
        logger.warning(
            "pins file %s is valid JSON but not a top-level object; treating as empty.",
            path,
        )
        return {}
    return data


def load_pins(path: str | None = None) -> dict[str, Any]:
    """Load and return the pins mapping.

    Args:
        path: Optional override path. Defaults to
            ``~/.config/cli-audit/pins.json``.
    """
    return _load_pins_cached(path or DEFAULT_PINS_PATH)


def reset_cache() -> None:
    """Clear the in-process cache. Useful for tests."""
    _load_pins_cached.cache_clear()


def _split_tool(tool_name: str) -> tuple[str, str | None]:
    """Split ``"python@3.13"`` into ``("python", "3.13")``.

    Returns ``(base, None)`` for single-version tools.
    """
    if "@" in tool_name:
        base, cycle = tool_name.split("@", 1)
        return base, cycle
    return tool_name, None


def lookup_pin(tool_name: str, pins: dict[str, Any] | None = None) -> str:
    """Return the pinned value for a tool, or empty string if not pinned.

    ``"never"`` is a valid return value and means "never update/install".

    Shape-mismatched lookups (flat pin queried with ``tool@cycle``, or a
    nested pin queried bare) return empty — callers are expected to match
    the pin file's structure, and silent fallbacks would mask bugs.
    """
    pins = pins if pins is not None else load_pins()
    base, cycle = _split_tool(tool_name)
    entry = pins.get(base)
    if entry is None:
        return ""
    if isinstance(entry, dict):
        # Nested (multi-version) pin: caller must supply a cycle.
        if cycle is None:
            return ""
        value = entry.get(cycle, "")
        return value if isinstance(value, str) else ""
    # Flat (single-version) pin: caller must not supply a cycle.
    if cycle is not None:
        return ""
    return entry if isinstance(entry, str) else ""


def is_pinned(tool_name: str, pins: dict[str, Any] | None = None) -> bool:
    """True if the tool has any pin (including ``"never"``)."""
    return bool(lookup_pin(tool_name, pins))


def is_never(tool_name: str, pins: dict[str, Any] | None = None) -> bool:
    """True if the tool is pinned to the sentinel ``"never"``."""
    return lookup_pin(tool_name, pins) == "never"


def should_skip(tool_name: str, latest_version: str, pins: dict[str, Any] | None = None) -> bool:
    """True if updates for this tool should be skipped.

    Skip when the tool is pinned to ``"never"`` or when the pinned version
    already matches the latest upstream version.
    """
    pin = lookup_pin(tool_name, pins)
    if not pin:
        return False
    if pin == "never":
        return True
    return pin == latest_version


def classify_pin(pin: str, cycle: str | None) -> str:
    """Classify a pin value against the row's cycle (if any).

    The ``pins.json`` schema stores pins as strings but the same slot
    can mean three different things:

    - ``"never"``         → deliberately-not-installed sentinel
    - pin equal to cycle  → "hold this cycle, accept any patch"
    - anything else       → specific version pin (patch-level intent)

    For single-version tools ``cycle`` is ``None`` and every non-never
    pin is treated as a specific version.

    Returns one of: ``"none"``, ``"never"``, ``"cycle"``, ``"version"``.
    """
    if not pin:
        return "none"
    if pin == "never":
        return "never"
    if cycle is not None and pin == cycle:
        return "cycle"
    return "version"


def apply_pin_to_status(
    status: str,
    installed: str,
    pin: str,
    cycle: str | None = None,
) -> str:
    """Adjust a snapshot status value using the user's pin as the target.

    The snapshot's ``status`` is computed against ``latest_upstream`` and
    has no knowledge of pins. The pin is the user's stated target, so any
    downstream consumer (rendering, summary counts, bulk decisions) must
    respect it — ``UP-TO-DATE`` must not be reported on a row whose
    installed version diverges from the pin.

    Cycle-awareness (see :func:`classify_pin`): a pin value equal to the
    row's ``cycle`` (e.g. ``"3.12"`` on ``python@3.12``) means "hold this
    cycle, any patch", so an installed ``3.12.7`` is up-to-date with
    respect to the pin. For multi-version tools, a stale patch-level pin
    (installed differs from pin and pin is not the cycle) is left at its
    upstream status rather than escalated to ``CONFLICT``: the schema
    can't distinguish a deliberate patch-hold from a skip-marker that
    guide.sh left behind after the world moved on.

    Rules:

    - pin kind ``none``    → pass through.
    - pin kind ``never``
        - nothing installed  → ``UP-TO-DATE`` (pin honored).
        - something installed→ ``CONFLICT`` (user said never).
    - pin kind ``cycle``
        - nothing installed  → ``NOT INSTALLED``.
        - installed in cycle → ``UP-TO-DATE``.
        - installed elsewhere→ ``CONFLICT``.
    - pin kind ``version``
        - nothing installed  → ``NOT INSTALLED``.
        - installed == pin   → ``UP-TO-DATE``.
        - installed != pin, multi-version row → pass through (stale).
        - installed != pin, single-version row → ``CONFLICT``.
    """
    kind = classify_pin(pin, cycle)
    if kind == "none":
        return status
    if kind == "never":
        return "UP-TO-DATE" if not installed else "CONFLICT"
    if kind == "cycle":
        if not installed:
            return "NOT INSTALLED"
        # installed is within the pinned cycle if it equals the cycle
        # (e.g. bare "3.12") or looks like "3.12.x".
        assert cycle is not None  # guaranteed by classify_pin
        if installed == cycle or installed.startswith(cycle + "."):
            return "UP-TO-DATE"
        return "CONFLICT"
    # kind == "version" — specific patch/exact pin.
    if not installed:
        return "NOT INSTALLED"
    if installed == pin:
        return "UP-TO-DATE"
    if cycle is not None:
        # Multi-version: the patch-pin is either stale or the world
        # moved past it (see module docstring). Don't elevate.
        return status
    return "CONFLICT"


def pin_label(pin: str, cycle: str | None, installed: str) -> str:
    """Human-readable label for the pin suffix in the ``installed`` column.

    Returns an empty string when there's no pin. Otherwise one of:

    - ``PIN:never``
    - ``CYCLE:3.12``          (cycle-hold — pin matches the row's cycle)
    - ``PIN:8.5.3``           (explicit patch-hold, currently honored)
    - ``PIN:8.5.3 stale``     (patch-hold on a multi-version row where
                               installed no longer matches the pin — treated
                               as fossil data, kept visible for awareness)
    """
    kind = classify_pin(pin, cycle)
    if kind == "none":
        return ""
    if kind == "never":
        return "PIN:never"
    if kind == "cycle":
        return f"CYCLE:{pin}"
    # version
    if installed and installed != pin and cycle is not None:
        return f"PIN:{pin} stale"
    return f"PIN:{pin}"
