"""Tests for dispenser-increment rounding (apply_dispenser_increment)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.normalization import apply_dispenser_increment  # noqa: E402


def test_increment_zero_is_noop() -> None:
    df = pd.DataFrame({
        "Volume [uL]": [0.0042, 0.012],
        "stock_conc_mM": [10.0, 1.0],
        "well_vol_uL": [40.0, 40.0],
        "CONCuM": [1.05, 0.3],
    })
    out = apply_dispenser_increment(df, increment_nL=0)
    pd.testing.assert_frame_equal(out, df)


def test_increment_25nl_rounds_volume() -> None:
    df = pd.DataFrame({
        "Volume [uL]": [0.004, 0.012, 0.0625],
        "stock_conc_mM": [10.0, 10.0, 10.0],
        "well_vol_uL": [40.0, 40.0, 40.0],
        "CONCuM": [1.0, 3.0, 15.625],
    })
    out = apply_dispenser_increment(df, increment_nL=2.5)
    # 4.0 -> 5.0, 12.0 -> 12.5, 62.5 -> 62.5 (already a multiple)
    assert list((out["Volume [uL]"] * 1000).round(2)) == [5.0, 12.5, 62.5]


def test_increment_back_calculates_concum() -> None:
    df = pd.DataFrame({
        "Volume [uL]": [0.004],
        "stock_conc_mM": [10.0],
        "well_vol_uL": [40.0],
        "CONCuM": [1.0],
    })
    out = apply_dispenser_increment(df, increment_nL=2.5)
    # 5.0 nL * 10 mM * 1000 / (40 uL * 1000) = 1.25 uM
    assert round(out["CONCuM"].iloc[0], 4) == 1.25
    assert out["CONCuM_requested"].iloc[0] == 1.0
    assert round(out["Volume_nL_unrounded"].iloc[0], 4) == 4.0


def test_increment_skips_solvent_rows_with_zero_stock() -> None:
    df = pd.DataFrame({
        "Volume [uL]": [0.0125],
        "stock_conc_mM": [0.0],
        "well_vol_uL": [40.0],
        "CONCuM": [0.0],
    })
    out = apply_dispenser_increment(df, increment_nL=2.5)
    assert "CONCuM_requested" not in out.columns or pd.isna(out["CONCuM_requested"].iloc[0])
    assert round(out["Volume [uL]"].iloc[0] * 1000, 2) == 12.5
