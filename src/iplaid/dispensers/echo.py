"""Echo dispenser implementation.

Vendor format: single-section CSV, 10 fixed columns. Source wells zero-padded ("A07"),
destination wells unpadded ("B2"). Volumes in nL, multiples of 2.5, written as %.1f.
Encoding: utf-8 (no BOM), line terminator: LF.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .base import DispenserSpec
from . import _register


_WELL_RE = re.compile(r"^([A-Z])(\d+)$")
_LIQUID_RE = re.compile(r"^\[(.*?)\]\[(.*?)\]$")


def _pad_source_well(well: str) -> str:
    """A1 -> A01, B12 -> B12. Always 2-digit number."""
    m = _WELL_RE.match(well)
    if not m:
        raise ValueError(f"Bad well: {well!r}")
    return f"{m.group(1)}{int(m.group(2)):02d}"


def _unpad_dest_well(well: str) -> str:
    """A01 -> A1, B12 -> B12."""
    m = _WELL_RE.match(well)
    if not m:
        raise ValueError(f"Bad well: {well!r}")
    return f"{m.group(1)}{int(m.group(2))}"


def _liquid_name_to_sample_name(liquid_name: str) -> str:
    """[compound][stock_mM] -> compound[stock_mM] (Echo Sample Name format)."""
    m = _LIQUID_RE.match(liquid_name)
    if not m:
        raise ValueError(f"Liquid Name not in [compound][stock] format: {liquid_name!r}")
    return f"{m.group(1)}[{m.group(2)}]"


_ECHO_COLUMNS = [
    "Sample Name",
    "Source Plate Name",
    "Source well",
    "Destination Plate Barcode",
    "destination well",
    "Transfer Volume",
    "Source Plate Type",
    "Destination Plate Type",
    "Destination Well X Offset",
    "Destination Well Y Offset",
]


class EchoDispenser:
    spec = DispenserSpec(
        name="echo",
        display_name="Echo",
        plate_specs_path="echo_source_plate_specs.json",
        target_plate_specs_path="echo_target_plate_specs.json",
        min_increment_nL=2.5,
        default_sourceplate_type="384LDV",
        default_target_plate_type="Revvity_384_6007660",
    )

    def load_plate_specs(self, project_root: Path) -> dict:
        return json.loads(
            (Path(project_root) / "data" / self.spec.plate_specs_path).read_text()
        )

    def build_protocol(self, all_rows, liquid_table, *, cfg, source_specs):
        out = pd.DataFrame()
        out["Sample Name"] = all_rows["Liquid Name"].map(_liquid_name_to_sample_name)
        out["Source Plate Name"] = all_rows["Source Plate"]
        out["Source well"] = all_rows["Source Well"].map(_pad_source_well)
        out["Destination Plate Barcode"] = all_rows["Target Plate"]
        out["destination well"] = all_rows["Target Well"].map(_unpad_dest_well)
        # Volume comes in as µL; Echo wants nL formatted as %.1f.
        out["Transfer Volume"] = (all_rows["Volume [uL]"].astype(float) * 1000.0).map(
            lambda v: f"{v:.1f}"
        )
        out["Source Plate Type"] = cfg["sourceplate_type"]
        out["Destination Plate Type"] = cfg["target_plate_type"]
        out["Destination Well X Offset"] = source_specs["x_offset"]
        out["Destination Well Y Offset"] = source_specs["y_offset"]
        return out.reset_index(drop=True)

    def write_protocol(self, protocol_df: pd.DataFrame, out_path: Path) -> None:
        protocol_df.to_csv(out_path, index=False, encoding="utf-8", lineterminator="\n")

    def write_liquids(self, liquid_table_export: pd.DataFrame, out_path: Path) -> None:
        liquid_table_export.to_csv(out_path, index=False)

    def validate_export(
        self,
        out_path: Path,
        *,
        protocol_name: str,
        user_name: str,
    ) -> tuple[pd.DataFrame, int]:
        df = pd.read_csv(out_path, encoding="utf-8")
        if list(df.columns) != _ECHO_COLUMNS:
            raise ValueError(f"Echo CSV header mismatch: got {list(df.columns)}")
        if len(df) == 0:
            raise ValueError("Echo CSV has no dispense rows")
        vols = pd.to_numeric(df["Transfer Volume"], errors="raise")
        bad_vol = df[((vols % 2.5).round(6) != 0)]
        if len(bad_vol) > 0:
            raise ValueError(f"{len(bad_vol)} rows have non-2.5 nL volumes")
        if not df["Source well"].astype(str).str.match(r"^[A-Z]\d{2}$").all():
            raise ValueError("Source wells must be 2-digit zero-padded ([A-Z]\\d{2})")
        if not df["destination well"].astype(str).str.match(r"^[A-Z]\d+$").all():
            raise ValueError("Destination wells malformed")
        if df.isna().any().any():
            raise ValueError("Echo CSV contains NaN")
        return df.head(20), 0


_register(EchoDispenser())
