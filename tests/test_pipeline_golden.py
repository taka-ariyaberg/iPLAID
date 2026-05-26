"""End-to-end byte-equal regression: run_pipeline_with_inputs against captured goldens.

These tests lock the iDOT and Echo CSV outputs against reference files in tests/scenarios/.
A diff here means the pipeline output bytes changed — intentional or not.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from iplaid.pipeline import run_pipeline_with_inputs


SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def _run_golden(fixture_name: str, tmp_path: Path) -> dict:
    """Copy a golden fixture into tmp_path and run the pipeline against it."""
    src = SCENARIOS_DIR / fixture_name
    work = tmp_path / fixture_name
    work.mkdir(parents=True)
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"
    out_dir.mkdir()
    return run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=False,
    )


def _read_bytes(p) -> bytes:
    return Path(p).read_bytes()


# ---- iDOT goldens -----------------------------------------------------------


def test_idot_basic_protocol_byte_equal(tmp_path: Path, freeze_now) -> None:
    result = _run_golden("idot_basic", tmp_path)
    expected = _read_bytes(SCENARIOS_DIR / "idot_basic" / "expected_protocol.csv")
    assert _read_bytes(result["paths"]["out_idot"]) == expected


def test_idot_basic_liquids_byte_equal(tmp_path: Path, freeze_now) -> None:
    result = _run_golden("idot_basic", tmp_path)
    expected = _read_bytes(SCENARIOS_DIR / "idot_basic" / "expected_liquids.csv")
    assert _read_bytes(result["paths"]["out_liquids"]) == expected


def test_idot_basic_imeta_byte_equal(tmp_path: Path, freeze_now) -> None:
    result = _run_golden("idot_basic", tmp_path)
    expected = _read_bytes(SCENARIOS_DIR / "idot_basic" / "expected_imeta.csv")
    assert _read_bytes(result["paths"]["out_imeta"]) == expected


def test_idot_omitted_vs_explicit_dispenser_field(tmp_path: Path, freeze_now) -> None:
    """cfg with dispenser='idot' produces identical output to cfg with the field omitted."""
    src = SCENARIOS_DIR / "idot_basic"
    work = tmp_path / "explicit"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    cfg["dispenser"] = "idot"
    out_dir = work / "out"; out_dir.mkdir()
    result = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=False,
    )
    expected = _read_bytes(SCENARIOS_DIR / "idot_basic" / "expected_protocol.csv")
    assert _read_bytes(result["paths"]["out_idot"]) == expected


# ---- Echo goldens -----------------------------------------------------------


def test_echo_basic_byte_equal(tmp_path: Path, freeze_now) -> None:
    result = _run_golden("echo_basic", tmp_path)
    expected = _read_bytes(SCENARIOS_DIR / "echo_basic" / "expected_protocol.csv")
    assert _read_bytes(result["paths"]["out_idot"]) == expected


# ---- Supplied source-plate-layout goldens -----------------------------------


def test_echo_with_supplied_source_layout_byte_equal(tmp_path: Path, freeze_now) -> None:
    """Echo + supplied source-plate layout matches the echo_with_layout golden."""
    src = SCENARIOS_DIR / "echo_with_layout"
    work = tmp_path / "echo_layout"
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
        include_source_prep=False,
        source_layout_path=src / "source_layout.csv",
    )
    expected = _read_bytes(src / "expected_protocol.csv")
    assert _read_bytes(r["paths"]["out_idot"]) == expected


def test_idot_with_supplied_source_layout_byte_equal(tmp_path: Path, freeze_now) -> None:
    """iDOT round-trip: re-feed the golden's liquids CSV as a supplied layout → byte-equal."""
    src = SCENARIOS_DIR / "idot_basic"
    work = tmp_path / "idot_with_layout"
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
        include_source_prep=False,
        source_layout_path=src / "expected_liquids.csv",
    )
    expected = _read_bytes(src / "expected_protocol.csv")
    assert _read_bytes(r["paths"]["out_idot"]) == expected
