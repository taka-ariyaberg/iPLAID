"""Tests for user-supplied source-plate layout import."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.dispensers.base import SourceLayoutError  # noqa: E402
from iplaid.output import build_liquid_table  # noqa: E402


def _all_rows() -> pd.DataFrame:
    return pd.DataFrame({
        "Target Plate": ["P1"] * 3,
        "Target Well": ["A1", "A2", "A3"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
        "Volume [uL]": [0.005, 0.0125, 0.01],
    })


def test_build_liquid_table_default_auto_assigns() -> None:
    lt, lt_export = build_liquid_table(_all_rows(), "PROTO")
    assert lt_export["Source Well"].iloc[0] == "A1"


def test_build_liquid_table_uses_existing_layout() -> None:
    layout = pd.DataFrame({
        "Source Well": ["A07", "A10", "A12"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
    })
    lt, lt_export = build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)
    mapping = dict(zip(lt_export["Liquid Name"], lt_export["Source Well"]))
    assert mapping["[gemcitabine][1.0]"] == "A07"
    assert mapping["[etoposide][10.0]"] == "A10"
    assert mapping["[dmso][0.0]"] == "A12"


def test_build_liquid_table_rejects_missing_liquid() -> None:
    layout = pd.DataFrame({
        "Source Well": ["A07"],
        "Liquid Name": ["[gemcitabine][1.0]"],  # missing etoposide and dmso
    })
    with pytest.raises(SourceLayoutError, match="missing"):
        build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)


def test_build_liquid_table_rejects_duplicate_wells() -> None:
    layout = pd.DataFrame({
        "Source Well": ["A07", "A07", "A12"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
    })
    with pytest.raises(SourceLayoutError, match="duplicate"):
        build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)


def test_build_liquid_table_layout_unused_entries_warn_not_fail(capsys) -> None:
    layout = pd.DataFrame({
        "Source Well": ["A07", "A10", "A12", "A15"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]", "[unused][5.0]"],
    })
    lt, _ = build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)
    captured = capsys.readouterr()
    assert "unused" in captured.out.lower() or "1 layout entr" in captured.out.lower()
