"""
Validators Module

Protocol validation checks and assertions:
- Export file structure validation
- DMSO normalization verification
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd


def validate_export_file(
    out_protocol: str,
    *,
    protocol_name: str,
    user_name: str,
    software_version: str = "1.7.2021.1019",
) -> tuple[pd.DataFrame, int]:
    """
    Validate structure of exported protocol file.
    
    Args:
        out_protocol: Path to protocol CSV file
        protocol_name: Expected protocol name in header
        user_name: Expected user name in header
        software_version: Expected software version
        
    Returns:
        Tuple of (protocol_dataframe, header_row_index)
        
    Raises:
        AssertionError: If file validation fails
    """
    out_protocol = str(out_protocol)

    assert os.path.exists(out_protocol), f"Missing file: {out_protocol}"
    assert os.path.getsize(out_protocol) > 0, f"Empty file: {out_protocol}"

    p = pd.read_csv(out_protocol, header=None, nrows=30)

    assert str(p.iloc[0, 0]).strip() == protocol_name, "Header mismatch: protocol name"
    assert str(p.iloc[0, 1]).strip() == software_version, "Header mismatch: software version"
    assert str(p.iloc[0, 2]).strip() == user_name, "Header mismatch: user name"
    assert p.shape[1] == 8, f"Expected 8 columns, found {p.shape[1]}"

    header_row_idx = None
    for i in range(len(p)):
        row = p.iloc[i].astype(str).tolist()
        if ("Source Well" in row) and ("Target Well" in row) and ("Volume [uL]" in row) and ("Liquid Name" in row):
            header_row_idx = i
            break

    assert header_row_idx is not None, "Did not find the transfer table header row"

    return p, header_row_idx


def validate_dmso_normalization(
    df: pd.DataFrame,
    *,
    max_dmso_pct: float,
    working_volume_ul: float,
) -> tuple[float, float]:
    """
    Validate DMSO normalization was successful.
    
    Args:
        df: DataFrame with dmso_total_uL column
        max_dmso_pct: Maximum DMSO percentage allowed
        working_volume_ul: Working volume of wells
        
    Returns:
        Tuple of (target_dmso_ul, max_dmso_ul)
        
    Raises:
        ValueError: If normalization failed
    """
    max_dmso_ul = (max_dmso_pct / 100.0) * working_volume_ul

    assert "dmso_total_uL" in df.columns, "Missing df['dmso_total_uL']"

    target_dmso_ul = float(df["dmso_total_uL"].iloc[0])

    if not np.allclose(df["dmso_total_uL"].values, target_dmso_ul, atol=1e-9):
        raise ValueError("DMSO normalization failed: final DMSO is not identical across all wells.")

    if df["dmso_total_uL"].max() > max_dmso_ul + 1e-12:
        raise ValueError(
            f"DMSO exceeds cap: max {df['dmso_total_uL'].max():.6f} uL > cap {max_dmso_ul:.6f} uL"
        )

    return target_dmso_ul, max_dmso_ul
