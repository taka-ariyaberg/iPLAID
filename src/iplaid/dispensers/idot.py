"""iDOT dispenser implementation.

Functions previously in src/iplaid/output.py and src/iplaid/validators.py live here.
output.py and validators.py re-export them for import-path stability.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .base import DispenserSpec
from . import _register


# --------------------------- moved from output.py ---------------------------

def format_protocol_volume_ul(volume_ul: float) -> str:
    """Format a dispense volume exactly as written to the iDOT protocol CSV."""
    return f"{float(volume_ul):05.2f}"


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
            body["Volume [uL]"] = body["Volume [uL]"].map(format_protocol_volume_ul)

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
    """Write protocol to iDOT CSV file with proper formatting."""
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
    """Write liquid mapping file."""
    liquid_table_export.to_csv(output_path, index=False)


def write_outputs(
    full_protocol: pd.DataFrame,
    liquid_table_export: pd.DataFrame,
    *,
    out_protocol: Path,
    out_liquids: Path,
) -> None:
    """Write both protocol and liquids files."""
    write_protocol_file(full_protocol, Path(out_protocol))
    write_liquids_file(liquid_table_export, Path(out_liquids))


# ------------------------- moved from validators.py -------------------------

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


# --------------------------- IDotDispenser class ----------------------------

class IDotDispenser:
    spec = DispenserSpec(
        name="idot",
        display_name="iDOT",
        plate_specs_path="source_plate_specs.json",
        min_increment_nL=0.0,
        default_sourceplate_type="S.100 Plate",
        default_target_plate_type="MWP 384",
    )

    def load_plate_specs(self, project_root: Path) -> dict:
        import json
        return json.loads((Path(project_root) / "data" / self.spec.plate_specs_path).read_text())

    def build_protocol(self, all_rows, liquid_table, *, cfg, source_specs):
        return build_full_protocol(
            all_rows,
            protocol_name=str(cfg["protocol_name"]),
            user_name=str(cfg["user_name"]),
            sourceplate_type=str(cfg["sourceplate_type"]),
            target_plate_type=str(cfg["target_plate_type"]),
            source_specs=source_specs,
        )

    def write_protocol(self, protocol_df, out_path):
        write_protocol_file(protocol_df, Path(out_path))

    def write_liquids(self, liquid_table_export, out_path):
        write_liquids_file(liquid_table_export, Path(out_path))

    def validate_export(self, out_path, *, protocol_name, user_name):
        return validate_export_file(Path(out_path), protocol_name=protocol_name, user_name=user_name)


_register(IDotDispenser())
