"""Schema-level validation for the new-format Source plate layout CSV upload."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.preview import validate_source_layout_upload  # noqa: E402


def _to_bytes(rows: list[str]) -> bytes:
    return ("\n".join(rows) + "\n").encode("utf-8")


HEADER = "cmpdname,conc_mM,solvent,source_plate,source_well"


def test_valid_minimal() -> None:
    csv = _to_bytes([HEADER, "DMSO,0.0,DMSO,P1,A1", "Dasatinib,0.1,DMSO,P1,B1"])
    summary = validate_source_layout_upload("ok.csv", csv)
    assert summary["rowCount"] == 2


def test_rejects_unparseable_file() -> None:
    with pytest.raises(ValueError, match="parse"):
        validate_source_layout_upload("broken.csv", b"\x00\x01not-a-csv")


def test_rejects_missing_required_column() -> None:
    csv = _to_bytes(["cmpdname,conc_mM,solvent,source_well", "DMSO,0,DMSO,A1"])
    with pytest.raises(ValueError, match="source_plate"):
        validate_source_layout_upload("missing.csv", csv)


def test_rejects_empty_csv() -> None:
    csv = _to_bytes([HEADER])
    with pytest.raises(ValueError, match="no data rows"):
        validate_source_layout_upload("empty.csv", csv)


def test_rejects_blank_required_value() -> None:
    csv = _to_bytes([HEADER, "Dasatinib,0.1,DMSO,P1,"])
    with pytest.raises(ValueError, match="Row 1.*source_well"):
        validate_source_layout_upload("blank.csv", csv)


def test_rejects_non_numeric_conc_mM() -> None:
    csv = _to_bytes([HEADER, "Dasatinib,high,DMSO,P1,A1"])
    with pytest.raises(ValueError, match="Row 1.*conc_mM"):
        validate_source_layout_upload("bad.csv", csv)


def test_rejects_negative_conc_mM() -> None:
    csv = _to_bytes([HEADER, "Dasatinib,-0.1,DMSO,P1,A1"])
    with pytest.raises(ValueError, match="Row 1.*conc_mM"):
        validate_source_layout_upload("neg.csv", csv)


def test_rejects_solvent_inconsistency_per_compound() -> None:
    csv = _to_bytes([
        HEADER,
        "Dasatinib,0.1,DMSO,P1,A1",
        "Dasatinib,1.0,Water,P1,B1",
    ])
    with pytest.raises(ValueError, match="Inconsistent solvent.*Dasatinib"):
        validate_source_layout_upload("inconsistent.csv", csv)


def test_rejects_duplicate_well() -> None:
    csv = _to_bytes([
        HEADER,
        "Dasatinib,0.1,DMSO,P1,A1",
        "Etoposide,10.0,DMSO,P1,A1",
    ])
    with pytest.raises(ValueError, match="Duplicate.*A1"):
        validate_source_layout_upload("dup.csv", csv)


def test_rejects_solvent_control_rule_nonzero() -> None:
    # cmpdname == solvent must have conc_mM == 0
    csv = _to_bytes([HEADER, "DMSO,0.5,DMSO,P1,A1"])
    with pytest.raises(ValueError, match="solvent-control.*0"):
        validate_source_layout_upload("ctrl.csv", csv)


def test_rejects_compound_with_zero_conc() -> None:
    # Non-solvent rows must have conc_mM > 0
    csv = _to_bytes([HEADER, "Dasatinib,0,DMSO,P1,A1"])
    with pytest.raises(ValueError, match="conc_mM > 0"):
        validate_source_layout_upload("zero.csv", csv)


def test_well_address_format_validated() -> None:
    csv = _to_bytes([HEADER, "Dasatinib,0.1,DMSO,P1,!!"])
    with pytest.raises(ValueError, match="source_well"):
        validate_source_layout_upload("well.csv", csv)
