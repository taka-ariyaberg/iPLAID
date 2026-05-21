"""Tests for iplaid.loaders — layout normalization + derive_meta + legacy adapter."""
from __future__ import annotations

import pandas as pd
import pytest

from iplaid.loaders import (
    derive_meta_from_source_layout,
    normalize_layout_df,
    normalize_meta_df,
    source_layout_to_legacy_shape,
)


# ---- normalize_layout_df ----------------------------------------------------


def test_normalize_layout_canonicalizes_well_addresses():
    df = pd.DataFrame({
        "plateID": ["plate_1", "plate_1"],
        "well": ["B2", "J6"],
        "cmpdname": ["CmpdA", "CmpdB"],
        "CONCuM": [1, 2],
    })
    normalized, _ = normalize_layout_df(df)
    assert normalized["well"].tolist() == ["B02", "J06"]


def test_normalize_layout_rejects_duplicate_wells_after_canonicalization():
    df = pd.DataFrame({
        "plateID": ["plate_1", "plate_1"],
        "well": ["B2", "B02"],  # same well, different padding
        "cmpdname": ["CmpdA", "CmpdB"],
        "CONCuM": [1, 2],
    })
    with pytest.raises(ValueError, match="duplicate target wells"):
        normalize_layout_df(df)


# ---- derive_meta_from_source_layout -----------------------------------------


def _layout_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["cmpdname", "conc_mM", "solvent", "source_plate", "source_well"])


def test_derive_meta_picks_max_conc_per_compound():
    df = _layout_df([
        {"cmpdname": "Dasatinib", "conc_mM": 0.1, "solvent": "DMSO", "source_plate": "P1", "source_well": "A1"},
        {"cmpdname": "Dasatinib", "conc_mM": 1.0, "solvent": "DMSO", "source_plate": "P1", "source_well": "B1"},
        {"cmpdname": "DMSO",      "conc_mM": 0.0, "solvent": "DMSO", "source_plate": "P1", "source_well": "C1"},
    ])
    meta = derive_meta_from_source_layout(df)
    by_name = meta.set_index("cmpdname")["highest_stock_mM"].to_dict()
    assert by_name == {"Dasatinib": 1.0, "DMSO": 0.0}

    normalized = normalize_meta_df(meta)
    assert "is_solvent_control" in normalized.columns
    assert bool(normalized.loc[normalized["cmpdname"] == "DMSO", "is_solvent_control"].iloc[0]) is True


def test_derive_meta_rejects_inconsistent_solvent_per_compound():
    df = _layout_df([
        {"cmpdname": "Dasatinib", "conc_mM": 0.1, "solvent": "DMSO",  "source_plate": "P1", "source_well": "A1"},
        {"cmpdname": "Dasatinib", "conc_mM": 1.0, "solvent": "Water", "source_plate": "P1", "source_well": "B1"},
    ])
    with pytest.raises(ValueError, match="Inconsistent solvent.*Dasatinib"):
        derive_meta_from_source_layout(df)


def test_derive_meta_rejects_blank_cmpdname():
    df = _layout_df([
        {"cmpdname": "", "conc_mM": 1.0, "solvent": "DMSO", "source_plate": "P1", "source_well": "A1"},
    ])
    with pytest.raises(ValueError, match="blank cmpdname"):
        derive_meta_from_source_layout(df)


def test_derive_meta_rejects_blank_solvent():
    df = _layout_df([
        {"cmpdname": "Dasatinib", "conc_mM": 1.0, "solvent": "", "source_plate": "P1", "source_well": "A1"},
    ])
    with pytest.raises(ValueError, match="blank solvent"):
        derive_meta_from_source_layout(df)


def test_derive_meta_rejects_missing_columns():
    df = pd.DataFrame([{"cmpdname": "x", "conc_mM": 1.0}])
    with pytest.raises(ValueError, match="missing required columns"):
        derive_meta_from_source_layout(df)


# ---- source_layout_to_legacy_shape -----------------------------------------


def test_legacy_shape_emits_liquid_name_columns():
    df = pd.DataFrame([
        {"cmpdname": "Dasatinib", "conc_mM": 0.1, "solvent": "DMSO", "source_plate": "P1", "source_well": "A1"},
        {"cmpdname": "DMSO",      "conc_mM": 0.0, "solvent": "DMSO", "source_plate": "P1", "source_well": "B1"},
        {"cmpdname": "Etoposide", "conc_mM": 100.0, "solvent": "DMSO", "source_plate": "P1", "source_well": "C1"},
    ])
    legacy = source_layout_to_legacy_shape(df)
    assert list(legacy.columns) == ["Liquid Name", "Source Plate", "Source Well"]
    assert legacy["Liquid Name"].tolist() == ["[Dasatinib][0.1]", "[DMSO][0.0]", "[Etoposide][100.0]"]
    assert legacy["Source Plate"].tolist() == ["P1", "P1", "P1"]
    assert legacy["Source Well"].tolist() == ["A1", "B1", "C1"]


def test_legacy_shape_rejects_missing_columns():
    df = pd.DataFrame([{"cmpdname": "x", "conc_mM": 1.0}])
    with pytest.raises(ValueError, match="missing required columns"):
        source_layout_to_legacy_shape(df)
