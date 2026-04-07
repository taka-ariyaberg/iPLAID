"""
Basic Usage Example

Simple microplate design with 4 compounds and 1 control on a 96-well plate.
"""

from plaid_core import PlateDesigner, PlateConfig, Compound, Control


def main():
    print("=" * 60)
    print("PLAID_Core: Basic Usage Example")
    print("=" * 60)
    
    # Define compounds
    compounds = [
        Compound(
            name="Compound_A",
            concentrations=3,
            replicates=3,
            concentration_names=["Low", "Medium", "High"]
        ),
        Compound(
            name="Compound_B",
            concentrations=3,
            replicates=3,
            concentration_names=["Low", "Medium", "High"]
        ),
        Compound(
            name="Compound_C",
            concentrations=3,
            replicates=3,
            concentration_names=["Low", "Medium", "High"]
        ),
        Compound(
            name="Compound_D",
            concentrations=3,
            replicates=3,
            concentration_names=["Low", "Medium", "High"]
        ),
    ]
    
    # Define control
    controls = [
        Control(
            name="Positive_Control",
            concentration_levels=1,
            replicates=3,
            concentration_names=["100"]
        )
    ]
    
    # Create configuration
    config = PlateConfig(
        plate_rows=8,
        plate_cols=12,
        empty_edge=1,  # Exclude outer rows/columns
        compounds=compounds,
        controls=controls,
        concentrations_on_different_rows=True,
        concentrations_on_different_columns=True,
        replicates_on_same_plate=True,  # Keep replicates together
        timeout_seconds=10,
    )
    
    print(f"\nConfiguration:")
    print(f"  Plate: {config.plate_name} ({config.plate_rows}×{config.plate_cols})")
    print(f"  Usable wells: {config.usable_wells_per_plate}")
    print(f"  Compounds: {len(compounds)}")
    print(f"  Total samples: {config.total_samples}")
    print(f"  Timeout: {config.timeout_seconds}s")
    
    # Initialize designer
    print(f"\nInitializing designer...")
    designer = PlateDesigner()
    print(f"✓ MiniZinc ready")
    
    # Generate layout
    print(f"\nGenerating layout...")
    layout = designer.design(config)
    
    # Display results
    print(f"\n✓ Layout generated!")
    print(f"\n{layout.summary()}")
    
    # Save outputs
    csv_path = layout.save_csv("basic_design_layout.csv")
    json_path = layout.save_csv("basic_design_layout.json")
    
    print(f"\n✓ Saved to:")
    print(f"  CSV:  {csv_path}")
    print(f"  JSON: {json_path}")
    
    # Save configuration for reproducibility
    designer.save_config_to_json(config, "basic_design_config.json")
    print(f"  Config: basic_design_config.json")
    
    # Show sample of output
    print(f"\nFirst 5 wells:")
    print(layout.to_dataframe().head())


if __name__ == "__main__":
    main()
