"""Pipeline-level checks on the source-plate-prep / source-plate-summary output file.

Covers two distinct outputs produced by the pipeline depending on inputs:
- iDOT auto-derived layout → preparation recipe (STEP 1, STEP 2, ...)
- Uploaded source layout (iDOT or Echo) → usage summary (no recipe)
- Echo without uploaded layout → v2 placeholder (no recipe yet)
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from iplaid.dispensers.base import SourceLayoutError
from iplaid.pipeline import run_pipeline_with_inputs


GOLDEN_DIR = Path(__file__).parent / "golden"


def _run_with_supplied_layout(
    fixture_name: str, supplied_layout_relpath: str, tmp_path: Path,
) -> dict:
    src = GOLDEN_DIR / fixture_name
    work = tmp_path / f"prep_{fixture_name}"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"; out_dir.mkdir()
    return run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=True,
        source_layout_path=src / supplied_layout_relpath,
    )


def test_idot_uploaded_layout_produces_usage_summary(tmp_path: Path) -> None:
    r = _run_with_supplied_layout("idot_basic", "expected_liquids.csv", tmp_path)
    text = str(r["source_prep_instructions"])
    assert "SOURCE PLATE LAYOUT SUMMARY" in text
    assert "source of truth" in text
    assert "This file is a usage summary, not a preparation recipe." in text
    assert "STEP " not in text
    assert "[Dasatinib][0.1]" in text
    assert Path(r["paths"]["out_source_prep"]).read_text() == text


def test_echo_uploaded_layout_produces_usage_summary(tmp_path: Path) -> None:
    r = _run_with_supplied_layout("echo_with_layout", "source_layout.csv", tmp_path)
    text = str(r["source_prep_instructions"])
    assert "SOURCE PLATE LAYOUT SUMMARY" in text
    assert "Dispenser: echo" in text
    assert "v2" not in text
    assert "[Dasatinib][0.1]" in text


def test_echo_without_uploaded_layout_emits_v2_placeholder(tmp_path: Path) -> None:
    """Echo + include_source_prep=True without supplied layout writes a v2 placeholder."""
    src = GOLDEN_DIR / "echo_basic"
    work = tmp_path / "echo_placeholder"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"; out_dir.mkdir()
    r = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=True,
    )
    text = str(r["source_prep_instructions"])
    assert "v2" in text
    assert Path(r["paths"]["out_source_prep"]).exists()


def test_uploaded_layout_rejects_wells_outside_source_plate(tmp_path: Path) -> None:
    """Wells in the uploaded layout must exist on the configured source-plate type."""
    src = GOLDEN_DIR / "idot_basic"
    work = tmp_path / "bad_well"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    bad_layout = work / "bad_source_layout.csv"
    bad_layout.write_text(
        "Liquid Name,Source Plate,Source Well\n"
        "[DMSO][0.0],SRC_BAD,A13\n",
        encoding="utf-8",
    )

    with pytest.raises(SourceLayoutError, match="outside S.100 Plate"):
        run_pipeline_with_inputs(
            config=cfg,
            layout_path=work / "layout.csv",
            meta_path=work / "meta.csv",
            output_dir=work / "out",
            include_source_prep=True,
            source_layout_path=bad_layout,
        )
