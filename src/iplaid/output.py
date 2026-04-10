"""
Output Module

Consolidates all protocol building and file writing operations:
- Protocol building from normalized data
- Liquid table construction and source well assignment
- File writing with proper formatting
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional
import pandas as pd


def build_compound_and_topup_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build separate compound and solvent top-up dispense rows.
    
    Separates compound dispenses from solvent top-up dispenses for protocol generation.
    
    Args:
        df: DataFrame with Volume [uL], solvent_topup_uL, solvent_family, and Liquid Name columns
        
    Returns:
        Tuple of (compound_rows, topup_rows, all_rows)
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
    """
    Generate list of all 96-well plate positions.
    
    Returns:
        List of well names (A1-H12)
    """
    rows = list("ABCDEFGH")
    cols = list(range(1, 13))
    return [f"{r}{c}" for c in cols for r in rows]


def build_liquid_table(
    all_rows: pd.DataFrame,
    protocol_name: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build liquid table with source well assignments.
    
    Creates a mapping of unique liquids to source plate wells with proper sorting.
    
    Args:
        all_rows: DataFrame with unique Liquid Name entries
        protocol_name: Protocol name for source plate identification
        
    Returns:
        Tuple of (liquid_table, liquid_table_export)
        
    Raises:
        ValueError: If liquid name format invalid or too many liquids
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
    
    Args:
        all_rows: DataFrame with dispense instructions
        liquid_table: Liquid table with compound metadata
        liquid_table_export: Export version of liquid table
        
    Returns:
        Merged and sorted DataFrame
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


def build_full_protocol(
    all_rows: pd.DataFrame,
    *,
    protocol_name: str,
    user_name: str,
    sourceplate_type: str,
    target_plate_type: str,
    source_specs: dict,
    waste_pos: str = "Waste Tube",
    software_version: str = "1.7.2021.1019",
    date: Optional[str] = None,
    time: Optional[str] = None,
    dispense_to_waste: bool = True,
    dispense_to_waste_cycles: int = 2,
    dispense_to_waste_volume_l: float = 5e-8,
    use_deionisation: bool = True,
    optimization_level: str = "ReorderAndParallel",
    waste_error_handling_level: str = "Ask",
    save_liquids: str = "Ask",
) -> pd.DataFrame:
    """
    Build full iDOT protocol dataframe with headers and parameters.
    
    Args:
        all_rows: DataFrame with dispense instructions
        protocol_name: Protocol identifier
        user_name: User running the protocol
        sourceplate_type: Source plate type
        target_plate_type: Target plate type
        source_specs: Source plate specifications
        waste_pos: Waste position identifier
        software_version: iDOT software version
        date: Protocol date (auto if None)
        time: Protocol time (auto if None)
        dispense_to_waste: Whether to dispense to waste
        dispense_to_waste_cycles: Number of waste cycles
        dispense_to_waste_volume_l: Waste dispense volume in L
        use_deionisation: Use deionization
        optimization_level: iDOT optimization level
        waste_error_handling_level: Waste error handling mode
        save_liquids: Save liquids setting
        
    Returns:
        Complete protocol DataFrame
    """
    if date is None or time is None:
        x = datetime.datetime.now()
        if date is None:
            date = x.strftime("%x")
        if time is None:
            time = x.strftime("%X")

    max_volume_l = float(source_specs.get("max_volume_L_for_protocol", 8.0E-5))

    blocks = []
    sourceplates = all_rows["Source Plate"].unique().tolist()
    targetplates = all_rows["Target Plate"].unique().tolist()

    for sp in sourceplates:
        for tp in targetplates:
            dfx = all_rows.loc[(all_rows["Source Plate"] == sp) & (all_rows["Target Plate"] == tp)].copy()
            if dfx.empty:
                continue

            body = dfx[["Source Well", "Target Well", "Volume [uL]", "Liquid Name"]].copy()
            body["Volume [uL]"] = body["Volume [uL]"].map(lambda v: f"{float(v):05.2f}")

            body = body.reindex(columns=[*body.columns.tolist(), "", "", "", ""], fill_value="")
            body = pd.concat([body.columns.to_frame().T, body], ignore_index=True)
            body.columns = range(len(body.columns))

            subheader = pd.DataFrame([
                [sourceplate_type, sp, "", max_volume_l, target_plate_type, tp, "", waste_pos],
                [
                    f"DispenseToWaste={dispense_to_waste}",
                    f"DispenseToWasteCycles={dispense_to_waste_cycles}",
                    f"DispenseToWasteVolume={dispense_to_waste_volume_l}",
                    f"UseDeionisation={use_deionisation}",
                    f"OptimizationLevel={optimization_level}",
                    f"WasteErrorHandlingLevel={waste_error_handling_level}",
                    f"SaveLiquids={save_liquids}",
                    ""
                ],
            ])

            blocks.append(pd.concat([subheader, body], ignore_index=True))

    file_header = pd.DataFrame([[protocol_name, software_version, user_name, date, time, "", "", ""]])
    fullprotocol = pd.concat([file_header, *blocks], ignore_index=True)
    return fullprotocol


def write_protocol_file(full_protocol: pd.DataFrame, output_path: Path) -> None:
    """
    Write protocol to iDOT CSV file with proper formatting.
    
    Args:
        full_protocol: Protocol DataFrame
        output_path: Output file path
    """
    full_protocol.to_csv(
        output_path,
        header=False,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\r\n",
    )

    output_path = Path(output_path)
    data = output_path.read_bytes()
    if data.endswith(b"\r\n"):
        output_path.write_bytes(data[:-2])


def write_liquids_file(liquid_table_export: pd.DataFrame, output_path: Path) -> None:
    """
    Write liquid mapping file.
    
    Args:
        liquid_table_export: Liquid table DataFrame
        output_path: Output file path
    """
    liquid_table_export.to_csv(output_path, index=False)


def write_outputs(
    full_protocol: pd.DataFrame,
    liquid_table_export: pd.DataFrame,
    *,
    out_protocol: Path,
    out_liquids: Path
) -> None:
    """
    Write both protocol and liquids files.
    
    Args:
        full_protocol: Protocol DataFrame
        liquid_table_export: Liquid table DataFrame
        out_protocol: Output protocol file path
        out_liquids: Output liquids file path
    """
    write_protocol_file(full_protocol, Path(out_protocol))
    write_liquids_file(liquid_table_export, Path(out_liquids))
