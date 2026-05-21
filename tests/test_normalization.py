"""Tests for iplaid.normalization — apply_dispenser_increment + normalize_solvent_topup."""
from __future__ import annotations

import numpy as np
import pandas as pd

from iplaid.normalization import apply_dispenser_increment, normalize_solvent_topup


# ---- apply_dispenser_increment ----------------------------------------------


def test_increment_zero_is_noop():
    df = pd.DataFrame({
        "Volume [uL]": [0.0042, 0.012],
        "stock_conc_mM": [10.0, 1.0],
        "well_vol_uL": [40.0, 40.0],
        "CONCuM": [1.05, 0.3],
    })
    out = apply_dispenser_increment(df, increment_nL=0)
    pd.testing.assert_frame_equal(out, df)


def test_increment_25nl_rounds_volume():
    df = pd.DataFrame({
        "Volume [uL]": [0.004, 0.012, 0.0625],
        "stock_conc_mM": [10.0, 10.0, 10.0],
        "well_vol_uL": [40.0, 40.0, 40.0],
        "CONCuM": [1.0, 3.0, 15.625],
    })
    out = apply_dispenser_increment(df, increment_nL=2.5)
    # 4.0 → 5.0, 12.0 → 12.5, 62.5 → 62.5 (already a multiple)
    assert list((out["Volume [uL]"] * 1000).round(2)) == [5.0, 12.5, 62.5]


def test_increment_back_calculates_concum():
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


def test_increment_skips_solvent_rows_with_zero_stock():
    df = pd.DataFrame({
        "Volume [uL]": [0.0125],
        "stock_conc_mM": [0.0],
        "well_vol_uL": [40.0],
        "CONCuM": [0.0],
    })
    out = apply_dispenser_increment(df, increment_nL=2.5)
    assert "CONCuM_requested" not in out.columns or pd.isna(out["CONCuM_requested"].iloc[0])
    assert round(out["Volume [uL]"].iloc[0] * 1000, 2) == 12.5


# ---- normalize_solvent_topup ------------------------------------------------


def test_solvent_topup_equalizes_total_within_family():
    """All wells in a solvent family end up with identical solvent_total_uL."""
    df = pd.DataFrame({
        "cmpdname": ["CompA", "CompB", "CompC"],
        "CONCuM": [10, 20, 30],
        "solvent": ["DMSO", "DMSO", "DMSO"],
        "Volume [uL]": [0.01, 0.02, 0.03],
        "is_solvent_control": [False, False, False],
    })
    out, summary = normalize_solvent_topup(
        df, config={"max_dmso_pct": 0.5}, working_volume_ul=40.0,
    )
    totals = out["solvent_total_uL"].values
    assert np.allclose(totals, totals[0])
    # Target equals the max compound-contributed volume (0.03).
    assert abs(totals[0] - 0.03) < 1e-9
    assert summary[0]["solvent"] == "DMSO"
    assert summary[0]["compoundWellCount"] == 3


def test_solvent_topup_assigns_full_target_to_solvent_controls():
    df = pd.DataFrame({
        "cmpdname": ["CompA", "DMSO"],
        "CONCuM": [10, 0],
        "solvent": ["DMSO", "DMSO"],
        "Volume [uL]": [0.04, 0.0],
        "is_solvent_control": [False, True],
    })
    out, _ = normalize_solvent_topup(
        df, config={"max_dmso_pct": 0.5}, working_volume_ul=40.0,
    )
    control_row = out.loc[out["cmpdname"] == "DMSO"].iloc[0]
    # Control row receives the entire family target as top-up.
    assert abs(control_row["solvent_topup_uL"] - 0.04) < 1e-9
    assert abs(control_row["solvent_total_uL"] - 0.04) < 1e-9
