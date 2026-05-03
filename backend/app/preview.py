from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import pandas as pd

from src.iplaid.loaders import load_layout_csv, normalize_layout_df
from src.iplaid.wells import canonical_well_name


WELL_PATTERN = re.compile(r"^([A-Za-z]+)(\d+)$")
LIQUID_NAME_PATTERN = re.compile(r"^\[(.*?)\]\[(.*?)\]$")


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


def validate_source_layout_upload(file_name: str, file_bytes: bytes) -> dict:
    """
    Schema-level validation for a source-plate-layout CSV upload.

    Checks the structural shape of the file (parseable, required columns
    present, Liquid Name in `[Compound][Stock]` format with a numeric stock,
    Source Well in `<letters><digits>` format, no blanks, no duplicates).

    Geometry checks against the selected source plate (does well exist on
    the plate?) and completeness checks against the run's layout/meta (are
    all required liquids present?) intentionally happen later, at run time
    in `output.py`, since those need context this endpoint doesn't have.
    """
    suffix = Path(file_name).suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(file_bytes)
        temp_path = Path(handle.name)

    try:
        try:
            df = pd.read_csv(temp_path)
        except Exception as exc:
            raise ValueError(f"Could not parse CSV: {exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    required = ["Liquid Name", "Source Well"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            "Source plate layout CSV is missing required column(s): "
            f"{missing}. Expected: 'Liquid Name', 'Source Well' "
            "(and optionally 'Source Plate')."
        )

    if len(df) == 0:
        raise ValueError("Source plate layout CSV has no data rows.")

    columns_to_check = list(required)
    if "Source Plate" in df.columns:
        columns_to_check.append("Source Plate")
    for column in columns_to_check:
        stripped = df[column].astype(str).str.strip()
        if df[column].isna().any() or (stripped == "").any():
            raise ValueError(
                f"Source plate layout has blank values in column '{column}'."
            )

    bad_format: list[str] = []
    bad_concentration: list[str] = []
    for raw in df["Liquid Name"].astype(str).str.strip():
        match = LIQUID_NAME_PATTERN.match(raw)
        if not match:
            bad_format.append(raw)
            continue
        try:
            float(match.group(2))
        except ValueError:
            bad_concentration.append(raw)
    if bad_format:
        raise ValueError(
            "Source plate layout has Liquid Name(s) not in the expected "
            f"'[Compound][Stock]' format: {bad_format[:5]}"
        )
    if bad_concentration:
        raise ValueError(
            "Source plate layout has Liquid Name(s) with a non-numeric "
            f"stock concentration: {bad_concentration[:5]}"
        )

    bad_wells = [
        raw for raw in df["Source Well"].astype(str).str.strip()
        if not WELL_PATTERN.match(raw)
    ]
    if bad_wells:
        raise ValueError(
            f"Source plate layout has invalid Source Well value(s): {bad_wells[:5]}"
        )

    liquid_names = df["Liquid Name"].astype(str).str.strip()
    if liquid_names.duplicated().any():
        dups = liquid_names[liquid_names.duplicated(keep=False)].unique().tolist()
        raise ValueError(
            f"Source plate layout has duplicate Liquid Name(s): {dups[:5]}"
        )

    plate_keys = (
        df["Source Plate"].astype(str).str.strip()
        if "Source Plate" in df.columns
        else pd.Series([""] * len(df), index=df.index)
    )
    well_keys = df["Source Well"].astype(str).str.strip().str.upper()
    pairs = pd.DataFrame({"plate": plate_keys, "well": well_keys})
    if pairs.duplicated().any():
        dup_rows = pairs[pairs.duplicated(keep=False)].drop_duplicates()
        pretty = [
            f"{row['plate'] or '<default>'}:{row['well']}"
            for _, row in dup_rows.iterrows()
        ]
        raise ValueError(
            f"Source plate layout has duplicate Source Well(s): {pretty[:5]}"
        )

    columns_present = [
        col for col in ("Liquid Name", "Source Well", "Source Plate")
        if col in df.columns
    ]
    return {
        "rowCount": int(len(df)),
        "columns": columns_present,
        "sampleLiquidNames": liquid_names.head(5).tolist(),
    }
