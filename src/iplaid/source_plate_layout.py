from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompoundSpec:
    name: str
    stocks_mM: tuple[float, ...]


@dataclass(frozen=True)
class PlateGeometry:
    rows: int
    cols: int


@dataclass(frozen=True)
class ScatterWarning:
    compound: str
    wells: tuple[str, ...]


@dataclass(frozen=True)
class ExclusionWarning:
    compound: str
    stocks_needed: int
    free_wells_remaining: int


@dataclass
class AssignmentResult:
    placements: dict[str, str]  # Liquid Name → well address (e.g. "A1")
    excluded: list[ExclusionWarning] = field(default_factory=list)
    scatter_warnings: list[ScatterWarning] = field(default_factory=list)


def _row_label(row_idx_1based: int) -> str:
    """Convert 1-based row index to letter label. 1 -> 'A', 26 -> 'Z', 27 -> 'AA'."""
    label = ""
    n = row_idx_1based
    while n > 0:
        n, rem = divmod(n - 1, 26)
        label = chr(ord("A") + rem) + label
    return label


def assign_source_wells(
    compounds: list[CompoundSpec],
    solvents: list[str],
    geometry: PlateGeometry,
) -> AssignmentResult:
    # Minimal: place every compound's stocks starting at A1 row-major.
    # Will be replaced in subsequent tasks.
    placements: dict[str, str] = {}
    for cmpd in compounds:
        for i, stock in enumerate(sorted(cmpd.stocks_mM)):
            liquid_name = f"[{cmpd.name}][{stock}]"
            placements[liquid_name] = f"{_row_label(1)}{i + 1}"
    return AssignmentResult(placements=placements)
