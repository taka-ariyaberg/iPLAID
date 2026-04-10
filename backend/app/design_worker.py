from __future__ import annotations

import io
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .design_preflight import DesignPreflightError, assess_design_preflight
from .designer import layout_to_csv_bytes, run_design
from .models import DesignConfigModel
from .preview import build_layout_preview_from_dataframe


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_status(job_dir: Path) -> dict:
    return json.loads((job_dir / "status.json").read_text(encoding="utf-8"))


def _write_status(job_dir: Path, payload: dict) -> None:
    status_path = job_dir / "status.json"
    tmp_path = job_dir / "status.json.tmp"
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(status_path)


def _update_status(job_dir: Path, patch: dict) -> None:
    current = _read_status(job_dir)
    current.update(patch)
    _write_status(job_dir, current)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: python -m backend.app.design_worker <job_dir>")

    job_dir = Path(argv[1]).resolve()
    outputs_dir = job_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    _update_status(
        job_dir,
        {
            "status": "running",
            "phase": "preflight",
            "updatedAt": _now(),
            "startedAt": _now(),
            "workerPid": os.getpid(),
        },
    )

    try:
        payload = _read_status(job_dir)
        cfg = DesignConfigModel.model_validate(payload["designConfig"])
        preflight = assess_design_preflight(cfg)
        _update_status(
            job_dir,
            {
                "updatedAt": _now(),
                "preflight": preflight,
            },
        )
        if not preflight["ok"]:
            raise DesignPreflightError(preflight)

        _update_status(
            job_dir,
            {
                "updatedAt": _now(),
                "phase": "solving",
            },
        )

        layout, _plate_cfg = run_design(cfg)
        layout_bytes = layout_to_csv_bytes(layout, cfg)

        layout_path = outputs_dir / "designed_layout.csv"
        layout_path.write_bytes(layout_bytes)

        df = pd.read_csv(io.BytesIO(layout_bytes))
        preview = build_layout_preview_from_dataframe(df)

        _update_status(
            job_dir,
            {
                "status": "completed",
                "phase": "completed",
                "updatedAt": _now(),
                "finishedAt": _now(),
                "workerPid": None,
                "layoutPreview": preview,
                "artifacts": [
                    {"name": "designed_layout.csv", "label": "Layout CSV"},
                ],
                "numPlates": layout.num_plates,
                "numWells": len(layout.wells),
                "error": None,
            },
        )
        return 0
    except Exception as exc:
        preflight = exc.report if isinstance(exc, DesignPreflightError) else None
        _update_status(
            job_dir,
            {
                "status": "failed",
                "phase": "failed",
                "updatedAt": _now(),
                "finishedAt": _now(),
                "workerPid": None,
                "preflight": preflight or _read_status(job_dir).get("preflight"),
                "error": {
                    "message": str(exc),
                    "details": traceback.format_exc(),
                },
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
