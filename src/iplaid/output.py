"""
Output Module

Shared dispense-table builders. iDOT-specific protocol building, file
writing, and validation now live in iplaid.dispensers.idot and are
re-exported here for import-path stability.
"""

from __future__ import annotations

import datetime  # kept for backwards compat — some callers may import datetime via this module
from pathlib import Path
import pandas as pd

# Re-exports — iDOT functions moved to iplaid.dispensers.idot
from .dispensers.idot import (
    format_protocol_volume_ul,
    build_full_protocol,
    write_protocol_file,
    write_liquids_file,
    write_outputs,
)


def build_compound_and_topup_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build separate compound and solvent top-up dispense rows.
    """
    compound_rows = df[["Target Plate", "Target Well", "Liquid Name", "Volume [uL]"]].copy()
    compound_rows["Volume [uL]"] = compound_rows["Volume [uL]"].astype(float)

    topup_rows = df.loc[
        df["solvent_topup_uL"] > 0,
        ["Target Plate", "Target Well", "solvent_topup_uL", "solvent_family"],
    ].copy()
    topup_rows = topup_rows.rename(columns={"solvent_topup_uL": "Volume [uL]"})
    if len(topup_rows) > 0:
        topup_rows["Liquid Name"] = (
            "[" + topup_rows["solvent_family"].astype(str) + "][0.0]"
        )
    else:
        topup_rows["Liquid Name"] = pd.Series(dtype=str)
    topup_rows = topup_rows.drop(columns=["solvent_family"], errors="ignore")
    topup_rows["Volume [uL]"] = topup_rows["Volume [uL]"].astype(float)

    all_rows = pd.concat([compound_rows, topup_rows], ignore_index=True)
    all_rows = all_rows.loc[all_rows["Volume [uL]"] != 0].copy()

    return compound_rows, topup_rows, all_rows


def wells_96() -> list[str]:
    """Generate list of all 96-well plate positions (A1-H12)."""
    rows = list("ABCDEFGH")
    cols = list(range(1, 13))
    return [f"{r}{c}" for c in cols for r in rows]


def build_liquid_table(
    all_rows: pd.DataFrame,
    protocol_name: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build liquid table with source well assignments.
    """
    liquid_table = all_rows[["Liquid Name"]].drop_duplicates().copy()

    liquid_table[["compound", "stock_str"]] = liquid_table["Liquid Name"].str.extract(r"^\[(.*?)\]\[(.*?)\]$")
    bad = liquid_table.loc[liquid_table[["compound", "stock_str"]].isna().any(axis=1), "Liquid Name"]
    if len(bad) > 0:
        raise ValueError(f"Liquid Name not in expected format [Compound][Stock]:\n{bad.to_list()}")

    liquid_table["stock_mM"] = pd.to_numeric(liquid_table["stock_str"], errors="raise")
    liquid_table["is_control_liquid"] = liquid_table["stock_mM"] == 0
    liquid_table["sort_group"] = (~liquid_table["is_control_liquid"]).astype(int)

    liquid_table = liquid_table.sort_values(
        ["sort_group", "compound", "stock_mM", "Liquid Name"],
        kind="mergesort"
    ).reset_index(drop=True)

    liquid_table["Source Plate"] = f"SRC_{protocol_name}"
    avail = wells_96()
    if len(liquid_table) > len(avail):
        raise ValueError(
            f"Too many unique liquids ({len(liquid_table)}) for one source plate ({len(avail)} wells)."
        )

    liquid_table["Source Well"] = avail[:len(liquid_table)]
    liquid_table_export = liquid_table[["Liquid Name", "Source Plate", "Source Well"]].copy()

    return liquid_table, liquid_table_export


def attach_and_sort_dispense_rows(
    all_rows: pd.DataFrame,
    liquid_table: pd.DataFrame,
    liquid_table_export: pd.DataFrame
) -> pd.DataFrame:
    """
    Attach source well information and sort dispense rows optimally.
    """
    all_rows = all_rows.merge(liquid_table_export, on="Liquid Name", how="left")
    all_rows = all_rows.merge(
        liquid_table[["Liquid Name", "compound", "stock_mM", "is_control_liquid"]],
        on="Liquid Name",
        how="left"
    )

    all_rows = all_rows.sort_values(
        by=["is_control_liquid", "compound", "stock_mM", "Volume [uL]", "Source Well", "Target Plate", "Target Well"],
        ascending=[False, True, True, True, True, True, True],
        kind="mergesort"
    ).reset_index(drop=True)

    return all_rows


__all__ = [
    "build_compound_and_topup_rows",
    "wells_96",
    "build_liquid_table",
    "attach_and_sort_dispense_rows",
    "format_protocol_volume_ul",
    "build_full_protocol",
    "write_protocol_file",
    "write_liquids_file",
    "write_outputs",
]
