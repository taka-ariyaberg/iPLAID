from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "running", "completed", "failed"]


# ---------------------------------------------------------------------------
# Design (PLAID_Core) models
# ---------------------------------------------------------------------------

class ConcEntry(BaseModel):
    """One concentration entry: a µM value and its replicate count."""
    value_um: float = Field(default=0.0, ge=0)
    replicates: int = Field(default=3, ge=1)


class CompoundDef(BaseModel):
    """One compound entry for the plate designer."""
    name: str
    conc_entries: List[ConcEntry] = Field(default_factory=list)


class ControlDef(BaseModel):
    """One control entry for the plate designer."""
    name: str
    conc_entries: List[ConcEntry] = Field(default_factory=list)


class DesignConfigModel(BaseModel):
    """Full configuration sent to the PLAID_Core solver."""
    # Plate geometry
    plate_rows: int = Field(default=16, ge=4)
    plate_cols: int = Field(default=24, ge=4)
    empty_edge: int = Field(default=1, ge=0)
    # Compounds & controls
    compounds: List[CompoundDef] = Field(default_factory=list)
    controls: List[ControlDef] = Field(default_factory=list)
    # Distribution constraints
    concentrations_on_different_rows: bool = True
    concentrations_on_different_columns: bool = True
    replicates_on_same_plate: bool = True
    replicates_on_different_plates: bool = False
    allow_empty_wells: bool = True
    # Control constraints
    balance_controls_inside_plate: bool = True
    interconnected_plates: bool = True
    control_slack: int = Field(default=0, ge=0)
    # Compound constraints
    force_spread_controls: bool = False
    force_spread_concentrations: bool = False
    # Cell lines
    horizontal_cell_lines: int = Field(default=1, ge=1)
    vertical_cell_lines: int = Field(default=1, ge=1)
    # Solver
    timeout_seconds: int = Field(default=30, ge=1)
    num_threads: int = Field(default=4, ge=1)
    random_seed: Optional[int] = None


class RunConfigModel(BaseModel):
    user_name: str = Field(default="YourName")
    protocol_name: str = Field(default="PLAID_RUN")
    layout_file: str = Field(default="layout.csv")
    meta_file: str = Field(default="meta.csv")
    sourceplate_type: str = Field(default="S.100 Plate")
    target_plate_type: str = Field(default="MWP 384")
    working_volume_ul: float = Field(default=40.0, gt=0)
    max_dmso_pct: float = Field(default=0.1, gt=0)
    source_prep_overage_pct: float = Field(default=0.30, ge=0)
    min_pipette_volume_uL: float = Field(default=1.0, ge=0)
    dilution_solvent: str = Field(default="DMSO")
    source_well_fill_pct: float = Field(default=0.70, gt=0)
    standard_prep_volume_uL: float = Field(default=1000.0, gt=0)
    output_timestamp_format: str = Field(default="%Y%m%d_%H%M%S")