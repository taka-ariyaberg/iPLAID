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


def test_phase_b_same_stock_count_clusters_into_emptiest_row():
    # 14 compounds, each with 3 stocks. Sort tied → alphabetical.
    # Phase A claims rows 1-8 with the first 8. Phase B has 6 more, all 3-stock.
    # Same-# preference matches every row; T2 spread picks the emptiest each time.
    # Expected: rows 1-6 each get one additional 3-stock compound at cols D-F.
    names = ["C01","C02","C03","C04","C05","C06","C07","C08",
             "C09","C10","C11","C12","C13","C14"]
    compounds = [CompoundSpec(name=n, stocks_mM=(0.1, 1.0, 10.0)) for n in names]
    result = assign_source_wells(compounds, solvents=[], geometry=PlateGeometry(rows=8, cols=12))

    # First 8 (rows 1-8) at cols A-C.
    for row_idx, name in enumerate(names[:8], start=1):
        assert result.placements[f"[{name}][0.1]"] == f"{_row_label(row_idx)}1"
        assert result.placements[f"[{name}][10.0]"] == f"{_row_label(row_idx)}3"
    # Next 6 (rows 1-6) at cols D-F.
    for row_idx, name in enumerate(names[8:], start=1):
        assert result.placements[f"[{name}][0.1]"] == f"{_row_label(row_idx)}4"
        assert result.placements[f"[{name}][10.0]"] == f"{_row_label(row_idx)}6"


def test_phase_b_fallback_when_no_same_stock_row_fits():
    # 8 × 5-stock compounds → Phase A rows 1-8, each at cols A-E with 7 free trailing.
    # 1 × 4-stock overflow compound X — no 4-stock owner exists, but every row has 7 free ≥ 4.
    # Fallback: pick row with most free space (tied at 7), smallest row index → row 1.
    # X's 4 stocks placed at row 1 cols 6-9.
    compounds = [
        CompoundSpec(name=f"C{i:02d}", stocks_mM=(0.1, 1.0, 10.0, 100.0, 1000.0))
        for i in range(1, 9)
    ]
    compounds.append(CompoundSpec(name="X", stocks_mM=(0.05, 0.5, 5.0, 50.0)))
    result = assign_source_wells(compounds, solvents=[], geometry=PlateGeometry(rows=8, cols=12))
    assert result.placements["[X][0.05]"] == "A6"
    assert result.placements["[X][50.0]"] == "A9"
