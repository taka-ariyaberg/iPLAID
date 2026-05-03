from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Iterable, Sequence


DOWNLOAD_FILENAME_PREFIX = "iPLAID"
DEFAULT_DOWNLOAD_TIMESTAMP_FORMAT = "%y-%m-%d-%H-%M-%S"

_INVALID_SEGMENT_RE = re.compile(r"[^A-Za-z0-9]+")
_DUPLICATE_UNDERSCORES_RE = re.compile(r"_+")


def sanitize_filename_segment(value: object, fallback: str = "unnamed") -> str:
    """Normalize a filename segment into a portable underscore-delimited token."""
    raw = str(value).strip()
    if not raw:
        return fallback

    sanitized = _INVALID_SEGMENT_RE.sub("_", raw)
    sanitized = _DUPLICATE_UNDERSCORES_RE.sub("_", sanitized).strip("_")
    return sanitized or fallback


def build_project_details(*parts: object) -> str:
    """Join project-detail segments while dropping blanks."""
    cleaned = [
        sanitize_filename_segment(part, fallback="")
        for part in parts
        if part is not None
    ]
    cleaned = [part for part in cleaned if part]
    return "_".join(cleaned) if cleaned else "session"


def format_download_timestamp(
    timestamp: dt.datetime | None = None,
    *,
    timestamp_format: str = DEFAULT_DOWNLOAD_TIMESTAMP_FORMAT,
) -> str:
    """Format a timestamp for download filenames."""
    stamp = timestamp or dt.datetime.now()
    return stamp.strftime(timestamp_format)


def build_download_filename(
    *,
    project_details: str | Sequence[object],
    artifact: str,
    extension: str,
    timestamp: str | dt.datetime | None = None,
    timestamp_format: str = DEFAULT_DOWNLOAD_TIMESTAMP_FORMAT,
) -> str:
    """Build a standardized iPLAID download filename."""
    if isinstance(project_details, str):
        project_part = build_project_details(project_details)
    else:
        project_part = build_project_details(*project_details)

    artifact_part = sanitize_filename_segment(artifact, fallback="artifact")
    timestamp_part = (
        timestamp
        if isinstance(timestamp, str)
        else format_download_timestamp(timestamp, timestamp_format=timestamp_format)
    )
    ext = extension if extension.startswith(".") else f".{extension}"
    return f"{DOWNLOAD_FILENAME_PREFIX}_{project_part}_{artifact_part}_{timestamp_part}{ext}"


def build_run_artifact_paths(
    output_dir: Path,
    config: dict,
    *,
    timestamp: str | None = None,
) -> dict[str, Path | str]:
    """Return standardized output paths for a pipeline run."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_timestamp = timestamp or format_download_timestamp(
        timestamp_format=config.get("output_timestamp_format", DEFAULT_DOWNLOAD_TIMESTAMP_FORMAT)
    )
    project_details = (
        config.get("user_name", "user"),
        config.get("protocol_name", "run"),
    )
    dispenser = sanitize_filename_segment(
        str(config.get("dispenser", "idot")).lower(),
        fallback="idot",
    )
    protocol_path = output_dir / build_download_filename(
        project_details=project_details,
        artifact=f"{dispenser}_protocol",
        extension=".csv",
        timestamp=run_timestamp,
    )

    return {
        # `out_idot` is the legacy internal key used by the pipeline. The
        # filename itself is dispenser-aware.
        "out_idot": protocol_path,
        "out_protocol": protocol_path,
        "out_liquids": output_dir / build_download_filename(
            project_details=project_details,
            artifact="liquids_map",
            extension=".csv",
            timestamp=run_timestamp,
        ),
        "out_imeta": output_dir / build_download_filename(
            project_details=project_details,
            artifact="imeta",
            extension=".csv",
            timestamp=run_timestamp,
        ),
        "run_timestamp": run_timestamp,
    }


def build_source_prep_output_path(
    output_dir: Path,
    config: dict,
    *,
    timestamp: str | None = None,
    source_layout_provided: bool = False,
) -> Path:
    """Return the standardized source-prep or source-summary path."""
    timestamp_value = timestamp or format_download_timestamp(
        timestamp_format=config.get("output_timestamp_format", DEFAULT_DOWNLOAD_TIMESTAMP_FORMAT)
    )
    artifact = "source_plate_summary" if source_layout_provided else "source_plate_prep"
    return Path(output_dir) / build_download_filename(
        project_details=(config.get("user_name", "user"), config.get("protocol_name", "run")),
        artifact=artifact,
        extension=".txt",
        timestamp=timestamp_value,
    )


def build_design_layout_filename(
    *,
    plate_rows: int | None = None,
    plate_cols: int | None = None,
    timestamp: str | dt.datetime | None = None,
) -> str:
    """Return the standardized filename for a generated design layout CSV."""
    plate_shape = f"{plate_rows}x{plate_cols}" if plate_rows and plate_cols else None
    return build_download_filename(
        project_details=("plate_design", plate_shape),
        artifact="designed_layout",
        extension=".csv",
        timestamp=timestamp,
    )


def find_latest_download_artifact(
    output_dir: Path,
    *,
    artifact: str,
    extension: str,
    project_details: str | Iterable[object] | None = None,
) -> Path | None:
    """Locate the newest standardized artifact matching the given parameters."""
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return None

    artifact_part = sanitize_filename_segment(artifact, fallback="artifact")
    ext = extension if extension.startswith(".") else f".{extension}"
    if project_details is None:
        project_part = "*"
    elif isinstance(project_details, str):
        project_part = build_project_details(project_details)
    else:
        project_part = build_project_details(*project_details)
    pattern = f"{DOWNLOAD_FILENAME_PREFIX}_{project_part}_{artifact_part}_*{ext}"
    matches = sorted(
        output_dir.glob(pattern),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    return matches[0] if matches else None
