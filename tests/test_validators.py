"""Tests for iplaid.validators.validate_solvent_normalization."""
from __future__ import annotations

import pandas as pd
import pytest

from iplaid.validators import validate_solvent_normalization


REQUIRED_COLUMNS = [
    "solvent_key", "solvent_family", "solvent_total_uL", "solvent_target_uL",
    "solvent_cap_pct", "solvent_cap_uL", "solvent_topup_uL", "is_solvent_control",
]


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)


def test_accepts_equalized_family_under_cap():
    df = _df([
        {"solvent_key": "dmso", "solvent_family": "DMSO",
         "solvent_total_uL": 0.04, "solvent_target_uL": 0.04,
         "solvent_cap_pct": 0.5, "solvent_cap_uL": 0.20,
         "solvent_topup_uL": 0.02, "is_solvent_control": False},
        {"solvent_key": "dmso", "solvent_family": "DMSO",
         "solvent_total_uL": 0.04, "solvent_target_uL": 0.04,
         "solvent_cap_pct": 0.5, "solvent_cap_uL": 0.20,
         "solvent_topup_uL": 0.04, "is_solvent_control": True},
    ])
    summaries = validate_solvent_normalization(df)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["solvent"] == "DMSO"
    assert s["compoundWellCount"] == 1
    assert s["controlWellCount"] == 1


def test_rejects_unequalized_totals_within_family():
    df = _df([
        {"solvent_key": "dmso", "solvent_family": "DMSO",
         "solvent_total_uL": 0.04, "solvent_target_uL": 0.04,
         "solvent_cap_pct": 0.5, "solvent_cap_uL": 0.20,
         "solvent_topup_uL": 0.02, "is_solvent_control": False},
        {"solvent_key": "dmso", "solvent_family": "DMSO",
         "solvent_total_uL": 0.05,  # not equal to target_uL
         "solvent_target_uL": 0.04,
         "solvent_cap_pct": 0.5, "solvent_cap_uL": 0.20,
         "solvent_topup_uL": 0.03, "is_solvent_control": False},
    ])
    with pytest.raises(ValueError, match="not identical"):
        validate_solvent_normalization(df)


def test_rejects_total_exceeding_configured_cap():
    df = _df([
        {"solvent_key": "dmso", "solvent_family": "DMSO",
         "solvent_total_uL": 0.30,  # exceeds cap of 0.20
         "solvent_target_uL": 0.30,
         "solvent_cap_pct": 0.5, "solvent_cap_uL": 0.20,
         "solvent_topup_uL": 0.0, "is_solvent_control": False},
    ])
    with pytest.raises(ValueError, match="solvent cap"):
        validate_solvent_normalization(df)


def test_rejects_missing_required_columns():
    df = pd.DataFrame([{"solvent_key": "dmso"}])
    with pytest.raises(ValueError, match="Missing solvent normalization columns"):
        validate_solvent_normalization(df)
