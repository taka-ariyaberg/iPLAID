"""
Output Module

Shared dispense-table builders. iDOT-specific protocol building, file
writing, and validation now live in iplaid.dispensers.idot and are
re-exported here for import-path stability.
"""

from __future__ import annotations

import datetime  # kept for backwards compat — some callers may import datetime via this module
from pathlib import Path
import re
import pandas as pd

# Re-exports — iDOT functions moved to iplaid.dispensers.idot
from .dispensers.idot import (
    format_protocol_volume_ul,
    build_full_protocol,
    write_protocol_file,
    write_liquids_file,
    write_outputs,
)
from .dispensers.base import SourceLayoutError


_SOURCE_WELL_RE = re.compile(r"^([A-Za-z]+)0*(\d+)$")


def _row_label_to_index(label: str) -> int:
    """Convert A/B/.../Z/AA row labels to a 1-based row index."""
    idx = 0
    for char in label.upper():
        if not ("A" <= char <= "Z"):
            raise SourceLayoutError(f"Invalid source well row label: {label!r}")
        idx = idx * 26 + (ord(char) - ord("A") + 1)
    return idx


def _normalize_source_well_key(well: object) -> str:
    """Return canonical uppercase well key, with column zeros removed."""
    raw = str(well).strip()
    match = _SOURCE_WELL_RE.match(raw)
    if not match:
        raise SourceLayoutError(f"Invalid Source Well value: {raw!r}")
    col = int(match.group(2))
    if col < 1:
        raise SourceLayoutError(f"Invalid Source Well value: {raw!r}")
    return f"{match.group(1).upper()}{col}"


