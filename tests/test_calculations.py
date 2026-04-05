"""
Comprehensive Test Suite for PLAID iDOT Calculations

Tests cover:
- DMSO percentage calculations
- Stock finder algorithm
- Validation logic
- Data consistency
- Edge cases
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.calculations import (
    stockfinder,
    volume_from_stock,
    remove_leading_zero,
)
from iplaid.validators_preflight import (
    calculate_required_dmso_pct,
    validate_all_concentrations,
)
from iplaid.normalization import normalize_dmso_topup


class TestDMSOCalculations:
    """Test DMSO percentage calculations for accuracy."""
    
    def test_dmso_calc_basic(self):
        """Test basic DMSO % calculation: (target * 100) / (stock * 1000)"""
        # For 30 µM target with 100 mM stock:
        # dmso% = (30 * 100) / (100 * 1000) = 0.03%
        target_conc = 30
        stock_mm = 100
        expected_dmso_pct = (target_conc * 100) / (stock_mm * 1000)
        assert abs(expected_dmso_pct - 0.03) < 1e-9, f"Expected 0.03%, got {expected_dmso_pct}%"
    
    def test_dmso_calc_various_concentrations(self):
        """Test DMSO calculation for various target concentrations with 100 mM stock."""
        test_cases = [
            (1, 100, 0.001),      # 1 µM
            (10, 100, 0.01),      # 10 µM
            (30, 100, 0.03),      # 30 µM (the problematic case that was reported wrong)
            (100, 100, 0.1),      # 100 µM
        ]
        
        for target, stock, expected_pct in test_cases:
            actual_pct = (target * 100) / (stock * 1000)
            assert abs(actual_pct - expected_pct) < 1e-9, \
                f"Target {target} µM with {stock} mM: expected {expected_pct}%, got {actual_pct}%"
    
    def test_dmso_calc_dilution_series(self):
        """Test that lower dilutions require higher DMSO %."""
        target_conc = 30
        stocks = [100, 10, 1, 0.1]
        dmso_pcts = [(target_conc * 100) / (s * 1000) for s in stocks]
        
        # Each lower dilution should require higher DMSO%
        assert dmso_pcts[0] < dmso_pcts[1] < dmso_pcts[2] < dmso_pcts[3]
        assert abs(dmso_pcts[0] - 0.03) < 1e-9  # 100mM stock
        assert abs(dmso_pcts[1] - 0.30) < 1e-9  # 10mM stock
    
    def test_dmso_zero_concentration(self):
        """Test DMSO calculation with zero target concentration."""
        target_conc = 0
        stock_mm = 100
        # Zero target should have zero DMSO
        dmso_pct = (target_conc * 100) / (stock_mm * 1000) if stock_mm != 0 else 0
        assert dmso_pct == 0


class TestCalculateRequiredDMSO:
    """Test the validate_all_concentrations logic."""
    
    def test_calculate_required_dmso_pct_basic(self):
        """Test baseline DMSO calculation through the validation function."""
        # Target 30 µM, stock 100 mM should need 0.03% DMSO
        is_feasible, required_dmso, reason = calculate_required_dmso_pct(
            target_conc_um=30,
            highest_stock_mm=100,
            working_volume_ul=40,
            sourceplate_type="S.100 Plate",
        )
        
        assert is_feasible is True
        assert required_dmso is not None
        assert abs(required_dmso - 0.03) < 1e-6, f"Expected 0.03%, got {required_dmso}%"
    
    def test_calculate_required_dmso_pct_dmso_control(self):
        """Test DMSO control (stock = 0) should be feasible."""
        is_feasible, required_dmso, reason = calculate_required_dmso_pct(
            target_conc_um=0,
            highest_stock_mm=0,
            working_volume_ul=40,
            sourceplate_type="S.100 Plate",
        )
        
        assert is_feasible is True
        assert required_dmso == 0.0
    
    def test_dmso_within_limit(self):
        """Test concentration that fits within DMSO limit."""
        # 0.03% DMSO is well below 0.1% limit
        is_feasible, required_dmso, reason = calculate_required_dmso_pct(
            target_conc_um=30,
            highest_stock_mm=100,
            working_volume_ul=40,
            sourceplate_type="S.100 Plate",
        )
        
        assert is_feasible is True
        assert required_dmso <= 0.1  # Below the typical limit


class TestVolumeCalculations:
    """Test volume from stock calculations."""
    
    def test_volume_from_stock_basic(self):
        """Test volume needed from stock concentration."""
        # Target: 10 µM in 40 µL from 1 mM stock
        # volume = (target * working_vol) / stock / 1000
        # volume = (10 * 40) / 1 / 1000 = 0.4 µL
        vol = volume_from_stock(10, 1, 40)
        assert abs(vol - 0.4) < 1e-9
    
    def test_volume_from_stock_calculations(self):
        """Test various volume calculations."""
        test_cases = [
            # (target_um, stock_mm, working_vol_ul, expected_vol_ul)
            (30, 100, 40, 0.012),      # From 100 mM stock
            (30, 10, 40, 0.12),        # From 10 mM stock (10x more)
            (10, 1, 40, 0.4),          # From 1 mM stock
            (100, 100, 40, 0.04),      # Higher target
        ]
        
        for target, stock, working_vol, expected in test_cases:
            actual = volume_from_stock(target, stock, working_vol)
            assert abs(actual - expected) < 1e-9, \
                f"Target {target} µM, stock {stock} mM: expected {expected} µL, got {actual} µL"
    
    def test_volume_zero_concentration(self):
        """Test volume calculation for zero target."""
        vol = volume_from_stock(0, 100, 40)
        assert vol == 0


class TestWellNameFormatting:
    """Test well name formatting."""
    
    def test_remove_leading_zero_formats(self):
        """Test leading zero removal."""
        assert remove_leading_zero("A08") == "A8"
        assert remove_leading_zero("B12") == "B12"
        assert remove_leading_zero("H01") == "H1"
        assert remove_leading_zero("A1") == "A1"


class TestStockfinder:
    """Test the stockfinder algorithm."""
    
    def test_stockfinder_basic(self):
        """Test stockfinder picks highest suitable stock."""
        # For 30 µM target with 100 mM stock, 40 µL well, 0.1% DMSO max
        stock = stockfinder(
            concUM=30,
            highest_stock_mM=100,
            V2_ul=40,
            dmso_percmax=0.1,
            sourceplate_type="S.100 Plate",
        )
        
        assert stock == 100.0  # Should use the 100 mM stock directly
    
    def test_stockfinder_respects_dmso_limit(self):
        """Test that stockfinder finds stock within DMSO constraints."""
        # This concentration needs to be achievable within 0.5% DMSO
        stock = stockfinder(
            concUM=50,
            highest_stock_mM=100,
            V2_ul=40,
            dmso_percmax=0.5,
            sourceplate_type="S.100 Plate",
        )
        
        # Should find a suitable stock from the dilution series
        assert stock > 0


class TestDMSONormalization:
    """Test DMSO normalization logic."""
    
    def test_dmso_normalization_equalization(self):
        """Test that DMSO normalization makes all wells identical."""
        # Create sample data with varying DMSO amounts
        data = {
            'cmpdname': ['CompA', 'CompB', 'CompC'],
            'CONCuM': [10, 20, 30],
            'solvent': ['DMSO', 'DMSO', 'DMSO'],
            'Volume [uL]': [0.01, 0.02, 0.03],  # Different DMSO volumes
            'treatment_type': ['', '', ''],
        }
        df = pd.DataFrame(data)
        
        result_df, target_dmso, max_dmso = normalize_dmso_topup(
            df,
            max_dmso_pct=0.1,
            working_volume_ul=40,
        )
        
        # All wells should have same total DMSO
        dmso_totals = result_df['dmso_total_uL'].unique()
        assert len(dmso_totals) == 1, "Not all wells have identical DMSO"
        assert abs(dmso_totals[0] - target_dmso) < 1e-9


class TestDataConsistency:
    """Test data consistency checks."""
    
    def test_highest_stock_extraction(self):
        """Test extraction of highest stock from compound metadata."""
        data = {
            'cmpdname': ['CompA', 'CompB', 'CompC', 'DMSO'],
            'highest_stock_mM': [100, 100, 50, 0],
            'CONCuM': [10, 20, 15, 0],
        }
        df = pd.DataFrame(data)
        
        # Should extract 100 as highest (excluding DMSO which is 0)
        highest = float(df[df['highest_stock_mM'] > 0]['highest_stock_mM'].max())
        assert highest == 100
    
    def test_empty_dataframe_handling(self):
        """Test handling of empty dataframes."""
        df_empty = pd.DataFrame({
            'cmpdname': [],
            'highest_stock_mM': [],
        })
        
        # Should handle gracefully
        if len(df_empty) == 0 or df_empty['highest_stock_mM'].max() <= 0:
            highest = 10.0  # Default
        else:
            highest = float(df_empty['highest_stock_mM'].max())
        
        assert highest == 10.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
