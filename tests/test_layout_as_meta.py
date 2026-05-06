"""Unit tests for layout-derived meta (Task 1)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.iplaid.loaders import (  # noqa: E402
    derive_meta_from_source_layout,
    normalize_meta_df,
)


def _layout_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["cmpdname", "conc_mM", "solvent", "source_plate", "source_well"])


def test_derive_meta_picks_max_conc_per_compound() -> None:
    df = _layout_df([
        {"cmpdname": "Dasatinib", "conc_mM": 0.1, "solvent": "DMSO", "source_plate": "P1", "source_well": "A1"},
        {"cmpdname": "Dasatinib", "conc_mM": 1.0, "solvent": "DMSO", "source_plate": "P1", "source_well": "B1"},
        {"cmpdname": "DMSO",      "conc_mM": 0.0, "solvent": "DMSO", "source_plate": "P1", "source_well": "C1"},
    ])
    meta = derive_meta_from_source_layout(df)
    by_name = meta.set_index("cmpdname")["highest_stock_mM"].to_dict()
    assert by_name == {"Dasatinib": 1.0, "DMSO": 0.0}
    # Result must be acceptable to the existing meta normalizer
    normalized = normalize_meta_df(meta)
    assert "is_solvent_control" in normalized.columns
    assert bool(normalized.loc[normalized["cmpdname"] == "DMSO", "is_solvent_control"].iloc[0]) is True


def test_derive_meta_rejects_inconsistent_solvent_per_compound() -> None:
    df = _layout_df([
        {"cmpdname": "Dasatinib", "conc_mM": 0.1, "solvent": "DMSO",  "source_plate": "P1", "source_well": "A1"},
        {"cmpdname": "Dasatinib", "conc_mM": 1.0, "solvent": "Water", "source_plate": "P1", "source_well": "B1"},
    ])
    with pytest.raises(ValueError, match="Inconsistent solvent.*Dasatinib"):
        derive_meta_from_source_layout(df)


def test_derive_meta_rejects_blank_cmpdname() -> None:
    df = _layout_df([
        {"cmpdname": "", "conc_mM": 1.0, "solvent": "DMSO", "source_plate": "P1", "source_well": "A1"},
    ])
    with pytest.raises(ValueError, match="blank cmpdname"):
        derive_meta_from_source_layout(df)


def test_derive_meta_rejects_blank_solvent() -> None:
    df = _layout_df([
        {"cmpdname": "Dasatinib", "conc_mM": 1.0, "solvent": "", "source_plate": "P1", "source_well": "A1"},
    ])
    with pytest.raises(ValueError, match="blank solvent"):
        derive_meta_from_source_layout(df)


def test_derive_meta_requires_columns() -> None:
    df = pd.DataFrame([{"cmpdname": "x", "conc_mM": 1.0}])
    with pytest.raises(ValueError, match="missing required columns"):
        derive_meta_from_source_layout(df)
