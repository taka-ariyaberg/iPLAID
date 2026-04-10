"""
Normalization Module

Consolidates data transformation operations:
- Target well and volume column assignment
- Solvent-family normalization and top-up calculation
- Per-solvent volume cap enforcement
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.iplaid.solvents import clean_label, get_solvent_cap_pct, label_key


def normalize_solvent_topup(
    df: pd.DataFrame,
    *,
    config: dict,
    working_volume_ul: float,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Normalize carrier solvent within each solvent family.

    For each solvent family, every compound well is topped up to the maximum carrier
    volume already contributed by a compound in that same family. Pure solvent-control
    wells receive the full family target as top-up.
    """
    df = df.copy()

    df["solvent_family"] = df["solvent"].map(clean_label)
    df["solvent_key"] = df["solvent_family"].map(label_key)
    df["solvent_cap_pct"] = df["solvent_family"].map(lambda solvent: float(get_solvent_cap_pct(config, solvent)))
    df["solvent_cap_uL"] = (df["solvent_cap_pct"] / 100.0) * working_volume_ul

    is_solvent_control = df["is_solvent_control"].fillna(False).astype(bool)
    compound_volumes = df["Volume [uL]"].astype(float)

    df["solvent_from_compound_uL"] = np.where(is_solvent_control, 0.0, compound_volumes)
    df["solvent_topup_uL"] = 0.0
    df["solvent_total_uL"] = 0.0
    df["solvent_target_uL"] = 0.0

    solvent_summary: list[dict] = []

    for solvent_key, family_rows in df.groupby("solvent_key", sort=True):
        family_index = family_rows.index
        family_name = clean_label(family_rows["solvent_family"].iloc[0])
        family_cap_pct = float(family_rows["solvent_cap_pct"].iloc[0])
        family_cap_ul = float(family_rows["solvent_cap_uL"].iloc[0])
        family_is_control = is_solvent_control.loc[family_index]

        compound_rows = family_rows.loc[~family_is_control]
        target_ul = (
            float(compound_rows["solvent_from_compound_uL"].max())
            if len(compound_rows) > 0
            else 0.0
        )

        if target_ul > family_cap_ul + 1e-12:
            raise ValueError(
                f'Solvent normalization for "{family_name}" is impossible under the current cap:\n'
                f"  required max solvent = {target_ul:.6f} uL\n"
                f"  allowed cap          = {family_cap_ul:.6f} uL "
                f"({family_cap_pct}% of {working_volume_ul} uL)"
            )

        topup = (target_ul - family_rows["solvent_from_compound_uL"]).clip(lower=0.0)
        topup.loc[family_is_control] = target_ul

        total = family_rows["solvent_from_compound_uL"] + topup
        if not np.allclose(total.values, target_ul, atol=1e-9):
            raise ValueError(
                f'Solvent normalization failed for "{family_name}": final solvent is not identical '
                "across the family."
            )
        if total.max() > family_cap_ul + 1e-12:
            raise ValueError(
                f'Solvent normalization failed for "{family_name}": exceeded the configured solvent cap.'
            )

        df.loc[family_index, "solvent_topup_uL"] = topup
        df.loc[family_index, "solvent_total_uL"] = total
        df.loc[family_index, "solvent_target_uL"] = target_ul

        solvent_summary.append(
            {
                "solvent": family_name,
                "solventKey": solvent_key,
                "configuredCapPct": family_cap_pct,
                "maxSolventUl": family_cap_ul,
                "targetSolventUl": target_ul,
                "compoundWellCount": int((~family_is_control).sum()),
                "controlWellCount": int(family_is_control.sum()),
                "topupDispenseCount": int((topup > 0).sum()),
            }
        )

    return df, solvent_summary


def add_target_and_volume_columns(
    df: pd.DataFrame,
    *,
    remove_leading_zero_fn,
    volume_from_stock_fn,
    working_volume_ul: float,
) -> pd.DataFrame:
    """
    Add target well, target plate, liquid name, and volume columns.
    """
    df = df.copy()

    df["Target Plate"] = df["plateID"].astype(str)
    df["Target Well"] = df["well"].astype(str).map(remove_leading_zero_fn)
    df["Liquid Name"] = "[" + df["cmpdname"].astype(str) + "][" + df["stock_conc_mM"].astype(str) + "]"

    df["Volume [uL]"] = df.apply(
        lambda r: volume_from_stock_fn(r["CONCuM"], r["stock_conc_mM"], working_volume_ul),
        axis=1,
    )

    if df["Volume [uL]"].isna().any():
        raise ValueError(
            "Volume calculation failed for some rows. "
            "Check CONCuM/stock_conc_mM and volume_from_stock()."
        )

    return df


def enforce_solvent_volume_cap(
    df: pd.DataFrame,
    *,
    config: dict,
    working_volume_ul: float,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Check that each compound dispense volume stays below its solvent-family cap.
    """
    df = df.copy()
    df["solvent_family"] = df["solvent"].map(clean_label)
    df["solvent_key"] = df["solvent_family"].map(label_key)
    df["solvent_cap_pct"] = df["solvent_family"].map(lambda solvent: float(get_solvent_cap_pct(config, solvent)))
    df["solvent_cap_uL"] = (df["solvent_cap_pct"] / 100.0) * working_volume_ul

    compound_rows = df.loc[~df["is_solvent_control"].fillna(False).astype(bool)].copy()
    too_high = compound_rows.loc[
        compound_rows["Volume [uL]"].astype(float) > compound_rows["solvent_cap_uL"].astype(float) + 1e-12
    ]

    if len(too_high) > 0:
        first = too_high.iloc[0]
        raise ValueError(
            f'Solvent limit exceeded for "{first["cmpdname"]}" ({first["solvent_family"]}): '
            f'volume {float(first["Volume [uL]"]):.6f} uL > cap {float(first["solvent_cap_uL"]):.6f} uL '
            f'({float(first["solvent_cap_pct"]):.3f}% of {working_volume_ul} uL).'
        )

    solvent_caps = [
        {
            "solvent": clean_label(row.solvent_family),
            "solventKey": row.solvent_key,
            "configuredCapPct": float(row.solvent_cap_pct),
            "maxSolventUl": float(row.solvent_cap_uL),
        }
        for row in (
            df[["solvent_key", "solvent_family", "solvent_cap_pct", "solvent_cap_uL"]]
            .drop_duplicates(subset=["solvent_key"])
            .sort_values(["solvent_family"], kind="mergesort")
            .itertuples(index=False)
        )
    ]

    return df, solvent_caps
