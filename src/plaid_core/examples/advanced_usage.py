"""
Advanced Usage Example

Demonstrates advanced features:
- Loading configuration from JSON
- Multiple control types
- 384-well plate
- Replicates on different plates
- Custom timeout and threading
"""

from plaid_core import PlateDesigner, PlateConfig, Compound, Control


def main():
    print("=" * 60)
    print("PLAID_Core: Advanced Usage Example")
    print("=" * 60)
    
    # Define compounds with custom concentration names
    compounds = [
        Compound(
            name="Drug_X",
            concentrations=5,
            replicates=4,
            concentration_names=["0.1uM", "1uM", "10uM", "100uM", "1000uM"]
        ),
        Compound(
            name="Drug_Y",
            concentrations=5,
            replicates=4,
            concentration_names=["0.1uM", "1uM", "10uM", "100uM", "1000uM"]
        ),
        Compound(
            name="Drug_Z",
            concentrations=5,
            replicates=4,
            concentration_names=["0.1uM", "1uM", "10uM", "100uM", "1000uM"]
        ),
    ]
    
    # Multiple control types
    controls = [
        Control(
            name="Positive_Control",
            concentration_levels=1,
            replicates=6,
            concentration_names=["Max_effect"]
        ),
        Control(
            name="Negative_Control",
            concentration_levels=1,
            replicates=6,
            concentration_names=["No_effect"]
        ),
        Control(
            name="DMSO",
            concentration_levels=1,
            replicates=4,
            concentration_names=["Solvent_only"]
        ),
    ]
    
    # Create advanced configuration (384-well plate)
    config = PlateConfig(
        # Plate geometry
        plate_rows=16,
        plate_cols=24,
        empty_edge=1,
        compounds=compounds,
        controls=controls,
        
        # Basic spacing constraints - ensure good distribution
        concentrations_on_different_rows=True,
        concentrations_on_different_columns=True,
        
        # Replication strategy - spread across multiple plates if needed
        replicates_on_same_plate=False,
        replicates_on_different_plates=True,
        
        # ADVANCED: Control spreading constraints
        force_spread_controls=True,        # Force controls to spread across plate
        force_spread_concentrations=True,  # Force concentration levels to spread
        balance_controls_inside_plate=True,  # Keep control types balanced within plate
        
        # ADVANCED: Plate interconnection
        interconnected_plates=False,       # Set True to use shared constraints across plates
        control_slack=1,                   # Flexibility in control placement (wells)
        
        # ADVANCED: Testing & sorting
        testing=False,                     # Set True to run MiniZinc in test mode
        sorted_compounds=True,            # Prefer sorted output (helps with reproducibility)
        
        # Solver parameters - tuned for complex 384-well designs
        timeout_seconds=60,                # Increase for larger/complex designs
        num_threads=8,
        random_seed=42,  # For reproducibility
    )
    
    print(f"\nAdvanced Configuration:")
    print(f"  Plate: {config.plate_name} ({config.plate_rows}×{config.plate_cols})")
    print(f"  Usable wells: {config.usable_wells_per_plate}")
    print(f"  Compounds: {len(compounds)} (5 conc × 4 reps each)")
    print(f"  Controls: {len(controls)} types")
    print(f"  Total samples: {config.total_samples}")
    print(f"\n  Basic Constraints:")
    print(f"    Replicates mode: Different plates (allows scaling)")
    print(f"    Concentrations on different rows: {config.concentrations_on_different_rows}")
    print(f"    Concentrations on different columns: {config.concentrations_on_different_columns}")
    print(f"\n  Advanced Controls:")
    print(f"    Force spread controls: {config.force_spread_controls}")
    print(f"    Force spread concentrations: {config.force_spread_concentrations}")
    print(f"    Balance controls inside plate: {config.balance_controls_inside_plate}")
    print(f"    Interconnected plates: {config.interconnected_plates}")
    print(f"    Control slack: {config.control_slack}")
    print(f"\n  Solver Settings:")
    print(f"    Timeout: {config.timeout_seconds}s")
    print(f"    Threads: {config.num_threads}")
    print(f"    Random seed: {config.random_seed}")
    print(f"    Testing mode: {config.testing}")
    print(f"    Sorted output: {config.sorted_compounds}")
    
    # Save configuration
    print(f"\nSaving configuration...")
    designer = PlateDesigner()
    designer.save_config_to_json(config, "advanced_design_config.json")
    print(f"✓ Saved: advanced_design_config.json")
    
    # Later: Load from JSON
    print(f"\nLoading configuration from JSON...")
    config_loaded = designer.load_config_from_json("advanced_design_config.json")
    print(f"✓ Loaded {len(config_loaded.compounds)} compounds, {len(config_loaded.controls)} controls")
    
    # Generate layout
    print(f"\nGenerating advanced layout (this may take longer)...")
    try:
        layout = designer.design(config_loaded)
        
        print(f"\n✓ Layout generated!")
        print(f"\n{layout.summary()}")
        
        # Save outputs
        csv_path = layout.save_csv("advanced_design_layout.csv")
        json_path = layout.save_json("advanced_design_layout.json")
        
        print(f"\n✓ Saved to:")
        print(f"  CSV:  {csv_path}")
        print(f"  JSON: {json_path}")
        
        # Analysis
        df = layout.to_dataframe()
        print(f"\nAnalysis:")
        print(f"  Total wells used: {len(df)}")
        for plate_id in layout.plate_ids:
            plate_df = df[df['plateID'] == plate_id]
            print(f"  {plate_id}: {len(plate_df)} wells")
        
        print(f"\nCompound distribution:")
        for comp_name in df['cmpdname'].unique():
            comp_df = df[df['cmpdname'] == comp_name]
            print(f"  {comp_name}: {len(comp_df)} wells ({comp_df['plateID'].nunique()} plates)")
    
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {str(e)}")
        print(f"  Try reducing replicates or adjusting timeout.")


if __name__ == "__main__":
    main()
