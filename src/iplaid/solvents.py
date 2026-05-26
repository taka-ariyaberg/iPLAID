from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

_DEFAULT_CAPS_PATH = Path(__file__).resolve().parents[2] / "data" / "solvent_default_caps.json"


@lru_cache(maxsize=1)
def load_default_caps() -> dict[str, float]:
    """Load the per-solvent default cap table (keys are label_key form)."""
    raw = json.loads(_DEFAULT_CAPS_PATH.read_text(encoding="utf-8"))
    return {str(k).strip().lower(): float(v) for k, v in raw.items()}


def default_cap_for(solvent_name: str) -> float:
    """Default cap % for a solvent family, normalized by label_key, with fallback."""
    caps = load_default_caps()
    key = label_key(solvent_name)
    return caps.get(key, caps.get("default", 0.1))


def clean_label(value: Any) -> str:
    """Return a trimmed string label, preserving the original display case."""
    return "" if value is None else str(value).strip()


def label_key(value: Any) -> str:
    """Return a case-insensitive key for matching labels safely."""
    return clean_label(value).casefold()


def normalize_solvent_caps(raw_caps: Any) -> dict[str, float]:
    """
    Normalize an optional solvent cap mapping.

    Expected input shape:
      {"DMSO": 0.1, "Ethanol": 0.2, "default": 0.1}
    """
    if raw_caps in (None, "", {}):
        return {}
    if not isinstance(raw_caps, Mapping):
        raise ValueError("solvent_caps_pct must be a mapping of solvent names to percentages.")

    normalized: dict[str, float] = {}
    for raw_name, raw_value in raw_caps.items():
        key = label_key(raw_name)
        if not key:
            continue
        try:
            pct = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid solvent cap for {clean_label(raw_name) or '<blank>'}.") from exc
        if pct <= 0:
            raise ValueError(f"Solvent cap for {clean_label(raw_name) or '<blank>'} must be > 0.")
        normalized[key] = pct

    return normalized


def get_solvent_cap_pct(config: Mapping[str, Any], solvent_name: str) -> float:
    """
    Resolve the configured percentage cap for a solvent family.

    Backward compatibility:
      - if `solvent_caps_pct` is provided and contains the solvent, use it
      - else if `solvent_caps_pct.default` exists, use it
      - else fall back to legacy `max_dmso_pct`
    """
    caps = normalize_solvent_caps(config.get("solvent_caps_pct"))
    solvent_key = label_key(solvent_name)

    if solvent_key in caps:
        return caps[solvent_key]
    if "default" in caps:
        return caps["default"]
    if "*" in caps:
        return caps["*"]

    if "max_dmso_pct" not in config:
        raise KeyError(f"Missing solvent cap for {clean_label(solvent_name)}.")

    pct = float(config["max_dmso_pct"])
    if pct <= 0:
        raise ValueError("max_dmso_pct must be > 0.")
    return pct
