from __future__ import annotations

import re


WELL_PATTERN = re.compile(r"^([A-Za-z]+)0*(\d+)$")


def compact_well_name(well_name: str) -> str:
    """
    Convert a well name to its compact form (for example, ``B02`` -> ``B2``).
    """
    text = str(well_name).strip()
    match = WELL_PATTERN.match(text)
    if not match:
        return text

    row_label = match.group(1).upper()
    column = int(match.group(2))
    return f"{row_label}{column}"


def canonical_well_name(well_name: str, *, min_digits: int = 2) -> str:
    """
    Convert a well name to its canonical padded form (for example, ``B2`` -> ``B02``).
    """
    text = str(well_name).strip()
    match = WELL_PATTERN.match(text)
    if not match:
        return text

    row_label = match.group(1).upper()
    column = int(match.group(2))
    width = max(min_digits, len(str(column)))
    return f"{row_label}{column:0{width}d}"
