"""Source-plate-prep behavior across dispensers.

iDOT prep is the v1 path. Echo prep is deferred to v2 per spec §15;
this test pins the placeholder behavior so future v2 work has a known
starting point and downstream consumers don't crash on the placeholder.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.pipeline import run_pipeline_with_inputs  # noqa: E402


GOLDEN_DIR = Path(__file__).parent / "golden"


def test_source_plate_prep_runs_for_echo_with_placeholder(tmp_path: Path) -> None:
    """Echo + include_source_prep=True must not crash and must emit a placeholder note."""
    src = GOLDEN_DIR / "echo_basic"
    work = tmp_path / "prep"
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
    )
    assert r["source_prep_instructions"] is not None
    text = str(r["source_prep_instructions"])
    assert "v2" in text  # placeholder marker
    assert r["paths"]["out_source_prep"] is not None
    assert Path(r["paths"]["out_source_prep"]).exists()
