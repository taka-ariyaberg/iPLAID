from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import pandas as pd

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


REQUIRED_LAYOUT_COLUMNS = ["cmpdname", "conc_mM", "solvent", "source_plate", "source_well"]


def validate_source_layout_upload(file_name: str, file_bytes: bytes) -> dict:
    """
    Schema-level validation for the new-format Source plate layout CSV upload.

    Required columns: cmpdname, conc_mM, solvent, source_plate, source_well.
    Geometry checks against the selected source plate (does well exist on
    the plate?) intentionally happen later in `output.py`.
    """
    suffix = Path(file_name).suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(file_bytes)
        temp_path = Path(handle.name)

    try:
        if b"\x00" in file_bytes:
            raise ValueError("Could not parse CSV: file contains null bytes (not a text CSV).")
        try:
            df = pd.read_csv(temp_path)
        except Exception as exc:
            raise ValueError(f"Could not parse CSV: {exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    missing = [col for col in REQUIRED_LAYOUT_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            "Source plate layout CSV is missing required column(s): "
            f"{missing}. Required: {REQUIRED_LAYOUT_COLUMNS}."
        )

    if len(df) == 0:
        raise ValueError("Source plate layout CSV has no data rows.")

    for col in REQUIRED_LAYOUT_COLUMNS:
        stripped = df[col].astype(str).str.strip()
        blank_mask = df[col].isna() | stripped.eq("")
        if blank_mask.any():
            row_idx = int(blank_mask.idxmax()) + 1  # 1-based, header excluded
            raise ValueError(
                f"Row {row_idx}: blank value in column '{col}'."
            )

    # Numeric conc_mM
    for idx, raw in enumerate(df["conc_mM"], start=1):
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Row {idx}: non-numeric conc_mM value {raw!r}."
            ) from exc
        if value < 0:
            raise ValueError(
                f"Row {idx}: conc_mM must be >= 0, got {value}."
            )

    # Well address shape
    for idx, raw in enumerate(df["source_well"].astype(str).str.strip(), start=1):
        if not WELL_PATTERN.match(raw):
            raise ValueError(
                f"Row {idx}: invalid source_well value {raw!r} "
                "(expected letters followed by digits, e.g. 'A1')."
            )

    # Solvent-control rule: cmpdname == solvent (case/whitespace-normalized)
    # => conc_mM == 0; otherwise conc_mM > 0.
    cmpd_keys = df["cmpdname"].astype(str).str.strip().str.lower()
    solv_keys = df["solvent"].astype(str).str.strip().str.lower()
    conc_vals = df["conc_mM"].astype(float)
    is_ctrl = cmpd_keys.eq(solv_keys)
    bad_ctrl = is_ctrl & (conc_vals != 0)
    bad_compound = (~is_ctrl) & (conc_vals <= 0)
    if bad_ctrl.any():
        idx = int(bad_ctrl.idxmax()) + 1
        raise ValueError(
            f"Row {idx}: solvent-control row (cmpdname == solvent) must have conc_mM == 0."
        )
    if bad_compound.any():
        idx = int(bad_compound.idxmax()) + 1
        raise ValueError(
            f"Row {idx}: compound rows must have conc_mM > 0."
        )

    # Solvent consistency per compound
    cmpd_groups = df.groupby(cmpd_keys)
    for key, group in cmpd_groups:
        unique_solvents = sorted(set(group["solvent"].astype(str).str.strip()))
        if len(unique_solvents) > 1:
            display = group["cmpdname"].iloc[0]
            raise ValueError(
                f"Inconsistent solvent for cmpdname '{display}': "
                + " vs ".join(repr(s) for s in unique_solvents)
            )

    # Duplicate (source_plate, source_well)
    plate_keys = df["source_plate"].astype(str).str.strip()
    well_keys = df["source_well"].astype(str).str.strip().str.upper()
    pairs = pd.DataFrame({"plate": plate_keys, "well": well_keys})
    dup_mask = pairs.duplicated(keep=False)
    if dup_mask.any():
        first_idx = int(dup_mask.idxmax()) + 1
        well = pairs.iloc[int(dup_mask.idxmax())]["well"]
        raise ValueError(
            f"Row {first_idx}: Duplicate source_well '{well}' for source_plate "
            f"'{pairs.iloc[int(dup_mask.idxmax())]['plate']}'."
        )

    return {
        "rowCount": int(len(df)),
        "columns": REQUIRED_LAYOUT_COLUMNS,
        "sampleCompounds": df["cmpdname"].astype(str).str.strip().head(5).tolist(),
    }
