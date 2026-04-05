from __future__ import annotations

import json
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.iplaid.pipeline import run_pipeline_with_inputs

from .preview import build_layout_preview_from_dataframe, build_layout_preview_from_path, dataframe_to_records


class JobStore:
    def __init__(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.jobs_root = self.repo_root / "backend" / "data" / "jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def bootstrap_payload(self) -> dict:
        config_template_path = self.repo_root / "config" / "config.template.json"
        plate_specs_path = self.repo_root / "data" / "source_plate_specs.json"
        target_plate_types_path = self.repo_root / "data" / "target_plate_types.json"

        config_template = json.loads(config_template_path.read_text(encoding="utf-8"))
        plate_specs = json.loads(plate_specs_path.read_text(encoding="utf-8"))
        target_plate_types = json.loads(target_plate_types_path.read_text(encoding="utf-8"))

        source_plate_definitions = [
            {
                "id": name,
                "label": name,
                "rows": spec.get("rows", 8),
                "cols": spec.get("cols", 12),
                "wells": spec.get("wells", 96),
            }
            for name, spec in plate_specs.items()
        ]

        return {
            "configTemplate": config_template,
            "sourcePlateTypes": sorted(plate_specs.keys()),
            "sourcePlateDefinitions": source_plate_definitions,
            "targetPlateTypes": [p["id"] for p in target_plate_types],
            "targetPlateDefinitions": target_plate_types,
        }

    def create_job(
        self,
        *,
        layout_bytes: bytes,
        layout_filename: str,
        meta_bytes: bytes,
        meta_filename: str,
        config: dict,
    ) -> dict:
        job_id = uuid.uuid4().hex[:12]
        job_dir = self.jobs_root / job_id
        uploads_dir = job_dir / "uploads"
        outputs_dir = job_dir / "outputs"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)

        safe_layout_name = Path(layout_filename).name or "layout.csv"
        safe_meta_name = Path(meta_filename).name or "meta.csv"
        layout_path = uploads_dir / safe_layout_name
        meta_path = uploads_dir / safe_meta_name
        layout_path.write_bytes(layout_bytes)
        meta_path.write_bytes(meta_bytes)

        run_config = dict(config)
        run_config["layout_file"] = safe_layout_name
        run_config["meta_file"] = safe_meta_name

        preview = build_layout_preview_from_path(layout_path)
        payload = {
            "jobId": job_id,
            "status": "queued",
            "createdAt": self._now(),
            "updatedAt": self._now(),
            "config": run_config,
            "preview": preview,
            "resultPreview": None,
            "summary": None,
            "artifacts": [],
            "liquidsPreview": [],
            "stockSummary": [],
            "error": None,
        }
        self._write_status(job_dir, payload)

        worker = threading.Thread(
            target=self._run_job,
            kwargs={
                "job_id": job_id,
                "job_dir": job_dir,
                "layout_path": layout_path,
                "meta_path": meta_path,
                "outputs_dir": outputs_dir,
                "config": run_config,
            },
            daemon=True,
        )
        worker.start()

        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict:
        job_dir = self.jobs_root / job_id
        status_path = job_dir / "status.json"
        if not status_path.exists():
            raise FileNotFoundError(job_id)
        return json.loads(status_path.read_text(encoding="utf-8"))

    def resolve_artifact(self, job_id: str, artifact_name: str) -> Path:
        job_dir = self.jobs_root / job_id
        candidate = (job_dir / "outputs" / Path(artifact_name).name).resolve()
        outputs_dir = (job_dir / "outputs").resolve()
        if outputs_dir not in candidate.parents or not candidate.exists():
            raise FileNotFoundError(artifact_name)
        return candidate

    def _run_job(
        self,
        *,
        job_id: str,
        job_dir: Path,
        layout_path: Path,
        meta_path: Path,
        outputs_dir: Path,
        config: dict,
    ) -> None:
        self._update_status(job_dir, {"status": "running", "updatedAt": self._now(), "startedAt": self._now()})

        try:
            result = run_pipeline_with_inputs(
                config=config,
                layout_path=layout_path,
                meta_path=meta_path,
                output_dir=outputs_dir,
                include_source_prep=True,
                project_root=self.repo_root,
            )

            summary = {
                "inputRows": int(len(result["df"])),
                "dispenseRows": int(len(result["all_rows"])),
                "uniqueLiquids": int(len(result["liquid_table_export"])),
                "plateCount": int(result["df"]["plateID"].nunique()),
                "targetDmsoUl": float(result["target_dmso_ul"]),
                "maxDmsoUl": float(result["max_dmso_ul"]),
            }
            result_preview_columns = [
                "plateID",
                "well",
                "cmpdname",
                "CONCuM",
                "stock_conc_mM",
                "Volume [uL]",
            ]
            result_preview = build_layout_preview_from_dataframe(result["df"][result_preview_columns])

            artifacts = []
            for key, label in [
                ("out_idot", "Protocol CSV"),
                ("out_liquids", "Liquids CSV"),
                ("out_source_prep", "Source Prep TXT"),
            ]:
                artifact_path = result["paths"].get(key)
                if artifact_path:
                    artifacts.append({
                        "name": Path(artifact_path).name,
                        "label": label,
                    })

            self._update_status(
                job_dir,
                {
                    "status": "completed",
                    "updatedAt": self._now(),
                    "finishedAt": self._now(),
                    "resultPreview": result_preview,
                    "summary": summary,
                    "artifacts": artifacts,
                    "liquidsPreview": dataframe_to_records(
                        result["liquid_table"][["Liquid Name", "compound", "stock_mM", "Source Plate", "Source Well"]],
                        limit=96,
                    ),
                    "sourceWellTargetMap": (
                        result["all_rows"]
                        .dropna(subset=["Source Well", "Target Well"])
                        .groupby("Source Well")["Target Well"]
                        .agg(lambda wells: sorted(wells.tolist()))
                        .to_dict()
                    ),
                    "stockSummary": dataframe_to_records(result["stock_summary"], limit=24),
                    "error": None,
                },
            )
        except Exception as exc:
            self._update_status(
                job_dir,
                {
                    "status": "failed",
                    "updatedAt": self._now(),
                    "finishedAt": self._now(),
                    "error": {
                        "message": str(exc),
                        "details": traceback.format_exc(),
                    },
                },
            )

    def _write_status(self, job_dir: Path, payload: dict) -> None:
        with self._lock:
            (job_dir / "status.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _update_status(self, job_dir: Path, patch: dict) -> None:
        current = json.loads((job_dir / "status.json").read_text(encoding="utf-8"))
        current.update(patch)
        self._write_status(job_dir, current)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()