def validate_source_layout_geometry(
    existing_layout: pd.DataFrame,
    source_specs: dict,
    sourceplate_type: str,
) -> None:
    """Validate uploaded source wells against the selected source plate geometry."""
    if "Source Well" not in existing_layout.columns:
        return

    rows = int(source_specs.get("rows") or 0)
    cols = int(source_specs.get("cols") or 0)
    if rows <= 0 or cols <= 0:
        return

    bad_wells: list[str] = []
    for well in existing_layout["Source Well"]:
        try:
            well_key = _normalize_source_well_key(well)
            match = _SOURCE_WELL_RE.match(well_key)
            if not match:
                bad_wells.append(str(well))
                continue
            row_idx = _row_label_to_index(match.group(1))
            col_idx = int(match.group(2))
        except SourceLayoutError:
            bad_wells.append(str(well))
            continue

        if row_idx < 1 or row_idx > rows or col_idx < 1 or col_idx > cols:
            bad_wells.append(str(well))

    if bad_wells:
        preview = bad_wells[:10]
        suffix = "" if len(bad_wells) <= 10 else f" and {len(bad_wells) - 10} more"
        raise SourceLayoutError(
            f"source layout has wells outside {sourceplate_type} "
            f"({rows} rows x {cols} columns): {preview}{suffix}"
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
    protocol_name: str,
    *,
    existing_layout: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build liquid table with source well assignments.

    If existing_layout is None: auto-assign wells in deterministic order
    (current behavior; A1..H12 of a 96-well plate).

    If existing_layout is provided: validate completeness and map source
    wells from it. Raises SourceLayoutError if any required Liquid Name
    is missing or any well is duplicated.
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

    if existing_layout is None:
        from .source_plate_layout import assign_source_wells, CompoundSpec, PlateGeometry

        # Group the sorted liquid_table rows into CompoundSpec + solvent inputs.
        # Solvent controls (is_control_liquid=True) become the solvents list;
        # non-control rows are compounds with positive stock_mM.
        compounds_by_name: dict[str, list[float]] = {}
        solvent_names: list[str] = []
        for _, row in liquid_table.iterrows():
            if bool(row["is_control_liquid"]):
                name = str(row["compound"])
                if name not in solvent_names:
                    solvent_names.append(name)
            else:
                compounds_by_name.setdefault(str(row["compound"]), []).append(float(row["stock_mM"]))
        compounds_list = [
            CompoundSpec(name=name, stocks_mM=tuple(stocks))
            for name, stocks in compounds_by_name.items()
        ]

        # Source-plate geometry. iPLAID's supported source plates are all 96-well
        # (iDOT S.60 / S.100 / S.200; Echo 384LDV is not yet supported as a source).
        # Hardcoded to match today's behavior.
        geometry = PlateGeometry(rows=8, cols=12)

        result = assign_source_wells(compounds_list, solvent_names, geometry)

        liquid_table["Source Plate"] = f"SRC_{protocol_name}"
        liquid_table["Source Well"] = liquid_table["Liquid Name"].map(result.placements)

        # Drop excluded compounds from the liquid_table so downstream code sees only placed liquids.
        excluded_compound_names = {ew.compound for ew in result.excluded}
        if excluded_compound_names:
            liquid_table = liquid_table[
                ~liquid_table["compound"].isin(excluded_compound_names)
            ].reset_index(drop=True)

        # Stash warnings on the table's `.attrs` so the pipeline can carry them forward.
        liquid_table.attrs["scatter_warnings"] = list(result.scatter_warnings)
        liquid_table.attrs["excluded_compounds"] = list(result.excluded)
    else:
        # Validate the supplied layout and map wells from it.
        layout = existing_layout.copy()
        if "Source Well" not in layout.columns or "Liquid Name" not in layout.columns:
            raise SourceLayoutError(
                "existing_layout must have columns 'Source Well' and 'Liquid Name'"
            )
        for column in ["Source Well", "Liquid Name"]:
            if layout[column].isna().any():
                raise SourceLayoutError(f"existing_layout has blank {column} values")
            layout[column] = layout[column].astype(str).str.strip()
        if "Source Plate" in layout.columns:
            if layout["Source Plate"].isna().any():
                raise SourceLayoutError("existing_layout has blank Source Plate values")
            layout["Source Plate"] = layout["Source Plate"].astype(str).str.strip()

        if layout["Liquid Name"].duplicated().any():
            dups = layout.loc[layout["Liquid Name"].duplicated(keep=False), "Liquid Name"].tolist()
            raise SourceLayoutError(f"existing_layout has duplicate Liquid Names: {dups}")

        plate_keys = (
            layout["Source Plate"].astype(str).str.strip()
            if "Source Plate" in layout.columns
            else pd.Series([""] * len(layout), index=layout.index)
        )
        well_keys = layout["Source Well"].map(_normalize_source_well_key)
        duplicate_wells = pd.DataFrame({
            "Source Plate": plate_keys,
            "Source Well": well_keys,
        })
        if duplicate_wells.duplicated().any():
            dups = duplicate_wells.loc[duplicate_wells.duplicated(keep=False)]
            pretty = [
                f"{row['Source Plate'] or '<default>'}:{row['Source Well']}"
                for _, row in dups.iterrows()
            ]
            raise SourceLayoutError(f"existing_layout has duplicate Source Wells: {pretty}")

        required = set(liquid_table["Liquid Name"])
        provided = set(layout["Liquid Name"])
        missing = sorted(required - provided)
        if missing:
            raise SourceLayoutError(f"existing_layout missing required liquids: {missing}")

        unused = sorted(provided - required)
        if unused:
            print(
                f"WARN existing_layout has {len(unused)} unused "
                f"entr{'y' if len(unused) == 1 else 'ies'}: {unused}"
            )

        well_map = dict(zip(layout["Liquid Name"], layout["Source Well"]))
        liquid_table["Source Well"] = liquid_table["Liquid Name"].map(well_map)
        if "Source Plate" in layout.columns:
            plate_map = dict(zip(layout["Liquid Name"], layout["Source Plate"]))
            liquid_table["Source Plate"] = liquid_table["Liquid Name"].map(plate_map)
        else:
            liquid_table["Source Plate"] = f"SRC_{protocol_name}"

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
