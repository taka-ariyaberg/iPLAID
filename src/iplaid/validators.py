"""
Validators Module

Protocol validation checks and assertions:
- Solvent-family normalization verification

iDOT export-file validation moved to iplaid.dispensers.idot; re-exported here
for import-path stability.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Re-export — moved to iplaid.dispensers.idot
from .dispensers.idot import validate_export_file


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


__all__ = [
    "validate_export_file",
    "validate_solvent_normalization",
]
