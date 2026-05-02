"""Dispenser strategy interface.

Each dispenser implements this Protocol. The pipeline uses get_dispenser(cfg["dispenser"])
to dispatch dispenser-specific build/write/validate work.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd


class UnknownDispenserError(ValueError):
    """Raised when cfg['dispenser'] does not match a registered dispenser."""


class SourceLayoutError(ValueError):
    """Raised when a user-supplied source-plate layout is invalid or incomplete."""


@dataclass(frozen=True)
class DispenserSpec:
    """Static metadata for a dispenser. Loaded from the registry."""
    name: str
    display_name: str
    plate_specs_path: str  # relative to <project_root>/data/
    min_increment_nL: float  # 0 means no rounding (iDOT); 2.5 for Echo
    default_sourceplate_type: str
    default_target_plate_type: str


@runtime_checkable
class Dispenser(Protocol):
    spec: DispenserSpec

    def load_plate_specs(self, project_root: Path) -> dict: ...

    def build_protocol(
        self,
        all_rows: pd.DataFrame,
        liquid_table: pd.DataFrame,
        *,
        cfg: dict,
        source_specs: dict,
    ) -> pd.DataFrame: ...

    def write_protocol(self, protocol_df: pd.DataFrame, out_path: Path) -> None: ...

    def write_liquids(self, liquid_table_export: pd.DataFrame, out_path: Path) -> None: ...

    def validate_export(
        self,
        out_path: Path,
        *,
        protocol_name: str,
        user_name: str,
    ) -> tuple[pd.DataFrame, int]: ...
