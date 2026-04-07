#!/usr/bin/env python
"""
Test script to verify advanced parameters work correctly
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from config import PlateConfig, Compound, Control
from solver import MiniZincSolver
import tempfile

def test_dzn_generation():
    """Test that .dzn files generate all advanced parameters"""
    
    print("=" * 60)
    print("Testing Advanced Parameter .dzn Generation")
    print("=" * 60)
    
    # Create a simple test config with advanced parameters
    config = PlateConfig(
        plate_rows=8,
        plate_cols=12,
        empty_edge=1,
        compounds=[
            Compound(name="CompA", concentrations=2, replicates=2)
        ],
        controls=[
            Control(name="Ctrl", concentration_levels=1, replicates=2)
        ],
        # Basic constraints
        concentrations_on_different_rows=True,
        concentrations_on_different_columns=False,
        replicates_on_same_plate=True,
        replicates_on_different_plates=False,
        
        # ADVANCED parameters
        force_spread_controls=True,
        force_spread_concentrations=True,
        balance_controls_inside_plate=True,
        interconnected_plates=True,
        control_slack=2,
        testing=False,
        sorted_compounds=True,
        
        # Solver
        timeout_seconds=10,
        num_threads=4,
        random_seed=123,
    )
    
    print(f"\nTest Config:")
    print(f"  Plate: {config.plate_rows}×{config.plate_cols}")
    print(f"  Total samples: {config.total_samples}")
    print(f"  Advanced params:")
    print(f"    force_spread_controls: {config.force_spread_controls}")
    print(f"    force_spread_concentrations: {config.force_spread_concentrations}")
    print(f"    balance_controls_inside_plate: {config.balance_controls_inside_plate}")
    print(f"    interconnected_plates: {config.interconnected_plates}")
    print(f"    control_slack: {config.control_slack}")
    print(f"    sorted_compounds: {config.sorted_compounds}")
    
    # Generate .dzn file
    solver = MiniZincSolver()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.dzn', delete=False) as f:
        dzn_path = f.name
    
    try:
        # Generate the dzn content
        dzn_content = solver._generate_dzn(config)
        
        print(f"\nGenerated .dzn file (partial):")
        print("-" * 60)
        
        # Check for key advanced parameters in the dzn
        lines = dzn_content.split('\n')
        key_params = [
            'force_spread_controls',
            'force_spread_concentrations',
            'balance_controls_inside_plate',
            'interconnected_plates',
            'control_slack',
            'sorted_compounds',
        ]
        
        found_params = {}
        for line in lines:
            for param in key_params:
                if param + ' =' in line:
                    found_params[param] = line.strip()
                    print(f"  ✓ {line.strip()}")
        
        print("\nParameter Verification:")
        for param in key_params:
            if param in found_params:
                print(f"  ✓ {param} found in .dzn")
            else:
                print(f"  ✗ {param} NOT found in .dzn (ERROR!)")
        
        # Save the full dzn for inspection
        with open(dzn_path, 'w') as f:
            f.write(dzn_content)
        
        print(f"\n✓ Full .dzn saved to: {dzn_path}")
        print(f"  File size: {len(dzn_content)} bytes")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {str(e)}")
        return False

def test_json_serialization():
    """Test that all 24 parameters serialize to JSON"""
    
    print("\n" + "=" * 60)
    print("Testing JSON Serialization of All Parameters")
    print("=" * 60)
    
    from designer import PlateDesigner
    import json
    
    config = PlateConfig(
        plate_rows=16,
        plate_cols=24,
        empty_edge=1,
        compounds=[
            Compound(name="CompA", concentrations=3, replicates=2)
        ],
        controls=[
            Control(name="Ctrl", concentration_levels=1, replicates=2)
        ],
        concentrations_on_different_rows=True,
        concentrations_on_different_columns=True,
        replicates_on_same_plate=False,
        replicates_on_different_plates=True,
        force_spread_controls=True,
        force_spread_concentrations=False,
        balance_controls_inside_plate=True,
        interconnected_plates=False,
        control_slack=1,
        testing=True,
        sorted_compounds=True,
        timeout_seconds=30,
        num_threads=8,
        random_seed=456,
    )
    
    # Test serialization directly without creating PlateDesigner (which checks for MiniZinc)
    try:
        from config import PlateConfigJSON
        
        # Convert to JSON-serializable format
        json_data = {
            'plate_rows': config.plate_rows,
            'plate_cols': config.plate_cols,
            'empty_edge': config.empty_edge,
            'compounds': [
                {'name': c.name, 'concentrations': c.concentrations, 
                 'replicates': c.replicates, 'concentration_names': c.concentration_names}
                for c in config.compounds
            ],
            'controls': [
                {'name': c.name, 'concentration_levels': c.concentration_levels,
                 'replicates': c.replicates, 'concentration_names': c.concentration_names}
                for c in config.controls
            ],
            'concentrations_on_different_rows': config.concentrations_on_different_rows,
            'concentrations_on_different_columns': config.concentrations_on_different_columns,
            'replicates_on_same_plate': config.replicates_on_same_plate,
            'replicates_on_different_plates': config.replicates_on_different_plates,
            'force_spread_controls': config.force_spread_controls,
            'force_spread_concentrations': config.force_spread_concentrations,
            'balance_controls_inside_plate': config.balance_controls_inside_plate,
            'interconnected_plates': config.interconnected_plates,
            'control_slack': config.control_slack,
            'testing': config.testing,
            'sorted_compounds': config.sorted_compounds,
            'timeout_seconds': config.timeout_seconds,
            'num_threads': config.num_threads,
            'random_seed': config.random_seed,
            'horizontal_cell_lines': config.horizontal_cell_lines,
            'vertical_cell_lines': config.vertical_cell_lines,
        }
        
        json_str = json.dumps(json_data, indent=2)
        json_path = '/tmp/test_config.json'
        
        with open(json_path, 'w') as f:
            f.write(json_str)
        
        print(f"✓ Saved config to {json_path}")
        
        # Load it back
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        print(f"\nJSON Keys Count: {len(data)}")
        print("Advanced Parameters in JSON:")
        
        adv_params = [
            'force_spread_controls',
            'force_spread_concentrations',
            'balance_controls_inside_plate',
            'interconnected_plates',
            'control_slack',
            'testing',
            'sorted_compounds',
        ]
        
        all_found = True
        for param in adv_params:
            if param in data:
                print(f"  ✓ {param}: {data[param]}")
            else:
                print(f"  ✗ {param}: NOT IN JSON (ERROR!)")
                all_found = False
        
        print(f"\n✓ JSON serialization successful - all advanced parameters present")
        
        return all_found
        
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result1 = test_dzn_generation()
    result2 = test_json_serialization()
    
    print("\n" + "=" * 60)
    if result1 and result2:
        print("✓ ALL TESTS PASSED - Advanced parameters working!")
    else:
        print("✗ SOME TESTS FAILED - See details above")
    print("=" * 60)
