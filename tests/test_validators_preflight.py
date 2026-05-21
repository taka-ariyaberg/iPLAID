"""Tests for iplaid.validators_preflight.calculate_required_solvent_pct."""
from __future__ import annotations

from iplaid.validators_preflight import calculate_required_solvent_pct


def test_basic_target_within_solvent_limit():
    # 30 µM target, 100 mM stock → 0.03% solvent
    is_feasible, required_pct, _reason = calculate_required_solvent_pct(
        target_conc_um=30,
        highest_stock_mm=100,
        working_volume_ul=40,
        sourceplate_type="S.100 Plate",
    )
    assert is_feasible is True
    assert required_pct is not None
    assert abs(required_pct - 0.03) < 1e-6


def test_solvent_control_row_is_feasible():
    is_feasible, required_pct, _ = calculate_required_solvent_pct(
        target_conc_um=0,
        highest_stock_mm=0,
        working_volume_ul=40,
        sourceplate_type="S.100 Plate",
    )
    assert is_feasible is True
    assert required_pct == 0.0


def test_returns_required_pct_below_typical_limit():
    _, required_pct, _ = calculate_required_solvent_pct(
        target_conc_um=30,
        highest_stock_mm=100,
        working_volume_ul=40,
        sourceplate_type="S.100 Plate",
    )
    assert required_pct <= 0.1
