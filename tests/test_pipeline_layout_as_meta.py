"""Layout-only run produces the same artifacts as meta + legacy-format-layout."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.iplaid.pipeline import run_pipeline_with_inputs  # noqa: E402


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _write_min_layout(path: Path) -> None:
    pd.DataFrame([
        {"plateID": "plate_1", "well": "A1",  "cmpdname": "Dasatinib", "CONCuM": 1.0},
        {"plateID": "plate_1", "well": "A2",  "cmpdname": "DMSO",      "CONCuM": 0.0},
    ]).to_csv(path, index=False)


def _write_meta(path: Path) -> None:
    pd.DataFrame([
        {"cmpdname": "Dasatinib", "highest_stock_mM": 1.0,  "solvent": "DMSO"},
        {"cmpdname": "DMSO",      "highest_stock_mM": 0.0,  "solvent": "DMSO"},
    ]).to_csv(path, index=False)


def _write_old_format_source_layout(path: Path) -> None:
    pd.DataFrame([
        {"Liquid Name": "[Dasatinib][1.0]", "Source Plate": "P1", "Source Well": "A1"},
        {"Liquid Name": "[DMSO][0.0]",      "Source Plate": "P1", "Source Well": "B1"},
    ]).to_csv(path, index=False)


def _write_new_format_source_layout(path: Path) -> None:
    pd.DataFrame([
        {"cmpdname": "Dasatinib", "conc_mM": 1.0, "solvent": "DMSO", "source_plate": "P1", "source_well": "A1"},
        {"cmpdname": "DMSO",      "conc_mM": 0.0, "solvent": "DMSO", "source_plate": "P1", "source_well": "B1"},
    ]).to_csv(path, index=False)


def _baseline_config() -> dict:
    return {
        "user_name": "tester",
        "protocol_name": "regression",
        "dispenser": "idot",
        "sourceplate_type": "S.100 Plate",
        "target_plate_type": "MWP 384",
        "dilution_solvent": "DMSO",
        "working_volume_ul": 50.0,
        "max_dmso_pct": 0.5,
        "source_prep_overage_pct": 0.1,
        "min_pipette_volume_uL": 1.0,
        "source_well_fill_pct": 0.8,
        "standard_prep_volume_uL": 50,
        "layout_file": "layout.csv",
        "meta_file": "meta.csv",
        "output_timestamp_format": "FROZEN-TIMESTAMP",
    }


def test_layout_only_matches_meta_plus_legacy_layout(tmp_path: Path) -> None:
    legacy_dir = tmp_path / "legacy"; legacy_dir.mkdir()
    new_dir    = tmp_path / "new";    new_dir.mkdir()
    out_legacy = tmp_path / "out_legacy"; out_legacy.mkdir()
    out_new    = tmp_path / "out_new";    out_new.mkdir()

    layout_csv = legacy_dir / "layout.csv";       _write_min_layout(layout_csv)
    meta_csv   = legacy_dir / "meta.csv";         _write_meta(meta_csv)
    old_src    = legacy_dir / "old_src.csv";      _write_old_format_source_layout(old_src)
    new_src    = new_dir    / "new_src.csv";      _write_new_format_source_layout(new_src)
    layout2    = new_dir    / "layout.csv";       _write_min_layout(layout2)

    cfg = _baseline_config()

    a = run_pipeline_with_inputs(
        config=cfg, layout_path=layout_csv, meta_path=meta_csv,
        output_dir=out_legacy, source_layout_path=old_src, include_source_prep=False,
    )
    b = run_pipeline_with_inputs(
        config=cfg, layout_path=layout2, meta_path=None,
        output_dir=out_new, source_layout_path=new_src, include_source_prep=False,
    )

    # Compare every produced artifact byte-for-byte.
    for key in ("out_idot", "out_liquids", "out_imeta"):
        assert _read_text(a["paths"][key]) == _read_text(b["paths"][key]), key


def test_pipeline_rejects_both_files(tmp_path: Path) -> None:
    layout_csv = tmp_path / "layout.csv"; _write_min_layout(layout_csv)
    meta_csv   = tmp_path / "meta.csv";   _write_meta(meta_csv)
    new_src    = tmp_path / "new_src.csv"; _write_new_format_source_layout(new_src)
    out_dir    = tmp_path / "out"; out_dir.mkdir()

    with pytest.raises(ValueError, match="both meta_path and source_layout_path"):
        run_pipeline_with_inputs(
            config=_baseline_config(),
            layout_path=layout_csv,
            meta_path=meta_csv,
            output_dir=out_dir,
            source_layout_path=new_src,
        )


def test_pipeline_rejects_neither(tmp_path: Path) -> None:
    layout_csv = tmp_path / "layout.csv"; _write_min_layout(layout_csv)
    out_dir    = tmp_path / "out"; out_dir.mkdir()

    with pytest.raises(ValueError, match="meta_path is required"):
        run_pipeline_with_inputs(
            config=_baseline_config(),
            layout_path=layout_csv,
            meta_path=None,
            output_dir=out_dir,
            source_layout_path=None,
        )


def _write_multiconc_layout(path: Path) -> None:
    pd.DataFrame([
        {"plateID": "plate_1", "well": "A1",  "cmpdname": "Dasatinib", "CONCuM": 1.0},
        {"plateID": "plate_1", "well": "A2",  "cmpdname": "Dasatinib", "CONCuM": 10.0},
        {"plateID": "plate_1", "well": "A3",  "cmpdname": "DMSO",      "CONCuM": 0.0},
    ]).to_csv(path, index=False)


def _write_multiconc_meta(path: Path) -> None:
    # Dasatinib's highest stock is 10.0 — the max of its source-plate wells
    pd.DataFrame([
        {"cmpdname": "Dasatinib", "highest_stock_mM": 10.0,  "solvent": "DMSO"},
        {"cmpdname": "DMSO",      "highest_stock_mM": 0.0,   "solvent": "DMSO"},
    ]).to_csv(path, index=False)


def _write_multiconc_old_source_layout(path: Path) -> None:
    pd.DataFrame([
        {"Liquid Name": "[Dasatinib][1.0]",  "Source Plate": "P1", "Source Well": "A1"},
        {"Liquid Name": "[Dasatinib][10.0]", "Source Plate": "P1", "Source Well": "B1"},
        {"Liquid Name": "[DMSO][0.0]",       "Source Plate": "P1", "Source Well": "C1"},
    ]).to_csv(path, index=False)


def _write_multiconc_new_source_layout(path: Path) -> None:
    pd.DataFrame([
        {"cmpdname": "Dasatinib", "conc_mM": 1.0,  "solvent": "DMSO", "source_plate": "P1", "source_well": "A1"},
        {"cmpdname": "Dasatinib", "conc_mM": 10.0, "solvent": "DMSO", "source_plate": "P1", "source_well": "B1"},
        {"cmpdname": "DMSO",      "conc_mM": 0.0,  "solvent": "DMSO", "source_plate": "P1", "source_well": "C1"},
    ]).to_csv(path, index=False)


def test_layout_only_matches_meta_plus_legacy_multiconc(tmp_path: Path) -> None:
    """AC2 with multi-conc per compound — exercises max(conc_mM) derivation."""
    legacy_dir = tmp_path / "legacy"; legacy_dir.mkdir()
    new_dir    = tmp_path / "new";    new_dir.mkdir()
    out_legacy = tmp_path / "out_legacy"; out_legacy.mkdir()
    out_new    = tmp_path / "out_new";    out_new.mkdir()

    layout_csv = legacy_dir / "layout.csv";  _write_multiconc_layout(layout_csv)
    meta_csv   = legacy_dir / "meta.csv";    _write_multiconc_meta(meta_csv)
    old_src    = legacy_dir / "old_src.csv"; _write_multiconc_old_source_layout(old_src)
    layout2    = new_dir    / "layout.csv";  _write_multiconc_layout(layout2)
    new_src    = new_dir    / "new_src.csv"; _write_multiconc_new_source_layout(new_src)

    cfg = _baseline_config()

    a = run_pipeline_with_inputs(
        config=cfg, layout_path=layout_csv, meta_path=meta_csv,
        output_dir=out_legacy, source_layout_path=old_src, include_source_prep=False,
    )
    b = run_pipeline_with_inputs(
        config=cfg, layout_path=layout2, meta_path=None,
        output_dir=out_new, source_layout_path=new_src, include_source_prep=False,
    )

    for key in ("out_idot", "out_liquids", "out_imeta"):
        assert _read_text(a["paths"][key]) == _read_text(b["paths"][key]), key
