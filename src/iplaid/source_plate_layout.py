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
    placements: dict[str, str] = {}

    # Sort descending by # of stocks, alphabetical tiebreak.
    sorted_compounds = sorted(
        compounds,
        key=lambda c: (-len(c.stocks_mM), c.name),
    )

    # row_state[row_idx] = (owner_compound_name, owner_stock_count, next_free_col_1based)
    row_state: dict[int, tuple[str, int, int]] = {}

    # Phase A: first geometry.rows compounds each claim a fresh row.
    phase_a = sorted_compounds[: geometry.rows]
    phase_b = sorted_compounds[geometry.rows :]

    for row_idx_0, cmpd in enumerate(phase_a):
        row_idx = row_idx_0 + 1
        for col_offset, stock in enumerate(sorted(cmpd.stocks_mM)):
            placements[f"[{cmpd.name}][{stock}]"] = f"{_row_label(row_idx)}{col_offset + 1}"
        row_state[row_idx] = (cmpd.name, len(cmpd.stocks_mM), len(cmpd.stocks_mM) + 1)

    # Phase B: pack overflow.
    for cmpd in phase_b:
        n_needed = len(cmpd.stocks_mM)

        # Candidates: rows with ≥ n_needed trailing free cols.
        candidates = [
            row_idx for row_idx, (_, _, next_col) in row_state.items()
            if (geometry.cols - next_col + 1) >= n_needed
        ]
        if not candidates:
            # Tier 2 / Tier 3 handled in next tasks. For now, raise to keep behavior visible.
            raise NotImplementedError("Tier 2 scatter not yet implemented")

        # Preferred: candidates whose owner has the same stock count.
        preferred = [r for r in candidates if row_state[r][1] == n_needed]
        pool = preferred if preferred else candidates

        # T2 spread: pick the row with the most free space; tiebreak smallest row index.
        def free_in_row(r: int) -> int:
            return geometry.cols - row_state[r][2] + 1

        chosen = max(pool, key=lambda r: (free_in_row(r), -r))

        start_col = row_state[chosen][2]
        for col_offset, stock in enumerate(sorted(cmpd.stocks_mM)):
            placements[f"[{cmpd.name}][{stock}]"] = f"{_row_label(chosen)}{start_col + col_offset}"
        owner, owner_stocks, _ = row_state[chosen]
        row_state[chosen] = (owner, owner_stocks, start_col + n_needed)

    return AssignmentResult(placements=placements)
