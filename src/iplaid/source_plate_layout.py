from __future__ import annotations
from dataclasses import dataclass, field
from typing import NamedTuple


class RowState(NamedTuple):
    owner_compound: str
    owner_stock_count: int
    next_free_col: int  # 1-based; the next unfilled column in this row


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

    scatter_warnings: list[ScatterWarning] = []
    row_state: dict[int, RowState] = {}

    # Phase A: first geometry.rows compounds each claim a fresh row.
    phase_a = sorted_compounds[: geometry.rows]
    phase_b = sorted_compounds[geometry.rows :]

    for row_idx_0, cmpd in enumerate(phase_a):
        row_idx = row_idx_0 + 1
        for col_offset, stock in enumerate(sorted(cmpd.stocks_mM)):
            placements[f"[{cmpd.name}][{stock}]"] = f"{_row_label(row_idx)}{col_offset + 1}"
        row_state[row_idx] = RowState(
            owner_compound=cmpd.name,
            owner_stock_count=len(cmpd.stocks_mM),
            next_free_col=len(cmpd.stocks_mM) + 1,
        )

    # Phase B: pack overflow.
    for cmpd in phase_b:
        n_needed = len(cmpd.stocks_mM)

        # Candidates: rows with ≥ n_needed trailing free cols.
        candidates = [
            r for r in row_state
            if (geometry.cols - row_state[r].next_free_col + 1) >= n_needed
        ]
        if not candidates:
            # Tier 2: scatter into row-major free wells (only Phase A rows have free wells).
            free_wells = _enumerate_free_wells(geometry, row_state, reserved_wells=set())
            if len(free_wells) < n_needed:
                # Tier 3 handled in next task.
                raise NotImplementedError("Tier 3 exclusion not yet implemented")
            chosen_wells = tuple(free_wells[:n_needed])
            for well, stock in zip(chosen_wells, sorted(cmpd.stocks_mM)):
                placements[f"[{cmpd.name}][{stock}]"] = well
            _consume_scattered_wells(row_state, chosen_wells, geometry)
            scatter_warnings.append(ScatterWarning(compound=cmpd.name, wells=chosen_wells))
            continue

        # Preferred: candidates whose owner has the same stock count.
        preferred = [r for r in candidates if row_state[r].owner_stock_count == n_needed]
        pool = preferred if preferred else candidates

        # T2 spread: pick the row with the most free space; tiebreak smallest row index.
        def free_in_row(r: int) -> int:
            return geometry.cols - row_state[r].next_free_col + 1

        chosen = max(pool, key=lambda r: (free_in_row(r), -r))

        start_col = row_state[chosen].next_free_col
        for col_offset, stock in enumerate(sorted(cmpd.stocks_mM)):
            placements[f"[{cmpd.name}][{stock}]"] = f"{_row_label(chosen)}{start_col + col_offset}"
        row_state[chosen] = row_state[chosen]._replace(next_free_col=start_col + n_needed)

    return AssignmentResult(placements=placements, scatter_warnings=scatter_warnings)


def _enumerate_free_wells(
    geometry: PlateGeometry,
    row_state: dict[int, RowState],
    *,
    reserved_wells: set[str],
) -> list[str]:
    """Return free wells in row-major order (top-to-bottom, left-to-right).

    Phase A rows: free wells start at `next_free_col`. Unclaimed rows (not in
    row_state): all cols are free. Reserved wells excluded.
    """
    free: list[str] = []
    for row_idx in range(1, geometry.rows + 1):
        label = _row_label(row_idx)
        start_col = row_state[row_idx].next_free_col if row_idx in row_state else 1
        for col in range(start_col, geometry.cols + 1):
            well = f"{label}{col}"
            if well not in reserved_wells:
                free.append(well)
    return free


def _parse_well(well: str) -> tuple[int, int]:
    """Parse a well address like 'AA10' into (row_idx_1based, col_1based)."""
    i = 0
    while i < len(well) and well[i].isalpha():
        i += 1
    row_label_str, col_str = well[:i], well[i:]
    row_idx = 0
    for ch in row_label_str:
        row_idx = row_idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return row_idx, int(col_str)


def _consume_scattered_wells(
    row_state: dict[int, RowState],
    wells: tuple[str, ...],
    geometry: PlateGeometry,
) -> None:
    """Advance `next_free_col` past consumed wells. Updates row_state in place.

    Wells are consumed in row-major order; for each row touched, advance the
    next-free pointer to one past the rightmost well consumed in that row.
    """
    last_col_per_row: dict[int, int] = {}
    for well in wells:
        row_idx, col = _parse_well(well)
        last_col_per_row[row_idx] = max(last_col_per_row.get(row_idx, 0), col)

    for row_idx, last_col in last_col_per_row.items():
        if row_idx in row_state:
            row_state[row_idx] = row_state[row_idx]._replace(next_free_col=last_col + 1)
        else:
            row_state[row_idx] = RowState(
                owner_compound="__scatter__",
                owner_stock_count=0,
                next_free_col=last_col + 1,
            )
