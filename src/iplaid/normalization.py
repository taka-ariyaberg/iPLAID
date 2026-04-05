"""
Normalization Module

Consolidates data transformation operations:
- Target well and volume column assignment
- DMSO normalization and top-up calculation
- Volume cap enforcement
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# DMSO normalization
def normalize_dmso_topup(
    df: pd.DataFrame,
    *,
    max_dmso_pct: float,
    working_volume_ul: float,
) -> tuple[pd.DataFrame, float, float]:
    """
    Normalize DMSO to be identical across all wells, respecting maximum percentage cap.
    
    Calculates how much additional DMSO to add to each well so that the total DMSO
    is identical across all wells and does not exceed the specified percentage cap.
    
    Args:
        df: DataFrame with Volume [uL] and solvent columns
        max_dmso_pct: Maximum DMSO percentage of working volume
        working_volume_ul: Target well working volume
        
    Returns:
        Tuple of (modified_df, target_dmso_ul, max_dmso_ul)
        
    Raises:
        ValueError: If DMSO constraints cannot be satisfied
    """
    df = df.copy()

    max_dmso_ul = (max_dmso_pct / 100.0) * working_volume_ul

    df["dmso_from_compound_uL"] = np.where(
        df["solvent"].astype(str).str.upper().eq("DMSO"),
        df["Volume [uL]"].astype(float),
        0.0
    )

    target_dmso_ul = float(df["dmso_from_compound_uL"].max())

    if target_dmso_ul > max_dmso_ul + 1e-12:
        raise ValueError(
            f"DMSO normalization impossible under the current cap:\n"
            f"  required max DMSO = {target_dmso_ul:.6f} uL\n"
            f"  allowed cap       = {max_dmso_ul:.6f} uL ({max_dmso_pct}% of {working_volume_ul} uL)"
        )

    df["dmso_topup_uL"] = (target_dmso_ul - df["dmso_from_compound_uL"]).clip(lower=0.0)

    is_dmso_control = (
        df["cmpdname"].astype(str).str.strip().str.lower().eq("dmso")
        | df.get("treatment_type", pd.Series("", index=df.index)).astype(str).str.upper().str.contains("DMSO", na=False)
    )
    df.loc[is_dmso_control, "dmso_from_compound_uL"] = 0.0
    df.loc[is_dmso_control, "dmso_topup_uL"] = target_dmso_ul

    df["dmso_total_uL"] = df["dmso_from_compound_uL"] + df["dmso_topup_uL"]

    if not np.allclose(df["dmso_total_uL"].values, target_dmso_ul, atol=1e-9):
        raise ValueError("DMSO normalization failed: final DMSO is not identical across all wells.")

    if df["dmso_total_uL"].max() > max_dmso_ul + 1e-12:
        raise ValueError("DMSO normalization failed: exceeded MAX_DMSO_PCT cap.")

    return df, target_dmso_ul, max_dmso_ul


# Volume calculation and normalization
def add_target_and_volume_columns(
    df: pd.DataFrame,
    *,
    remove_leading_zero_fn,
    volume_from_stock_fn,
    working_volume_ul: float,
) -> pd.DataFrame:
    """
    Add target well, target plate, liquid name, and volume columns.
    
    Args:
        df: DataFrame with plateID, well, cmpdname, stock_conc_mM, CONCuM columns
        remove_leading_zero_fn: Function to format well names
        volume_from_stock_fn: Function to calculate volume from stock
        working_volume_ul: Target well working volume
        
    Returns:
        DataFrame with additional columns
        
    Raises:
        ValueError: If volume calculation fails
    """
    df = df.copy()

    df["Target Plate"] = df["plateID"].astype(str)
    df["Target Well"] = df["well"].astype(str).map(remove_leading_zero_fn)
    df["Liquid Name"] = "[" + df["cmpdname"].astype(str) + "][" + df["stock_conc_mM"].astype(str) + "]"

    df["Volume [uL]"] = df.apply(
        lambda r: volume_from_stock_fn(r["CONCuM"], r["stock_conc_mM"], working_volume_ul),
        axis=1
    )

    if df["Volume [uL]"].isna().any():
        raise ValueError(
            "Volume calculation failed for some rows. "
            "Check CONCuM/stock_conc_mM and volume_from_stock()."
        )

    return df


def enforce_dmso_volume_cap(
    df: pd.DataFrame,
    *,
    max_dmso_pct: float,
    working_volume_ul: float,
) -> tuple[pd.DataFrame, float]:
    """
    Check that DMSO volumes don't exceed cap.
    
    Args:
        df: DataFrame with Volume [uL] column
        max_dmso_pct: Maximum DMSO percentage of working volume
        working_volume_ul: Target well working volume
        
    Returns:
        Tuple of (df, max_dmso_ul)
        
    Raises:
        ValueError: If any volume exceeds cap
    """
    df = df.copy()
    max_dmso_ul = (max_dmso_pct / 100.0) * working_volume_ul
    too_high = df.loc[df["Volume [uL]"] > max_dmso_ul]

    if len(too_high) > 0:
        raise ValueError(
            f"DMSO limit exceeded: Volume [uL] > {max_dmso_ul:.6f} uL "
            f"(>{max_dmso_pct}% of {working_volume_ul} uL)."
        )

    return df, max_dmso_ul
