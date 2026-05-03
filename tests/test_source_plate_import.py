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


def test_echo_with_supplied_layout_byte_equal(tmp_path: Path) -> None:
    """Echo + supplied layout reproduces echo_basic byte-equal.

    The supplied layout matches the auto-assignment for this fixture so the
    output is byte-identical to the echo_basic golden. This proves the
    layout-import code path doesn't perturb the protocol when wells happen
    to coincide.
    """
    import json
    import shutil
    from iplaid.pipeline import run_pipeline_with_inputs

    src = Path(__file__).parent / "golden" / "echo_with_layout"
    work = tmp_path / "echo_layout"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"
    out_dir.mkdir()
    r = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=False,
        source_layout_path=src / "source_layout.csv",
    )
    expected = (src / "expected_protocol.csv").read_bytes()
    assert Path(r["paths"]["out_idot"]).read_bytes() == expected


def test_pipeline_with_existing_source_layout_idot(tmp_path: Path) -> None:
    """Round-trip: capture iDOT goldens layout, then re-run with it as input → byte-equal."""
    import datetime as _dt
    import json
    import shutil
    from iplaid.pipeline import run_pipeline_with_inputs
    import iplaid.output as _output

    # Freeze datetime.now so the iDOT header timestamp matches the golden capture.
    FROZEN = _dt.datetime(2026, 1, 1, 12, 0, 0)
    class _F(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return FROZEN if tz is None else FROZEN.replace(tzinfo=tz)
    orig = _output.datetime.datetime
    _output.datetime.datetime = _F
    try:
        src = Path(__file__).parent / "golden" / "idot_basic"
        layout_csv = src / "expected_liquids.csv"

        work = tmp_path / "with_layout"
        work.mkdir()
        shutil.copy(src / "layout.csv", work / "layout.csv")
        shutil.copy(src / "meta.csv", work / "meta.csv")
        cfg = json.loads((src / "config.json").read_text())
        out_dir = work / "out"
        out_dir.mkdir()
        r = run_pipeline_with_inputs(
            config=cfg,
            layout_path=work / "layout.csv",
            meta_path=work / "meta.csv",
            output_dir=out_dir,
            include_source_prep=False,
            source_layout_path=layout_csv,
        )
        expected = (src / "expected_protocol.csv").read_bytes()
        assert Path(r["paths"]["out_idot"]).read_bytes() == expected
    finally:
        _output.datetime.datetime = orig


def test_uploaded_source_layout_writes_summary_for_idot(tmp_path: Path) -> None:
    """Existing iDOT source layouts produce a usage summary, not prep recipes."""
    import json
    import shutil
    from iplaid.pipeline import run_pipeline_with_inputs

    src = Path(__file__).parent / "golden" / "idot_basic"
    work = tmp_path / "idot_summary"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"
    out_dir.mkdir()

    r = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=True,
        source_layout_path=src / "expected_liquids.csv",
    )

    text = str(r["source_prep_instructions"])
    assert "SOURCE PLATE LAYOUT SUMMARY" in text
    assert "source of truth" in text
    assert "This file is a usage summary, not a preparation recipe." in text
    assert "STEP " not in text
    assert "[Dasatinib][0.1]" in text
    assert Path(r["paths"]["out_source_prep"]).read_text() == text


def test_uploaded_source_layout_writes_summary_for_echo(tmp_path: Path) -> None:
    """Existing Echo source layouts produce a summary instead of the v2 placeholder."""
    import json
    import shutil
    from iplaid.pipeline import run_pipeline_with_inputs

    src = Path(__file__).parent / "golden" / "echo_with_layout"
    work = tmp_path / "echo_summary"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"
    out_dir.mkdir()

    r = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=True,
        source_layout_path=src / "source_layout.csv",
    )

    text = str(r["source_prep_instructions"])
    assert "SOURCE PLATE LAYOUT SUMMARY" in text
    assert "Dispenser: echo" in text
    assert "v2" not in text
    assert "[Dasatinib][0.1]" in text


def test_uploaded_source_layout_rejects_wells_outside_source_plate(tmp_path: Path) -> None:
    """Uploaded source-layout wells must exist on the selected source plate."""
    import json
    import shutil
    from iplaid.pipeline import run_pipeline_with_inputs

    src = Path(__file__).parent / "golden" / "idot_basic"
    work = tmp_path / "bad_source_layout"
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


def test_build_liquid_table_layout_unused_entries_warn_not_fail(capsys) -> None:
    layout = pd.DataFrame({
        "Source Well": ["A07", "A10", "A12", "A15"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]", "[unused][5.0]"],
    })
    lt, _ = build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)
    captured = capsys.readouterr()
    assert "unused" in captured.out.lower() or "1 layout entr" in captured.out.lower()
