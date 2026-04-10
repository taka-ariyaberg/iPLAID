"""
Validators Module

Protocol validation checks and assertions:
- Export file structure validation
- Solvent-family normalization verification
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
    """Validate structure of exported protocol file."""
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


def validate_solvent_normalization(df: pd.DataFrame) -> list[dict]:
    """
    Validate solvent-family normalization and return a solvent summary.
    """
    required_columns = {
        "solvent_key",
        "solvent_family",
        "solvent_total_uL",
        "solvent_target_uL",
        "solvent_cap_pct",
        "solvent_cap_uL",
        "solvent_topup_uL",
        "is_solvent_control",
    }
    missing = sorted(required_columns - set(df.columns))
    if missing:
        raise ValueError(f"Missing solvent normalization columns: {missing}")

    summaries: list[dict] = []
    for solvent_key, family_rows in df.groupby("solvent_key", sort=True):
        family_name = str(family_rows["solvent_family"].iloc[0]).strip()
        target_ul = float(family_rows["solvent_target_uL"].iloc[0])
        max_ul = float(family_rows["solvent_cap_uL"].iloc[0])
        cap_pct = float(family_rows["solvent_cap_pct"].iloc[0])
        totals = family_rows["solvent_total_uL"].astype(float)

        if not np.allclose(totals.values, target_ul, atol=1e-9):
            raise ValueError(
                f'Solvent normalization failed for "{family_name}": final solvent is not identical across the family.'
            )

        if totals.max() > max_ul + 1e-12:
            raise ValueError(
                f'Solvent normalization failed for "{family_name}": exceeded the configured solvent cap.'
            )

        control_mask = family_rows["is_solvent_control"].fillna(False).astype(bool)
        summaries.append(
            {
                "solvent": family_name,
                "solventKey": solvent_key,
                "configuredCapPct": cap_pct,
                "maxSolventUl": max_ul,
                "targetSolventUl": target_ul,
                "compoundWellCount": int((~control_mask).sum()),
                "controlWellCount": int(control_mask.sum()),
                "topupDispenseCount": int((family_rows["solvent_topup_uL"].astype(float) > 0).sum()),
            }
        )

    return summaries
