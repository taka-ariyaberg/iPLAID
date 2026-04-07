"""
Input validation utilities.
"""
# Support both package and direct imports
try:
    from .config import PlateConfig
    from .exceptions import ValidationError
except ImportError:
    from config import PlateConfig
    from exceptions import ValidationError


def validate_plate_config(config: PlateConfig) -> None:
    """
    Validate plate configuration for feasibility.
    
    Args:
        config: PlateConfig instance
        
    Raises:
        ValidationError: If configuration is invalid
    """
    # Basic checks already done in PlateConfig.__post_init__
    
    # Check if total samples fit
    total_samples = config.total_samples
    usable_wells = config.usable_wells_per_plate
    
    if total_samples == 0:
        raise ValidationError("Design has no compounds or controls")
    
    # Estimate number of plates needed (rough)
    # With spreading constraints, may need more than ceil(total/usable)
    estimated_plates_needed = (total_samples + usable_wells - 1) // usable_wells
    
    # Very rough feasibility check (with spreading, might need 2-3x more)
    if config.concentrations_on_different_rows and config.concentrations_on_different_columns:
        # Strict spreading significantly increases plate requirements
        max_plates_reasonable = estimated_plates_needed * 3
    else:
        max_plates_reasonable = estimated_plates_needed * 2
    
    # Warn if seems infeasible (but allow solver to try)
    if max_plates_reasonable > 10:
        raise ValidationError(
            f"Configuration may be too ambitious: {config.total_samples} samples, "
            f"{usable_wells} usable wells per plate, "
            f"estimated {estimated_plates_needed} plates minimum. "
            f"Consider reducing replicates/compounds or increasing plate size."
        )
    
    # Validate compounds
    if not config.compounds and not config.controls:
        raise ValidationError("Must specify at least one compound or control")
    
    for i, compound in enumerate(config.compounds):
        if compound.concentrations * compound.replicates > usable_wells:
            raise ValidationError(
                f"Compound '{compound.name}' alone needs "
                f"{compound.concentrations * compound.replicates} wells, "
                f"but only {usable_wells} usable wells available per plate"
            )
    
    # Validate controls
    for i, control in enumerate(config.controls):
        if control.concentration_levels * control.replicates > usable_wells:
            raise ValidationError(
                f"Control '{control.name}' alone needs "
                f"{control.concentration_levels * control.replicates} wells, "
                f"but only {usable_wells} usable wells available per plate"
            )
    
    # Check constraint compatibility
    if config.replicates_on_same_plate and config.replicates_on_different_plates:
        raise ValidationError(
            "Conflicting replicate placement constraints"
        )


def validate_minizinc_available() -> bool:
    """
    Check if MiniZinc is available in PATH or macOS app bundle.

    Returns:
        True if minizinc executable is found
    """
    import os
    import shutil
    if shutil.which("minizinc") is not None:
        return True
    # MiniZinc installed via the macOS IDE bundle
    macos_path = "/Applications/MiniZincIDE.app/Contents/Resources/minizinc"
    return os.path.isfile(macos_path)
