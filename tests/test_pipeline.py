"""End-to-end regression tests for run_pipeline_with_inputs.

Locks the iDOT and (later) Echo outputs byte-for-byte against captured goldens.
"""
from __future__ import annotations

import datetime as _datetime
import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.pipeline import run_pipeline_with_inputs  # noqa: E402


GOLDEN_DIR = Path(__file__).parent / "golden"
FROZEN_NOW = _datetime.datetime(2026, 1, 1, 12, 0, 0)


@pytest.fixture
def freeze_now(monkeypatch: pytest.MonkeyPatch):
    """Freeze datetime.now() inside iplaid.output to make the iDOT CSV header deterministic."""
    import iplaid.output as _output

    class _FrozenDateTime(_datetime.datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return FROZEN_NOW if tz is None else FROZEN_NOW.replace(tzinfo=tz)

    monkeypatch.setattr(_output.datetime, "datetime", _FrozenDateTime)
    yield


def _read_bytes(p: Path) -> bytes:
    return Path(p).read_bytes()


def _run_golden(fixture_name: str, tmp_path: Path) -> dict:
    """Copy a golden fixture into tmp_path and run the pipeline against it."""
    src = GOLDEN_DIR / fixture_name
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


def test_idot_basic_protocol_byte_equal(tmp_path: Path, freeze_now) -> None:
    result = _run_golden("idot_basic", tmp_path)
    expected = _read_bytes(GOLDEN_DIR / "idot_basic" / "expected_protocol.csv")
    actual = _read_bytes(result["paths"]["out_idot"])
    assert actual == expected, "iDOT protocol CSV diverged from golden"


def test_idot_basic_liquids_byte_equal(tmp_path: Path, freeze_now) -> None:
    result = _run_golden("idot_basic", tmp_path)
    expected = _read_bytes(GOLDEN_DIR / "idot_basic" / "expected_liquids.csv")
    actual = _read_bytes(result["paths"]["out_liquids"])
    assert actual == expected


def test_idot_basic_imeta_byte_equal(tmp_path: Path, freeze_now) -> None:
    result = _run_golden("idot_basic", tmp_path)
    expected = _read_bytes(GOLDEN_DIR / "idot_basic" / "expected_imeta.csv")
    actual = _read_bytes(result["paths"]["out_imeta"])
    assert actual == expected


def test_echo_smoke_produces_valid_csv(tmp_path: Path, freeze_now) -> None:
    """Run the full pipeline with dispenser='echo' and verify the output validates."""
    import pandas as pd

    src = GOLDEN_DIR / "idot_basic"
    work = tmp_path / "echo_smoke"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    cfg["dispenser"] = "echo"
    cfg["sourceplate_type"] = "384LDV"
    cfg["target_plate_type"] = "Revvity_384_6007660"
    cfg["working_volume_ul"] = 50
    out_dir = work / "out"
    out_dir.mkdir()

    result = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=False,
    )
    out_path = Path(result["paths"]["out_idot"])
    assert out_path.exists()
    df = pd.read_csv(out_path)
    assert len(df.columns) == 10
    assert df.columns[0] == "Sample Name"
    assert df.columns[5] == "Transfer Volume"
    vols = pd.to_numeric(df["Transfer Volume"])
    assert ((vols % 2.5).round(6) == 0).all()


def test_echo_basic_byte_equal(tmp_path: Path, freeze_now) -> None:
    result = _run_golden("echo_basic", tmp_path)
    expected = (GOLDEN_DIR / "echo_basic" / "expected_protocol.csv").read_bytes()
    actual = Path(result["paths"]["out_idot"]).read_bytes()
    assert actual == expected, "Echo protocol CSV diverged from golden"


def test_idot_explicit_dispenser_field_byte_equal(tmp_path: Path, freeze_now) -> None:
    """cfg with dispenser='idot' produces identical output to cfg with no dispenser field."""
    src = GOLDEN_DIR / "idot_basic"
    work = tmp_path / "explicit"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    cfg["dispenser"] = "idot"
    out_dir = work / "out"
    out_dir.mkdir()
    result = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=False,
    )
    expected = (GOLDEN_DIR / "idot_basic" / "expected_protocol.csv").read_bytes()
    assert Path(result["paths"]["out_idot"]).read_bytes() == expected
