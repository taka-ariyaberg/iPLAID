from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


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


class SolventDef(BaseModel):
    """One solvent entry for the plate designer."""
    name: str
    replicates: int = Field(default=3, ge=1)


class DesignConfigModel(BaseModel):
    """Full configuration sent to the PLAID_Core solver."""
    # Plate geometry
    plate_rows: int = Field(default=16, ge=4)
    plate_cols: int = Field(default=24, ge=4)
    empty_edge: int = Field(default=1, ge=0)
    # Compounds & solvents
    compounds: List[CompoundDef] = Field(default_factory=list)
    solvents: List[SolventDef] = Field(default_factory=list)
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
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    num_threads: int = Field(default=8, ge=1, le=64)
    random_seed: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_solvents(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        raw_solvents = data.get("solvents")
        if raw_solvents is None and "controls" in data:
            raw_solvents = data.get("controls")

        if raw_solvents is None:
            return data

        normalized_solvents: list[dict[str, Any]] = []
        for item in raw_solvents or []:
            if isinstance(item, SolventDef):
                normalized_solvents.append(item.model_dump())
                continue
            if not isinstance(item, dict):
                normalized_solvents.append({"name": "", "replicates": 3})
                continue

            replicates = item.get("replicates")
            if replicates is None:
                entries = item.get("conc_entries") or []
                non_zero_entries = [
                    entry
                    for entry in entries
                    if isinstance(entry, dict) and float(entry.get("value_um", 0) or 0) != 0
                ]
                if non_zero_entries:
                    raise ValueError(
                        "Legacy design controls with explicit concentrations can no longer be "
                        "auto-converted to solvents. Recreate them as compounds with real "
                        "concentrations, and use solvents only for vehicle-only wells."
                    )
                replicates = sum(
                    int(entry.get("replicates", 0))
                    for entry in entries
                    if isinstance(entry, dict)
                ) or 3

            normalized_solvents.append({
                "name": item.get("name", ""),
                "replicates": replicates,
            })

        normalized = dict(data)
        normalized["solvents"] = normalized_solvents
        normalized.pop("controls", None)
        return normalized


class RunConfigModel(BaseModel):
    user_name: str = Field(default="YourName")
    protocol_name: str = Field(default="PLAID_RUN")
    layout_file: str = Field(default="layout.csv")
    meta_file: str = Field(default="meta.csv")
    sourceplate_type: str = Field(default="S.100 Plate")
    target_plate_type: str = Field(default="MWP 384")
    working_volume_ul: float = Field(default=40.0, gt=0)
    max_dmso_pct: float = Field(default=0.1, gt=0)
    solvent_caps_pct: Optional[Dict[str, float]] = None
    source_prep_overage_pct: float = Field(default=0.30, ge=0)
    min_pipette_volume_uL: float = Field(default=1.0, ge=0)
    dilution_solvent: str = Field(default="DMSO")
    source_well_fill_pct: float = Field(default=0.70, gt=0)
    standard_prep_volume_uL: float = Field(default=1000.0, gt=0)
    output_timestamp_format: str = Field(default="%y-%m-%d-%H-%M-%S")
