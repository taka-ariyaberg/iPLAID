"""Tests for iplaid.calculations — stockfinder, volume_from_stock, remove_leading_zero."""
from __future__ import annotations

import pytest

from iplaid.calculations import (
    remove_leading_zero,
    stockfinder,
    volume_from_stock,
)


class TestVolumeFromStock:
    def test_basic(self):
        # Target: 10 µM in 40 µL from 1 mM stock → 0.4 µL
        assert abs(volume_from_stock(10, 1, 40) - 0.4) < 1e-9

    def test_various_concentrations(self):
        cases = [
            (30, 100, 40, 0.012),
            (30, 10, 40, 0.12),
            (10, 1, 40, 0.4),
            (100, 100, 40, 0.04),
        ]
        for target, stock, vol, expected in cases:
            assert abs(volume_from_stock(target, stock, vol) - expected) < 1e-9, (target, stock)

    def test_zero_target_returns_zero(self):
        assert volume_from_stock(0, 100, 40) == 0


class TestStockfinder:
    def test_picks_highest_suitable_stock(self):
        stock = stockfinder(
            concUM=30, highest_stock_mM=100, V2_ul=40,
            dmso_percmax=0.1, sourceplate_type="S.100 Plate",
        )
        assert stock == 100.0

    def test_respects_dmso_limit(self):
        stock = stockfinder(
            concUM=50, highest_stock_mM=100, V2_ul=40,
            dmso_percmax=0.5, sourceplate_type="S.100 Plate",
        )
        assert stock > 0


def test_remove_leading_zero_formats():
    assert remove_leading_zero("A08") == "A8"
    assert remove_leading_zero("B12") == "B12"
    assert remove_leading_zero("H01") == "H1"
    assert remove_leading_zero("A1") == "A1"
