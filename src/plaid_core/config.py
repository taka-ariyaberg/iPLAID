"""
Configuration classes for plate design parameters.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from pydantic import BaseModel, field_validator


@dataclass
class Compound:
    """Single compound specification."""
    name: str
    concentrations: int  # Number of concentration levels
    replicates: int      # Number of replicates per concentration
    concentration_names: Optional[List[str]] = None  # Custom names for each concentration

    def __post_init__(self):
        if self.concentrations < 1:
            raise ValueError("Concentrations must be >= 1")
        if self.replicates < 1:
            raise ValueError("Replicates must be >= 1")
        
        # Auto-generate concentration names if not provided
        if self.concentration_names is None:
            self.concentration_names = [f"Conc_{i+1}" for i in range(self.concentrations)]
        elif len(self.concentration_names) != self.concentrations:
            raise ValueError(f"Concentration names count ({len(self.concentration_names)}) must match concentrations ({self.concentrations})")


@dataclass
class Control:
    """Single control specification."""
    name: str
    concentration_levels: int  # Usually 1 for controls
    replicates: int            # Number of replicates
    concentration_names: Optional[List[str]] = None

    def __post_init__(self):
        if self.concentration_levels < 1:
            raise ValueError("Concentration levels must be >= 1")
        if self.replicates < 1:
            raise ValueError("Replicates must be >= 1")
        
        if self.concentration_names is None:
            self.concentration_names = [f"{self.name}_conc_{i+1}" for i in range(self.concentration_levels)]
        elif len(self.concentration_names) != self.concentration_levels:
            raise ValueError(f"Concentration names count must match concentration levels")


@dataclass
class PlateConfig:
    """Plate design configuration."""
    
    # Plate geometry
    plate_rows: int
    plate_cols: int
    empty_edge: int = 1  # Rows/cols to exclude from edges
    
    # Compounds and controls
    compounds: List[Compound] = field(default_factory=list)
    controls: List[Control] = field(default_factory=list)
    
    # Distribution constraints
    concentrations_on_different_rows: bool = True
    concentrations_on_different_columns: bool = True
    replicates_on_same_plate: bool = True  # All replicates stay together
    replicates_on_different_plates: bool = False  # If True, spread across plates
    
    # Optional constraints
    allow_empty_wells: bool = True
    
    # Advanced control constraints
    balance_controls_inside_plate: bool = True  # Balance controls within plates
    interconnected_plates: bool = True  # Connect plates for better global distribution
    control_slack: int = 0  # Slack for control distribution (higher = more flexible)
    
    # Advanced compound constraints
    force_spread_controls: bool = False  # Force spreading based on proven bounds
    force_spread_concentrations: bool = False  # Force concentration spreading
    
    # Cell lines (advanced)
    horizontal_cell_lines: int = 1
    vertical_cell_lines: int = 1
    
    # Solver parameters
    timeout_seconds: int = 10
    num_threads: int = 10
    random_seed: Optional[int] = None
    
    # Testing mode
    testing: bool = False  # Enable testing mode debug output
    sorted_compounds: Optional[bool] = None  # Optional sorting of compounds
    
    def __post_init__(self):
        """Validate configuration."""
        if self.plate_rows < 4:
            raise ValueError("Plate must have at least 4 rows")
        if self.plate_cols < 4:
            raise ValueError("Plate must have at least 4 columns")
        if self.empty_edge < 0:
            raise ValueError("Empty edge cannot be negative")
        if self.empty_edge * 2 >= self.plate_rows or self.empty_edge * 2 >= self.plate_cols:
            raise ValueError("Empty edge too large for plate dimensions")
        
        if self.replicates_on_same_plate and self.replicates_on_different_plates:
            raise ValueError("Cannot have replicates on both same and different plates")
        if not self.replicates_on_same_plate and not self.replicates_on_different_plates:
            raise ValueError("Must specify replicate placement (same or different plates)")
    
    @property
    def total_samples(self) -> int:
        """Calculate total sample wells needed."""
        compound_wells = sum(c.concentrations * c.replicates for c in self.compounds)
        control_wells = sum(c.concentration_levels * c.replicates for c in self.controls)
        return compound_wells + control_wells
    
    @property
    def usable_wells_per_plate(self) -> int:
        """Calculate available wells after edge removal."""
        usable_rows = self.plate_rows - (2 * self.empty_edge)
        usable_cols = self.plate_cols - (2 * self.empty_edge)
        return usable_rows * usable_cols
    
    @property
    def plate_name(self) -> str:
        """Human-readable plate format name."""
        total = self.plate_rows * self.plate_cols
        if total == 96:
            return "96-well"
        elif total == 384:
            return "384-well"
        elif total == 1536:
            return "1536-well"
        else:
            return f"{self.plate_rows}×{self.plate_cols}"


class PlateConfigJSON(BaseModel):
    """Pydantic model for JSON validation/serialization."""
    plate_rows: int
    plate_cols: int
    empty_edge: int = 1
    compounds: List[dict]  # [{"name": str, "concentrations": int, "replicates": int}, ...]
    controls: List[dict]
    concentrations_on_different_rows: bool = True
    concentrations_on_different_columns: bool = True
    replicates_on_same_plate: bool = True
    replicates_on_different_plates: bool = False
    allow_empty_wells: bool = True
    balance_controls_inside_plate: bool = True
    interconnected_plates: bool = True
    control_slack: int = 0
    force_spread_controls: bool = False
    force_spread_concentrations: bool = False
    horizontal_cell_lines: int = 1
    vertical_cell_lines: int = 1
    timeout_seconds: int = 10
    num_threads: int = 10
    random_seed: Optional[int] = None
    testing: bool = False
    sorted_compounds: Optional[bool] = None
    
    @field_validator('plate_rows', 'plate_cols')
    @classmethod
    def validate_plate_dims(cls, v):
        if v < 4:
            raise ValueError("Plate dimensions must be >= 4")
        return v
    
    def to_config(self) -> PlateConfig:
        """Convert JSON model to PlateConfig dataclass."""
        compounds = [Compound(**c) for c in self.compounds]
        controls = [Control(**c) for c in self.controls]
        
        return PlateConfig(
            plate_rows=self.plate_rows,
            plate_cols=self.plate_cols,
            empty_edge=self.empty_edge,
            compounds=compounds,
            controls=controls,
            concentrations_on_different_rows=self.concentrations_on_different_rows,
            concentrations_on_different_columns=self.concentrations_on_different_columns,
            replicates_on_same_plate=self.replicates_on_same_plate,
            replicates_on_different_plates=self.replicates_on_different_plates,
            allow_empty_wells=self.allow_empty_wells,
            balance_controls_inside_plate=self.balance_controls_inside_plate,
            interconnected_plates=self.interconnected_plates,
            control_slack=self.control_slack,
            force_spread_controls=self.force_spread_controls,
            force_spread_concentrations=self.force_spread_concentrations,
            horizontal_cell_lines=self.horizontal_cell_lines,
            vertical_cell_lines=self.vertical_cell_lines,
            timeout_seconds=self.timeout_seconds,
            num_threads=self.num_threads,
            random_seed=self.random_seed,
            testing=self.testing,
            sorted_compounds=self.sorted_compounds,
        )
