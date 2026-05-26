from iplaid.source_plate_layout import (
    assign_source_wells,
    CompoundSpec,
    PlateGeometry,
    _row_label,
)


def test_single_compound_single_stock_lands_at_A1():
    result = assign_source_wells(
        compounds=[CompoundSpec(name="Dasatinib", stocks_mM=(0.1,))],
        solvents=[],
        geometry=PlateGeometry(rows=8, cols=12),
    )
    assert result.placements["[Dasatinib][0.1]"] == "A1"
    assert result.excluded == []
    assert result.scatter_warnings == []


def test_phase_a_three_compounds_each_claim_a_row():
    result = assign_source_wells(
        compounds=[
            CompoundSpec(name="Adavosertib", stocks_mM=(0.1, 1.0, 10.0)),
            CompoundSpec(name="Berzosertib", stocks_mM=(0.5, 5.0, 50.0)),
            CompoundSpec(name="Carboplatin", stocks_mM=(1.0, 10.0)),
        ],
        solvents=[],
        geometry=PlateGeometry(rows=8, cols=12),
    )
    # Sort descending by # stocks → 3-stock compounds first (alphabetical tiebreak: Adavosertib, Berzosertib),
    # then 2-stock Carboplatin. Each claims a fresh row, ascending concentration left to right.
    assert result.placements["[Adavosertib][0.1]"] == "A1"
    assert result.placements["[Adavosertib][1.0]"] == "A2"
    assert result.placements["[Adavosertib][10.0]"] == "A3"
    assert result.placements["[Berzosertib][0.5]"] == "B1"
    assert result.placements["[Berzosertib][5.0]"] == "B2"
    assert result.placements["[Berzosertib][50.0]"] == "B3"
    assert result.placements["[Carboplatin][1.0]"] == "C1"
    assert result.placements["[Carboplatin][10.0]"] == "C2"
    assert result.excluded == []


def test_phase_a_eight_compounds_fill_all_rows():
    compounds = [
        CompoundSpec(name=name, stocks_mM=(1.0,))
        for name in "ABCDEFGH"
    ]
    result = assign_source_wells(compounds, solvents=[], geometry=PlateGeometry(rows=8, cols=12))
    for row_idx, letter in enumerate("ABCDEFGH", start=1):
        assert result.placements[f"[{letter}][1.0]"] == f"{_row_label(row_idx)}1"
