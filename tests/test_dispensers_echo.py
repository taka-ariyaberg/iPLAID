"""Tests for iplaid.dispensers.echo — helpers, build_protocol, write_protocol, validate_export."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from iplaid.dispensers import get_dispenser
from iplaid.dispensers.echo import (
    EchoDispenser,
    _liquid_name_to_sample_name,
    _pad_source_well,
    _unpad_dest_well,
)


def test_pad_source_well_pads_single_digit() -> None:
    assert _pad_source_well("A1") == "A01"
    assert _pad_source_well("B7") == "B07"


def test_pad_source_well_leaves_double_digit() -> None:
    assert _pad_source_well("A12") == "A12"
    assert _pad_source_well("H24") == "H24"


def test_pad_source_well_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        _pad_source_well("BAD")


def test_unpad_dest_well_strips_leading_zero() -> None:
    assert _unpad_dest_well("A01") == "A1"
    assert _unpad_dest_well("B07") == "B7"


def test_unpad_dest_well_leaves_already_unpadded() -> None:
    assert _unpad_dest_well("A1") == "A1"
    assert _unpad_dest_well("H24") == "H24"


def test_liquid_name_to_sample_name() -> None:
    assert _liquid_name_to_sample_name("[gemcitabine][1.0]") == "gemcitabine[1.0]"
    assert _liquid_name_to_sample_name("[dmso][0.0]") == "dmso[0.0]"


# ---- EchoDispenser spec + registry + load_plate_specs ----------------------


def test_echo_dispenser_spec() -> None:
    disp = EchoDispenser()
    assert disp.spec.name == "echo"
    assert disp.spec.min_increment_nL == 2.5
    assert disp.spec.default_sourceplate_type == "384LDV"


def test_echo_registered() -> None:
    disp = get_dispenser("echo")
    assert isinstance(disp, EchoDispenser)


def test_echo_load_plate_specs(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "echo_source_plate_specs.json").write_text(
        '{"384LDV": {"x_offset": 1050, "y_offset": -1050, "dispense_min_nL": 2.5}}'
    )
    disp = EchoDispenser()
    specs = disp.load_plate_specs(tmp_path)
    assert specs["384LDV"]["x_offset"] == 1050


# ---- EchoDispenser.build_protocol ------------------------------------------


def test_echo_build_protocol_columns_and_format() -> None:
    all_rows = pd.DataFrame({
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
        "Source Plate": ["source_dmso", "source_dmso", "source_dmso"],
        "Source Well": ["A1", "A2", "A12"],
        "Target Plate": ["P1", "P1", "P1"],
        "Target Well": ["B02", "B03", "B17"],
        "Volume [uL]": [0.005, 0.0125, 0.05],
    })
    liquid_table = pd.DataFrame({
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
        "Source Plate": ["source_dmso"] * 3,
        "Source Well": ["A1", "A2", "A12"],
    })
    cfg = {
        "sourceplate_type": "384LDV",
        "target_plate_type": "Corning_384_3784",
    }
    source_specs = {"x_offset": 1050, "y_offset": -1050}

    out = EchoDispenser().build_protocol(all_rows, liquid_table, cfg=cfg, source_specs=source_specs)

    assert list(out.columns) == [
        "Sample Name", "Source Plate Name", "Source well",
        "Destination Plate Barcode", "destination well", "Transfer Volume",
        "Source Plate Type", "Destination Plate Type",
        "Destination Well X Offset", "Destination Well Y Offset",
    ]
    assert list(out["Sample Name"]) == ["gemcitabine[1.0]", "etoposide[10.0]", "dmso[0.0]"]
    assert list(out["Source well"]) == ["A01", "A02", "A12"]
    assert list(out["destination well"]) == ["B2", "B3", "B17"]
    assert list(out["Transfer Volume"]) == ["5.0", "12.5", "50.0"]
    assert (out["Source Plate Type"] == "384LDV").all()
    assert (out["Destination Well X Offset"] == 1050).all()


# ---- EchoDispenser.write_protocol: UTF-8, no BOM, LF -----------------------


def test_echo_write_protocol_uses_utf8_no_bom_and_lf(tmp_path: Path) -> None:
    df = pd.DataFrame({
        "Sample Name": ["gemcitabine[1.0]"],
        "Source Plate Name": ["source_dmso"],
        "Source well": ["A01"],
        "Destination Plate Barcode": ["P1"],
        "destination well": ["B2"],
        "Transfer Volume": ["5.0"],
        "Source Plate Type": ["384LDV"],
        "Destination Plate Type": ["Corning_384_3784"],
        "Destination Well X Offset": [1050],
        "Destination Well Y Offset": [-1050],
    })
    out = tmp_path / "echo.csv"
    EchoDispenser().write_protocol(df, out)
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "Echo CSV must not have UTF-8 BOM"
    assert b"\r\n" not in raw, "Echo CSV must use LF, not CRLF"
    assert raw.count(b"\n") == 2  # header + 1 row


# ---- EchoDispenser.write_liquids round-trip + validate_export -------------


def test_echo_write_liquids_round_trip(tmp_path: Path) -> None:
    lt = pd.DataFrame({
        "Liquid Name": ["[gemcitabine][1.0]"],
        "Source Plate": ["SRC_T"],
        "Source Well": ["A1"],
    })
    out = tmp_path / "liquids.csv"
    EchoDispenser().write_liquids(lt, out)
    back = pd.read_csv(out)
    assert list(back["Liquid Name"]) == ["[gemcitabine][1.0]"]


def _good_echo_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Sample Name": ["gemcitabine[1.0]"],
        "Source Plate Name": ["source_dmso"],
        "Source well": ["A01"],
        "Destination Plate Barcode": ["P1"],
        "destination well": ["B2"],
        "Transfer Volume": ["5.0"],
        "Source Plate Type": ["384LDV"],
        "Destination Plate Type": ["Corning_384_3784"],
        "Destination Well X Offset": [1050],
        "Destination Well Y Offset": [-1050],
    })


def test_echo_validate_export_accepts_good_file(tmp_path: Path) -> None:
    out = tmp_path / "echo.csv"
    EchoDispenser().write_protocol(_good_echo_df(), out)
    preview, idx = EchoDispenser().validate_export(out, protocol_name="P1", user_name="U")
    assert idx == 0
    assert len(preview) == 1


def test_echo_validate_export_rejects_non_increment(tmp_path: Path) -> None:
    df = _good_echo_df()
    df["Transfer Volume"] = ["12.7"]  # NOT a multiple of 2.5
    out = tmp_path / "bad.csv"
    EchoDispenser().write_protocol(df, out)
    with pytest.raises(ValueError, match="non-2.5"):
        EchoDispenser().validate_export(out, protocol_name="P", user_name="U")


def test_echo_validate_export_rejects_unpadded_source(tmp_path: Path) -> None:
    df = _good_echo_df()
    df["Source well"] = ["A1"]  # NOT zero-padded
    out = tmp_path / "bad2.csv"
    EchoDispenser().write_protocol(df, out)
    with pytest.raises(ValueError, match="zero-padded"):
        EchoDispenser().validate_export(out, protocol_name="P", user_name="U")
