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


def test_tier_2_scatter_when_no_row_fits_but_total_free_enough():
    # 8 compounds in Phase A, each claims a row of 9 stocks → 3 trailing free cols per row.
    # 8 rows × 3 free = 24 trailing free wells total.
    # 9th compound has 4 stocks — no row has 4 contiguous, scatter into row-major free wells.
    compounds = [
        CompoundSpec(name=f"C{i:02d}", stocks_mM=tuple(float(j) for j in range(1, 10)))
        for i in range(1, 9)
    ]
    compounds.append(CompoundSpec(name="Overflow", stocks_mM=(0.1, 1.0, 10.0, 100.0)))
    result = assign_source_wells(compounds, solvents=[], geometry=PlateGeometry(rows=8, cols=12))

    # Each Phase A row used cols 1-9 → first free wells in row-major order: A10, A11, A12, B10.
    assert result.placements["[Overflow][0.1]"] == "A10"
    assert result.placements["[Overflow][1.0]"] == "A11"
    assert result.placements["[Overflow][10.0]"] == "A12"
    assert result.placements["[Overflow][100.0]"] == "B10"

    assert len(result.scatter_warnings) == 1
    assert result.scatter_warnings[0].compound == "Overflow"
    assert result.scatter_warnings[0].wells == ("A10", "A11", "A12", "B10")


def test_tier_3_exclusion_when_total_free_insufficient():
    # 8 compounds each with 12 stocks → Phase A fills the entire 96-well plate.
    # 9th compound with 1 stock cannot fit anywhere.
    compounds = [
        CompoundSpec(name=f"C{i:02d}", stocks_mM=tuple(float(j) for j in range(1, 13)))
        for i in range(1, 9)
    ]
    compounds.append(CompoundSpec(name="Dropped", stocks_mM=(0.1,)))
    result = assign_source_wells(compounds, solvents=[], geometry=PlateGeometry(rows=8, cols=12))

    assert "[Dropped][0.1]" not in result.placements
    assert len(result.excluded) == 1
    assert result.excluded[0].compound == "Dropped"
    assert result.excluded[0].stocks_needed == 1
    assert result.excluded[0].free_wells_remaining == 0


def test_tier_3_exclusion_partial_when_only_some_stocks_fit():
    # 7 compounds with 12 stocks each + 1 compound with 11 stocks → 7×12 + 11 = 95 wells used in Phase A.
    # Phase A rows 1-7: full; Phase A row 8: 11 cols used, 1 free trailing.
    # 9th compound has 3 stocks — total free is 1, less than 3 → Tier 3 exclusion.
    compounds = [
        CompoundSpec(name=f"C{i:02d}", stocks_mM=tuple(float(j) for j in range(1, 13)))
        for i in range(1, 8)
    ]
    compounds.append(
        CompoundSpec(name="C08", stocks_mM=tuple(float(j) for j in range(1, 12)))
    )
    compounds.append(CompoundSpec(name="Wants3", stocks_mM=(0.1, 1.0, 10.0)))
    result = assign_source_wells(compounds, solvents=[], geometry=PlateGeometry(rows=8, cols=12))
    assert "[Wants3][0.1]" not in result.placements
    assert len(result.excluded) == 1
    assert result.excluded[0].compound == "Wants3"
    assert result.excluded[0].free_wells_remaining == 1


def test_solvents_reserved_at_bottom_right():
    result = assign_source_wells(
        compounds=[CompoundSpec(name="Dasatinib", stocks_mM=(0.1, 1.0, 10.0))],
        solvents=["DMSO", "water"],
        geometry=PlateGeometry(rows=8, cols=12),
    )
    # DMSO at H12 (bottom-right), water at G12 (one row up, same col).
    assert result.placements["[DMSO][0.0]"] == "H12"
    assert result.placements["[water][0.0]"] == "G12"
    # Compound still at A1 — solvent reservation does not displace it.
    assert result.placements["[Dasatinib][0.1]"] == "A1"


def test_solvents_never_displaced_by_packed_compounds():
    # 8 compounds × 11 stocks each → Phase A rows 1-8, cols 1-11 used.
    # Col 12 in every row is initially free, but H12 and G12 are reserved for solvents.
    # Each row has 1 free trailing non-reserved col (col 12) EXCEPT rows G and H whose col 12 is reserved.
    # Solvents land at H12 and G12 regardless of compound packing.
    compounds = [
        CompoundSpec(name=f"C{i:02d}", stocks_mM=tuple(float(j) for j in range(1, 12)))
        for i in range(1, 9)
    ]
    result = assign_source_wells(
        compounds=compounds,
        solvents=["DMSO", "water"],
        geometry=PlateGeometry(rows=8, cols=12),
    )
    assert result.placements["[DMSO][0.0]"] == "H12"
    assert result.placements["[water][0.0]"] == "G12"


def test_reserved_wells_excluded_from_phase_b_candidates():
    # 8 compounds × 9 stocks each → Phase A rows 1-8, cols 1-9 used. Each row has 3 trailing cols free.
    # Reserve 8 solvents → fills col 12 in all rows (H12..A12).
    # 9th compound has 3 stocks → in each Phase A row, contiguous non-reserved free from col 10 is only 2 (cols 10, 11).
    # So no Phase B candidate; Tier 2 should attempt scatter. Total non-reserved free wells: 8 rows × 2 = 16. Wait, that's enough for 3.
    # Scatter places at A10, A11, B10 (row-major non-reserved). The compound shouldn't crash.
    compounds = [
        CompoundSpec(name=f"C{i:02d}", stocks_mM=tuple(float(j) for j in range(1, 10)))
        for i in range(1, 9)
    ]
    compounds.append(CompoundSpec(name="Overflow", stocks_mM=(0.1, 1.0, 10.0)))
    solvents = [f"S{i}" for i in range(1, 9)]
    result = assign_source_wells(
        compounds=compounds,
        solvents=solvents,
        geometry=PlateGeometry(rows=8, cols=12),
    )
    # Overflow scatters because col 12 is reserved across all rows, leaving cols 10-11 = 2 contiguous.
    assert result.placements["[Overflow][0.1]"] == "A10"
    assert result.placements["[Overflow][1.0]"] == "A11"
    assert result.placements["[Overflow][10.0]"] == "B10"
    assert len(result.scatter_warnings) == 1
    # All 8 solvents present in their reserved wells (H12, G12, ..., A12).
    for i, solvent_name in enumerate(solvents):
        # Reservation order: H12, G12, F12, E12, D12, C12, B12, A12 → rows 8,7,6,5,4,3,2,1.
        row_idx = 8 - i
        assert result.placements[f"[{solvent_name}][0.0]"] == f"{_row_label(row_idx)}12"
