from iplaid.source_plate_layout import assign_source_wells, CompoundSpec, PlateGeometry


def test_single_compound_single_stock_lands_at_A1():
    result = assign_source_wells(
        compounds=[CompoundSpec(name="Dasatinib", stocks_mM=(0.1,))],
        solvents=[],
        geometry=PlateGeometry(rows=8, cols=12),
    )
    assert result.placements["[Dasatinib][0.1]"] == "A1"
    assert result.excluded == []
    assert result.scatter_warnings == []
