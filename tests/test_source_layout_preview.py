"""Schema-level validation for the Source plate layout CSV upload."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.preview import validate_source_layout_upload  # noqa: E402


def _to_bytes(rows: list[str]) -> bytes:
    return ("\n".join(rows) + "\n").encode("utf-8")


def test_valid_minimal_csv() -> None:
    csv = _to_bytes([
        "Liquid Name,Source Well",
        "[DMSO][0.0],A1",
        "[gemcitabine][1.0],A2",
    ])
    summary = validate_source_layout_upload("ok.csv", csv)
    assert summary["rowCount"] == 2
    assert "Source Plate" not in summary["columns"]


def test_valid_with_source_plate_column() -> None:
    csv = _to_bytes([
        "Liquid Name,Source Well,Source Plate",
        "[DMSO][0.0],A1,SRC1",
        "[etoposide][10.0],B7,SRC1",
    ])
    summary = validate_source_layout_upload("ok.csv", csv)
    assert summary["rowCount"] == 2
    assert "Source Plate" in summary["columns"]


def test_rejects_unparseable_file() -> None:
    with pytest.raises(ValueError, match="parse"):
        validate_source_layout_upload("broken.csv", b"\x00\x01not-a-csv")


def test_rejects_missing_required_column() -> None:
    csv = _to_bytes(["Liquid Name", "[DMSO][0.0]"])
    with pytest.raises(ValueError, match="Source Well"):
        validate_source_layout_upload("missing.csv", csv)


def test_rejects_empty_csv() -> None:
    csv = _to_bytes(["Liquid Name,Source Well"])
    with pytest.raises(ValueError, match="no data rows"):
        validate_source_layout_upload("empty.csv", csv)


def test_rejects_blank_required_value() -> None:
    csv = _to_bytes([
        "Liquid Name,Source Well",
        "[DMSO][0.0],",
    ])
    with pytest.raises(ValueError, match="blank"):
        validate_source_layout_upload("blank.csv", csv)


def test_rejects_bad_liquid_name_format() -> None:
    csv = _to_bytes([
        "Liquid Name,Source Well",
        "DMSO,A1",
    ])
    with pytest.raises(ValueError, match=r"\[Compound\]\[Stock\]"):
        validate_source_layout_upload("bad.csv", csv)


def test_rejects_non_numeric_stock() -> None:
    csv = _to_bytes([
        "Liquid Name,Source Well",
        "[DMSO][high],A1",
    ])
    with pytest.raises(ValueError, match="non-numeric"):
        validate_source_layout_upload("bad.csv", csv)


def test_rejects_invalid_well_format() -> None:
    csv = _to_bytes([
        "Liquid Name,Source Well",
        "[DMSO][0.0],123",
    ])
    with pytest.raises(ValueError, match="Source Well"):
        validate_source_layout_upload("bad.csv", csv)


def test_rejects_duplicate_liquid_name() -> None:
    csv = _to_bytes([
        "Liquid Name,Source Well",
        "[DMSO][0.0],A1",
        "[DMSO][0.0],A2",
    ])
    with pytest.raises(ValueError, match="duplicate Liquid Name"):
        validate_source_layout_upload("dup.csv", csv)


def test_rejects_duplicate_source_well() -> None:
    csv = _to_bytes([
        "Liquid Name,Source Well,Source Plate",
        "[DMSO][0.0],A1,SRC1",
        "[etoposide][10.0],A1,SRC1",
    ])
    with pytest.raises(ValueError, match="duplicate Source Well"):
        validate_source_layout_upload("dup.csv", csv)


def test_random_csv_rejected() -> None:
    """A random unrelated CSV should not validate as a source plate layout."""
    csv = _to_bytes([
        "name,age,city",
        "alice,30,Stockholm",
        "bob,25,Uppsala",
    ])
    with pytest.raises(ValueError, match="missing required column"):
        validate_source_layout_upload("random.csv", csv)
