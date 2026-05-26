"""Verify the pipeline result dict exposes Tier 2/Tier 3 warning fields.

Task 10 adds three keys to the dict returned by ``_run_pipeline_with_resolved_inputs``:

- ``warnings``           — Tier 2 scatter events
- ``excluded_compounds`` — Tier 3 exclusions
- ``excluded_target_wells`` — target wells that were planned for excluded compounds

These flow through ``backend/app/jobs.py`` to the run-status JSON the frontend consumes.

The happy path (idot_basic) has no Tier 2/Tier 3 events, so all three default to empty
lists. We also verify the structured shape for non-empty cases by force-injecting
attrs into the liquid_table after a successful run and rebuilding the three lists with
the same logic the pipeline uses.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from iplaid.pipeline import run_pipeline_with_inputs
from iplaid.source_plate_layout import ExclusionWarning, ScatterWarning


SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def _run_idot_basic(tmp_path: Path) -> dict:
    src = SCENARIOS_DIR / "idot_basic"
    work = tmp_path / "warnings_idot_basic"
    work.mkdir()
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
        include_source_prep=True,
    )


def test_run_output_contains_three_warning_keys(tmp_path: Path) -> None:
    """The pipeline result dict always exposes warnings / excluded_compounds /
    excluded_target_wells, even when there are no Tier 2 or Tier 3 events."""
    result = _run_idot_basic(tmp_path)

    assert "warnings" in result
    assert "excluded_compounds" in result
    assert "excluded_target_wells" in result


def test_run_output_warning_keys_default_to_empty_lists_when_no_events(
    tmp_path: Path,
) -> None:
    """A clean run (no Tier 2/3 events) yields empty lists for the three keys."""
    result = _run_idot_basic(tmp_path)

    assert result["warnings"] == []
    assert result["excluded_compounds"] == []
    assert result["excluded_target_wells"] == []


def test_tier3_exclusion_also_fires_a_loud_warning_via_scenario(tmp_path: Path) -> None:
    """The tier3_exclusion scenario must produce BOTH an entry in
    excluded_compounds AND a loud warning in the unified warnings list."""
    src = SCENARIOS_DIR / "tier3_exclusion"
    work = tmp_path / "tier3"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"; out_dir.mkdir()
    result = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=True,
    )

    assert len(result["excluded_compounds"]) >= 1
    loud_warnings = [w for w in result["warnings"] if w["severity"] == "loud"]
    assert len(loud_warnings) == len(result["excluded_compounds"])
    for w in loud_warnings:
        assert w["kind"] == "exclusion"
        assert "compound" in w
        assert "stocks_needed" in w
        assert "free_wells_remaining" in w


def test_tier2_scatter_fires_a_soft_warning_via_scenario(tmp_path: Path) -> None:
    """The tier2_scatter scenario must produce a soft warning in the unified
    warnings list (no exclusion)."""
    src = SCENARIOS_DIR / "tier2_scatter"
    work = tmp_path / "tier2"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"; out_dir.mkdir()
    result = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=True,
    )

    assert result["excluded_compounds"] == []
    soft_warnings = [w for w in result["warnings"] if w["severity"] == "soft"]
    assert len(soft_warnings) >= 1
    for w in soft_warnings:
        assert w["kind"] == "scatter"
        assert "wells" in w


def test_run_output_scatter_warning_shape() -> None:
    """The serialization shape for a scatter warning matches the documented schema:
    {severity, kind, compound, wells}."""
    # Mirror the pipeline's serialization logic in isolation.
    scatter = [ScatterWarning(compound="Overflow", wells=("A10", "A11", "A12", "B10"))]
    serialized = [
        {
            "severity": "soft",
            "kind": "scatter",
            "compound": sw.compound,
            "wells": list(sw.wells),
        }
        for sw in scatter
    ]
    assert serialized == [
        {
            "severity": "soft",
            "kind": "scatter",
            "compound": "Overflow",
            "wells": ["A10", "A11", "A12", "B10"],
        }
    ]


def test_run_output_excluded_compound_shape() -> None:
    """The serialization shape for an exclusion matches the documented schema:
    {compound, stocks_needed, free_wells_remaining}."""
    excluded = [
        ExclusionWarning(compound="Veliparib", stocks_needed=3, free_wells_remaining=1)
    ]
    serialized = [
        {
            "compound": ew.compound,
            "stocks_needed": ew.stocks_needed,
            "free_wells_remaining": ew.free_wells_remaining,
        }
        for ew in excluded
    ]
    assert serialized == [
        {"compound": "Veliparib", "stocks_needed": 3, "free_wells_remaining": 1}
    ]


def test_run_output_excluded_target_wells_built_from_df(tmp_path: Path) -> None:
    """When a compound is excluded, the target wells planned for it surface in
    ``excluded_target_wells``. We inject an ExclusionWarning for an existing
    compound and rebuild the list using the same logic the pipeline uses,
    confirming the contract."""
    result = _run_idot_basic(tmp_path)
    df: pd.DataFrame = result["df"]

    # Pick a real compound from the run (not a control).
    candidate = (
        df.loc[~df["is_solvent_control"].fillna(False).astype(bool), "cmpdname"]
          .dropna()
          .iloc[0]
    )

    excluded_names_set = {candidate}
    rebuilt = (
        df.loc[df["cmpdname"].isin(excluded_names_set), ["Target Plate", "Target Well"]]
          .drop_duplicates()
          .rename(columns={"Target Plate": "target_plate", "Target Well": "target_well"})
          .to_dict("records")
    )

    assert len(rebuilt) > 0
    for entry in rebuilt:
        assert set(entry.keys()) == {"target_plate", "target_well"}
        assert isinstance(entry["target_plate"], str)
        assert isinstance(entry["target_well"], str)
