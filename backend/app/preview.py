from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from src.iplaid.loaders import load_layout_csv, normalize_layout_df
from src.iplaid.wells import canonical_well_name


WELL_PATTERN = re.compile(r"^([A-Za-z]+)(\d+)$")


def _row_label_to_index(label: str) -> int:
    value = 0
    for char in label.upper():
        value = value * 26 + (ord(char) - 64)
    return value - 1


def _parse_well(well: str) -> tuple[str, int]:
    match = WELL_PATTERN.match(str(well).strip())
    if not match:
        return "?", 0
    return match.group(1).upper(), int(match.group(2))


def _normalize_number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_layout_preview_from_dataframe(df) -> dict:
    plates: dict[str, dict] = {}
    compound_counts: dict[str, int] = {}
    concentrations: list[float] = []

    for row in df.itertuples(index=False):
        plate_id = str(getattr(row, "plateID", "plate_1"))
        well = canonical_well_name(str(getattr(row, "well", "")))
        compound = str(getattr(row, "cmpdname", "Unknown")).strip()
        concentration = _normalize_number(getattr(row, "CONCuM", None))
        explicit_is_control = getattr(row, "is_solvent_control", None)
        row_label, column_number = _parse_well(well)

        plate = plates.setdefault(
            plate_id,
            {
                "plateId": plate_id,
                "rowLabels": set(),
                "columnLabels": set(),
                "wells": [],
            },
        )
        plate["rowLabels"].add(row_label)
        plate["columnLabels"].add(column_number)
        plate["wells"].append(
            {
                "well": well,
                "rowLabel": row_label,
                "column": column_number,
                "compound": compound,
                "concentration": concentration,
                "isControl": (
                    bool(explicit_is_control)
                    if explicit_is_control is not None
                    else (concentration == 0 if concentration is not None else compound.upper() == "DMSO")
                ),
            }
        )

        compound_counts[compound] = compound_counts.get(compound, 0) + 1
        if concentration is not None:
            concentrations.append(concentration)

    rendered_plates = []
    for plate_id, plate in sorted(plates.items()):
        row_labels = sorted(plate["rowLabels"], key=_row_label_to_index)
        column_labels = sorted(plate["columnLabels"])
        wells = sorted(
            plate["wells"],
            key=lambda well_info: (_row_label_to_index(well_info["rowLabel"]), well_info["column"]),
        )
        rendered_plates.append(
            {
                "plateId": plate_id,
                "rowLabels": row_labels,
                "columnLabels": column_labels,
                "wells": wells,
            }
        )

    compound_summary = [
        {"name": name, "count": count}
        for name, count in sorted(compound_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    concentration_summary = {
        "min": min(concentrations) if concentrations else None,
        "max": max(concentrations) if concentrations else None,
    }

    return {
        "plates": rendered_plates,
        "compoundSummary": compound_summary,
        "plateCount": len(rendered_plates),
        "wellCount": sum(len(plate["wells"]) for plate in rendered_plates),
        "concentrationSummary": concentration_summary,
    }


def build_layout_preview_from_path(layout_path: Path) -> dict:
    df = load_layout_csv(layout_path)
    normalized_df, _ = normalize_layout_df(df)
    return build_layout_preview_from_dataframe(normalized_df)


def build_layout_preview_from_upload(file_name: str, file_bytes: bytes) -> dict:
    suffix = Path(file_name).suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(file_bytes)
        temp_path = Path(handle.name)

    try:
        return build_layout_preview_from_path(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def dataframe_to_records(df, limit: int | None = None) -> list[dict]:
    if limit is not None:
        df = df.head(limit)
    return json.loads(df.to_json(orient="records"))
