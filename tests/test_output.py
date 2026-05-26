"""Tests for iplaid.output.build_liquid_table — source-well assignment + layout import."""
from __future__ import annotations

import pandas as pd
import pytest

from iplaid.dispensers.base import SourceLayoutError
from iplaid.output import build_liquid_table


def _all_rows() -> pd.DataFrame:
    return pd.DataFrame({
        "Target Plate": ["P1"] * 3,
        "Target Well": ["A1", "A2", "A3"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
        "Volume [uL]": [0.005, 0.0125, 0.01],
    })


def test_default_auto_assigns_source_wells():
    _, lt_export = build_liquid_table(_all_rows(), "PROTO")
    assert lt_export["Source Well"].iloc[0] == "A1"


def test_existing_layout_maps_each_liquid_to_supplied_well():
    layout = pd.DataFrame({
        "Source Well": ["A07", "A10", "A12"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
    })
    _, lt_export = build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)
    mapping = dict(zip(lt_export["Liquid Name"], lt_export["Source Well"]))
    assert mapping["[gemcitabine][1.0]"] == "A07"
    assert mapping["[etoposide][10.0]"] == "A10"
    assert mapping["[dmso][0.0]"] == "A12"


def test_existing_layout_rejects_missing_liquid():
    layout = pd.DataFrame({
        "Source Well": ["A07"],
        "Liquid Name": ["[gemcitabine][1.0]"],  # missing etoposide and dmso
    })
    with pytest.raises(SourceLayoutError, match="missing"):
        build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)


def test_existing_layout_rejects_duplicate_source_wells():
    layout = pd.DataFrame({
        "Source Well": ["A07", "A07", "A12"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
    })
    with pytest.raises(SourceLayoutError, match="duplicate"):
        build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)


def test_existing_layout_unused_entries_warn_not_fail(capsys):
    layout = pd.DataFrame({
        "Source Well": ["A07", "A10", "A12", "A15"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]", "[unused][5.0]"],
    })
    build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)
    captured = capsys.readouterr()
    assert "unused" in captured.out.lower() or "1 layout entr" in captured.out.lower()


def test_build_liquid_table_uses_pipette_friendly_algorithm():
    """Auto-assign route uses the new algorithm: same-compound stocks on one row, ascending concentration."""
    all_rows = pd.DataFrame({
        "Target Plate": ["P1"] * 6,
        "Target Well": ["A1"] * 6,
        "Liquid Name": [
            "[Adavosertib][0.1]", "[Adavosertib][1.0]", "[Adavosertib][10.0]",
            "[Berzosertib][0.5]", "[Berzosertib][5.0]", "[Berzosertib][50.0]",
        ],
        "Volume [uL]": [0.5] * 6,
    })
    _, lt_export = build_liquid_table(all_rows, "TEST", existing_layout=None)
    placements = dict(zip(lt_export["Liquid Name"], lt_export["Source Well"]))
    # Both compounds have 3 stocks → descending sort tied → alphabetical: Adavosertib row 1, Berzosertib row 2.
    assert placements["[Adavosertib][0.1]"] == "A1"
    assert placements["[Adavosertib][10.0]"] == "A3"
    assert placements["[Berzosertib][0.5]"] == "B1"
    assert placements["[Berzosertib][50.0]"] == "B3"
