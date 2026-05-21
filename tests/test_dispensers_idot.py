"""Tests for iplaid.dispensers.idot — volume format, header, validate_export."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from iplaid.dispensers import get_dispenser
from iplaid.dispensers.idot import (
    IDotDispenser,
    format_protocol_volume_ul,
    validate_export_file,
    write_protocol_file,
)


def test_idot_format_protocol_volume_pads_to_5_chars_2_decimals():
    # Matches the on-disk iDOT CSV cell format.
    assert format_protocol_volume_ul(0.04) == "00.04"
    assert format_protocol_volume_ul(1.5) == "01.50"
    assert format_protocol_volume_ul(40.0) == "40.00"


def test_idot_dispenser_spec_and_registry():
    disp = get_dispenser("idot")
    assert isinstance(disp, IDotDispenser)
    assert disp.spec.name == "idot"
    assert disp.spec.min_increment_nL == 0.0
    assert disp.spec.default_sourceplate_type == "S.100 Plate"


def _minimal_idot_protocol_df() -> pd.DataFrame:
    """The minimal shape `write_protocol_file` expects: header row + transfer block.

    Mirrors what build_full_protocol emits but without the full dispensing block —
    enough for validate_export_file's structural checks.
    """
    file_header = pd.DataFrame([["MyProtocol", "1.7.2021.1019", "tester", "01/01/26", "12:00:00", "", "", ""]])
    subheader = pd.DataFrame([
        ["S.100 Plate", "SRC", "", 8.0e-5, "MWP 384", "DST", "", "Waste Tube"],
        ["DispenseToWaste=True", "DispenseToWasteCycles=2", "DispenseToWasteVolume=5e-08",
         "UseDeionisation=True", "OptimizationLevel=ReorderAndParallel",
         "WasteErrorHandlingLevel=Ask", "SaveLiquids=Ask", ""],
    ])
    transfer = pd.DataFrame([
        ["Source Well", "Target Well", "Volume [uL]", "Liquid Name", "", "", "", ""],
        ["A1", "A1", "00.04", "[DMSO][0.0]", "", "", "", ""],
    ])
    return pd.concat([file_header, subheader, transfer], ignore_index=True)


def test_idot_validate_export_accepts_well_formed_file(tmp_path: Path):
    out = tmp_path / "idot.csv"
    write_protocol_file(_minimal_idot_protocol_df(), out)
    df, header_row_idx = validate_export_file(out, protocol_name="MyProtocol", user_name="tester")
    assert df.shape[1] == 8
    assert header_row_idx is not None


def test_idot_validate_export_rejects_mismatched_user(tmp_path: Path):
    out = tmp_path / "idot.csv"
    write_protocol_file(_minimal_idot_protocol_df(), out)
    with pytest.raises(AssertionError, match="user name"):
        validate_export_file(out, protocol_name="MyProtocol", user_name="someone_else")
