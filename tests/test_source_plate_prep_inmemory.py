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
