"""Verify Tier 3 exclusion cascades cleanly — no NaN source wells in the protocol."""
import pandas as pd
from iplaid.output import build_liquid_table, attach_and_sort_dispense_rows


def test_excluded_compound_dispense_rows_dropped_before_source_well_merge():
    """If a Liquid Name is missing from liquid_table_export (compound excluded),
    filtering all_rows by membership BEFORE the source-well merge prevents NaN
    cascade into the protocol."""
    all_rows = pd.DataFrame({
        "Target Plate": ["P1", "P1"],
        "Target Well": ["A1", "B1"],
        "Liquid Name": ["[Placed][1.0]", "[Excluded][1.0]"],
        "Volume [uL]": [0.5, 0.5],
    })
    liquid_table = pd.DataFrame({
        "Liquid Name": ["[Placed][1.0]"],
        "compound": ["Placed"],
        "stock_str": ["1.0"],
        "stock_mM": [1.0],
        "is_control_liquid": [False],
        "sort_group": [1],
        "Source Plate": ["SRC_TEST"],
        "Source Well": ["A1"],
    })
    liquid_table_export = liquid_table[["Liquid Name", "Source Plate", "Source Well"]].copy()

    # Filter all_rows by liquid_table_export membership BEFORE merging:
    placed_liquids = set(liquid_table_export["Liquid Name"])
    filtered_rows = all_rows[all_rows["Liquid Name"].isin(placed_liquids)].copy()

    merged = attach_and_sort_dispense_rows(filtered_rows, liquid_table, liquid_table_export)
    assert merged["Source Well"].notna().all()
    assert len(merged) == 1
    assert merged.iloc[0]["Liquid Name"] == "[Placed][1.0]"


def test_unfiltered_all_rows_produces_NaN_source_wells():
    """Demonstrates the bug Task 8 prevents: without filtering, NaN leaks through."""
    all_rows = pd.DataFrame({
        "Target Plate": ["P1", "P1"],
        "Target Well": ["A1", "B1"],
        "Liquid Name": ["[Placed][1.0]", "[Excluded][1.0]"],
        "Volume [uL]": [0.5, 0.5],
    })
    liquid_table = pd.DataFrame({
        "Liquid Name": ["[Placed][1.0]"],
        "compound": ["Placed"],
        "stock_str": ["1.0"],
        "stock_mM": [1.0],
        "is_control_liquid": [False],
        "sort_group": [1],
        "Source Plate": ["SRC_TEST"],
        "Source Well": ["A1"],
    })
    liquid_table_export = liquid_table[["Liquid Name", "Source Plate", "Source Well"]].copy()
    merged = attach_and_sort_dispense_rows(all_rows, liquid_table, liquid_table_export)
    # Without filtering, the Excluded row's Source Well is NaN.
    assert merged["Source Well"].isna().sum() == 1
