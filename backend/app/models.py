from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "running", "completed", "failed"]


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