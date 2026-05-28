"""Unit tests for aggregate_dispenses_per_stock — the in-memory replacement
for sum_volumes_per_compound. Verifies shape parity with the legacy CSV-based
aggregator and the solvent-topup filter."""

import pandas as pd

from src.iplaid.source_plate_prep import aggregate_dispenses_per_stock


def _sample_liquid_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Liquid Name": "[DrugA][10.0]", "Source Plate": "src", "Source Well": "A1"},
            {"Liquid Name": "[DrugA][1.0]",  "Source Plate": "src", "Source Well": "A2"},
            {"Liquid Name": "[DrugB][10.0]", "Source Plate": "src", "Source Well": "B1"},
            {"Liquid Name": "[DMSO][0.0]",   "Source Plate": "src", "Source Well": "H12"},
        ]
    )


def _sample_all_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Target Plate": "p1", "Target Well": "B02", "Liquid Name": "[DrugA][10.0]", "Volume [uL]": 0.040},
            {"Target Plate": "p1", "Target Well": "B03", "Liquid Name": "[DrugA][10.0]", "Volume [uL]": 0.040},
            {"Target Plate": "p1", "Target Well": "C02", "Liquid Name": "[DrugA][1.0]",  "Volume [uL]": 0.012},
            {"Target Plate": "p1", "Target Well": "D02", "Liquid Name": "[DrugB][10.0]", "Volume [uL]": 0.030},
            {"Target Plate": "p1", "Target Well": "D03", "Liquid Name": "[DMSO][0.0]",   "Volume [uL]": 0.060},
        ]
    )


def test_aggregator_returns_compound_concentration_keys():
    result = aggregate_dispenses_per_stock(_sample_all_rows(), _sample_liquid_table())
    assert set(result.keys()) == {("DrugA", 10.0), ("DrugA", 1.0), ("DrugB", 10.0)}


def test_aggregator_sums_volumes_per_stock():
    result = aggregate_dispenses_per_stock(_sample_all_rows(), _sample_liquid_table())
    assert result[("DrugA", 10.0)]["dispense_volume_uL"] == 0.080
    assert result[("DrugA", 1.0)]["dispense_volume_uL"] == 0.012
    assert result[("DrugB", 10.0)]["dispense_volume_uL"] == 0.030


def test_aggregator_attaches_source_wells_from_liquid_table():
    result = aggregate_dispenses_per_stock(_sample_all_rows(), _sample_liquid_table())
    assert result[("DrugA", 10.0)]["source_well"] == "A1"
    assert result[("DrugA", 1.0)]["source_well"] == "A2"
    assert result[("DrugB", 10.0)]["source_well"] == "B1"


def test_aggregator_filters_solvent_topup_liquids():
    result = aggregate_dispenses_per_stock(_sample_all_rows(), _sample_liquid_table())
    assert ("DMSO", 0.0) not in result
    assert all(conc != 0.0 for (_, conc) in result.keys())


def test_aggregator_ignores_dispense_rows_with_unknown_liquid_name():
    rows = _sample_all_rows()
    rows = pd.concat(
        [rows, pd.DataFrame([{
            "Target Plate": "p1", "Target Well": "Z01", "Liquid Name": "[Mystery][5.0]", "Volume [uL]": 0.5
        }])],
        ignore_index=True,
    )
    result = aggregate_dispenses_per_stock(rows, _sample_liquid_table())
    assert ("Mystery", 5.0) not in result


import json
import tempfile
from pathlib import Path

from src.iplaid.source_plate_prep import generate_source_plate_prep_instructions


def _write_specs(tmpdir: Path, sourceplate_type: str = "S.100 Plate") -> Path:
    specs_path = tmpdir / "specs.json"
    specs_path.write_text(json.dumps({
        sourceplate_type: {
            "wells": 96, "rows": 8, "cols": 12,
            "dead_volume_uL_aq_lt": 1.0,
            "effective_reservoir_uL": 80.0,
        }
    }))
    return specs_path


def _write_meta(tmpdir: Path) -> Path:
    meta_path = tmpdir / "meta.csv"
    meta_path.write_text(
        "cmpdname,highest_stock_mM,solvent\n"
        "DrugA,100,DMSO\n"
        "DrugB,100,DMSO\n"
        "DMSO,0,DMSO\n"
    )
    return meta_path


def test_generate_instructions_in_memory_path_produces_txt():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        cfg = {
            "user_name": "u",
            "sourceplate_type": "S.100 Plate",
            "source_prep_overage_pct": 0.30,
            "standard_prep_volume_uL": 1000.0,
            "source_well_fill_pct": 0.70,
        }
        _, txt = generate_source_plate_prep_instructions(
            output_dir=tmpdir,
            config=cfg,
            meta_path=_write_meta(tmpdir),
            plate_specs_path=_write_specs(tmpdir),
            protocol_name="t",
            layout_file="x.csv",
            all_rows=_sample_all_rows(),
            liquid_table=_sample_liquid_table(),
        )
    assert "SOURCE PLATE PREPARATION INSTRUCTIONS" in txt
    assert "DrugA" in txt
    assert "DrugB" in txt
    assert "COMPOUND: DMSO" not in txt
