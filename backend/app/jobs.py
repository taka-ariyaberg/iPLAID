from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.iplaid.pipeline import run_pipeline_with_inputs
from src.iplaid.validators_preflight import PreflightAssessmentError

from .preview import build_layout_preview_from_dataframe, build_layout_preview_from_path, dataframe_to_records


class JobStore:
    def __init__(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.jobs_root = self.repo_root / "backend" / "data" / "jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._design_workers: dict[str, subprocess.Popen[bytes] | subprocess.Popen[str]] = {}

    def bootstrap_payload(self) -> dict:
        import multiprocessing
        from src.iplaid.dispensers import list_dispensers

        config_template_path = self.repo_root / "config" / "config.template.json"
        config_template = json.loads(config_template_path.read_text(encoding="utf-8"))

        # Load each registered dispenser's source-plate and destination-plate
        # catalogs so the UI can swap dropdown options when the user picks a
        # dispenser.
        dispensers = list_dispensers()
        plate_types_by_dispenser: dict[str, list[str]] = {}
        plate_specs_by_dispenser: dict[str, dict] = {}
        source_plate_definitions_by_dispenser: dict[str, list[dict]] = {}
        target_plate_definitions_by_dispenser: dict[str, list[dict]] = {}
        for d in dispensers:
            specs_path = self.repo_root / "data" / d.plate_specs_path
            if not specs_path.exists():
                plate_types_by_dispenser[d.name] = []
                plate_specs_by_dispenser[d.name] = {}
                source_plate_definitions_by_dispenser[d.name] = []
            else:
                specs = json.loads(specs_path.read_text(encoding="utf-8"))
                plate_types_by_dispenser[d.name] = sorted(specs.keys())
                plate_specs_by_dispenser[d.name] = specs
                source_plate_definitions_by_dispenser[d.name] = [
                    {
                        "id": name,
                        "label": name,
                        "rows": spec.get("rows", 8),
                        "cols": spec.get("cols", 12),
                        "wells": spec.get("wells", 96),
                    }
                    for name, spec in specs.items()
                ]

            target_path = self.repo_root / "data" / d.target_plate_specs_path
            if not target_path.exists():
                target_plate_definitions_by_dispenser[d.name] = []
                continue
            target_raw = json.loads(target_path.read_text(encoding="utf-8"))
            # iDOT's catalog is an array of {id,label,rows,cols,wells}.
            # Echo's catalog is a dict keyed by SKU with per-plate metadata.
            # Normalize both into the same list-of-defs shape the UI expects.
            if isinstance(target_raw, list):
                target_plate_definitions_by_dispenser[d.name] = target_raw
            else:
                target_plate_definitions_by_dispenser[d.name] = [
                    {
                        "id": name,
                        "label": spec.get("label", name),
                        "rows": spec.get("rows", 16),
                        "cols": spec.get("cols", 24),
                        "wells": spec.get("wells", 384),
                    }
                    for name, spec in target_raw.items()
                ]

        # Legacy: keep `sourcePlateTypes`/`sourcePlateDefinitions` and
        # `targetPlateTypes`/`targetPlateDefinitions` keyed off the iDOT
        # catalogs so existing frontend consumers (DesignPanel,
        # PlateViewerPanel default, ResultsPage) continue to work unchanged.
        idot_specs = plate_specs_by_dispenser.get("idot", {})
        source_plate_definitions = [
            {
                "id": name,
                "label": name,
                "rows": spec.get("rows", 8),
                "cols": spec.get("cols", 12),
                "wells": spec.get("wells", 96),
            }
            for name, spec in idot_specs.items()
        ]
        idot_target_defs = target_plate_definitions_by_dispenser.get("idot", [])

        return {
            "configTemplate": config_template,
            "sourcePlateTypes": sorted(idot_specs.keys()),
            "sourcePlateDefinitions": source_plate_definitions,
            "targetPlateTypes": [p["id"] for p in idot_target_defs],
            "targetPlateDefinitions": idot_target_defs,
            "solverCpus": multiprocessing.cpu_count(),
            "dispensers": [
                {
                    "name": d.name,
                    "display_name": d.display_name,
                    "default_sourceplate_type": d.default_sourceplate_type,
                    "default_target_plate_type": d.default_target_plate_type,
                    "min_increment_nL": d.min_increment_nL,
                }
                for d in dispensers
            ],
            "plate_types_by_dispenser": plate_types_by_dispenser,
            "source_plate_definitions_by_dispenser": source_plate_definitions_by_dispenser,
            "target_plate_definitions_by_dispenser": target_plate_definitions_by_dispenser,
        }

    def create_job(
        self,
        *,
        layout_bytes: bytes,
        layout_filename: str,
        meta_bytes: bytes | None = None,
        meta_filename: str | None = None,
        config: dict,
        source_layout_bytes: bytes | None = None,
        source_layout_filename: str | None = None,
    ) -> dict:
        # Defense-in-depth: mirrors the HTTP route guard for programmatic callers.
        if (meta_bytes is None) == (source_layout_bytes is None):
            raise ValueError(
                "Provide exactly one of meta_file or source_layout_file. "
                "Source plate layout already includes the metadata."
            )

        job_id = uuid.uuid4().hex[:12]
        job_dir = self.jobs_root / job_id
        uploads_dir = job_dir / "uploads"
        outputs_dir = job_dir / "outputs"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)

        safe_layout_name = Path(layout_filename).name or "layout.csv"
        layout_path = uploads_dir / safe_layout_name
        layout_path.write_bytes(layout_bytes)

        meta_path: Path | None = None
        if meta_bytes is not None:
            safe_meta_name = Path(meta_filename or "meta.csv").name or "meta.csv"
            meta_path = uploads_dir / safe_meta_name
            meta_path.write_bytes(meta_bytes)

        source_layout_path: Path | None = None
        if source_layout_bytes is not None:
            safe_source_name = Path(source_layout_filename or "source_layout.csv").name
            source_layout_path = uploads_dir / safe_source_name
            source_layout_path.write_bytes(source_layout_bytes)

        run_config = dict(config)
        run_config["layout_file"] = safe_layout_name
        if meta_path is not None:
            run_config["meta_file"] = meta_path.name
        if source_layout_path is not None:
            run_config["source_layout_file"] = source_layout_path.name

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
            "preflight": None,
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
                "source_layout_path": source_layout_path,
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
        return self._read_status(status_path)

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
        meta_path: Path | None,
        outputs_dir: Path,
        config: dict,
        source_layout_path: Path | None = None,
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
                source_layout_path=source_layout_path,
            )

            summary = {
                "inputRows": int(len(result["df"])),
                "dispenseRows": int(len(result["all_rows"])),
                "uniqueLiquids": int(len(result["liquid_table_export"])),
                "plateCount": int(result["df"]["plateID"].nunique()),
                "solventFamilyCount": int(len(result["solvent_summary"])),
                "solventSummary": result["solvent_summary"],
                "targetDmsoUl": float(result["target_dmso_ul"]),
                "maxDmsoUl": float(result["max_dmso_ul"]),
            }
            result_preview_columns = [
                "plateID",
                "well",
                "cmpdname",
                "CONCuM",
                "is_solvent_control",
                "stock_conc_mM",
                "Volume [uL]",
            ]
            result_preview = build_layout_preview_from_dataframe(result["df"][result_preview_columns])

            source_layout_provided = bool(result.get("source_layout_provided"))
            dispenser_name = str(result["config"].get("dispenser", "idot")).lower()
            dispenser_label = {
                "idot": "iDOT",
                "echo": "Echo",
            }.get(dispenser_name, dispenser_name.upper())
            artifacts = []
            for key, label in [
                ("out_idot", f"{dispenser_label} Protocol CSV"),
                ("out_liquids", "Liquids CSV"),
                ("out_imeta", "iMETA CSV"),
                (
                    "out_source_prep",
                    "Source Plate Summary TXT" if source_layout_provided else "Source Prep TXT",
                ),
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
                    "preflight": result["preflight_assessment"],
                    "artifacts": artifacts,
                    "liquidsPreview": dataframe_to_records(
                        result["liquid_table"][
                            ["Liquid Name", "compound", "stock_mM", "is_control_liquid", "Source Plate", "Source Well"]
                        ],
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
            preflight = exc.assessment if isinstance(exc, PreflightAssessmentError) else None
            self._update_status(
                job_dir,
                {
                    "status": "failed",
                    "updatedAt": self._now(),
                    "finishedAt": self._now(),
                    "preflight": preflight,
                    "error": {
                        "message": str(exc),
                        "details": traceback.format_exc(),
                        "preflight": preflight,
                    },
                },
            )

    # ------------------------------------------------------------------
    # Design jobs (PLAID_Core solver)
    # ------------------------------------------------------------------

    def create_design_job(self, *, design_config: dict) -> dict:
        """
        Start a PLAID_Core solver job in a dedicated worker process.
        Returns the initial job status dict.
        """
        from .models import DesignConfigModel
        cfg = DesignConfigModel.model_validate(design_config)

        with self._lock:
            self._reap_design_workers_locked()
            active_job_id = next(iter(self._design_workers.keys()), None)
        if active_job_id:
            raise RuntimeError(
                f'Design job "{active_job_id}" is already running. Cancel it or wait for it to finish.'
            )

        job_id = uuid.uuid4().hex[:12]
        job_dir = self._design_job_dir(job_id)
        outputs_dir = job_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "jobId": job_id,
            "jobType": "design",
            "status": "queued",
            "phase": "queued",
            "createdAt": self._now(),
            "updatedAt": self._now(),
            "designConfig": cfg.model_dump(),
            "layoutPreview": None,
            "preflight": None,
            "artifacts": [],
            "numPlates": None,
            "numWells": None,
            "workerPid": None,
            "error": None,
        }
        self._write_status(job_dir, payload)

        try:
            worker = self._launch_design_worker(job_dir, outputs_dir)
        except Exception as exc:
            self._update_status(
                job_dir,
                {
                    "status": "failed",
                    "phase": "failed",
                    "updatedAt": self._now(),
                    "finishedAt": self._now(),
                    "error": {
                        "message": str(exc),
                        "details": traceback.format_exc(),
                    },
                },
            )
            raise

        with self._lock:
            self._design_workers[job_id] = worker

        return self.get_design_job(job_id)

    def get_design_job(self, job_id: str) -> dict:
        self._reap_design_workers()
        job_dir = self._design_job_dir(job_id)
        status_path = job_dir / "status.json"
        if not status_path.exists():
            raise FileNotFoundError(job_id)
        payload = self._read_status(status_path)
        return self._reconcile_design_job(job_id, job_dir, payload)

    def resolve_design_artifact(self, job_id: str, artifact_name: str) -> Path:
        job_dir = self._design_job_dir(job_id)
        candidate = (job_dir / "outputs" / Path(artifact_name).name).resolve()
        outputs_dir = (job_dir / "outputs").resolve()
        if outputs_dir not in candidate.parents or not candidate.exists():
            raise FileNotFoundError(artifact_name)
        return candidate

    def cancel_design_job(self, job_id: str, *, reason: str = "Design job cancelled.") -> dict:
        payload = self.get_design_job(job_id)
        if payload["status"] in {"completed", "failed"}:
            return payload

        job_dir = self._design_job_dir(job_id)
        worker_pid = payload.get("workerPid")
        with self._lock:
            worker = self._design_workers.pop(job_id, None)

        self._terminate_design_worker(worker, worker_pid)

        current = self._read_status(job_dir / "status.json")
        if current["status"] in {"completed", "failed"}:
            return current

        self._update_status(
            job_dir,
            {
                "status": "failed",
                "phase": "failed",
                "updatedAt": self._now(),
                "finishedAt": self._now(),
                "workerPid": None,
                "error": {
                    "message": reason,
                    "details": "The design solve was stopped before completion.",
                },
            },
        )
        return self.get_design_job(job_id)

    def shutdown(self) -> None:
        with self._lock:
            active_job_ids = list(self._design_workers.keys())

        for job_id in active_job_ids:
            with contextlib.suppress(FileNotFoundError):
                self.cancel_design_job(
                    job_id,
                    reason="Server shutdown cancelled the active design job.",
                )
        self._reap_design_workers()

    def _design_job_dir(self, job_id: str) -> Path:
        return self.jobs_root / ("design_" + job_id)

    def _launch_design_worker(self, job_dir: Path, outputs_dir: Path) -> subprocess.Popen[bytes] | subprocess.Popen[str]:
        log_path = outputs_dir / "design-worker.log"
        command = [sys.executable, "-m", "backend.app.design_worker", str(job_dir)]
        log_stream = log_path.open("w", encoding="utf-8")
        try:
            return subprocess.Popen(
                command,
                cwd=self.repo_root,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                text=True,
            )
        finally:
            log_stream.close()

    def _reconcile_design_job(self, job_id: str, job_dir: Path, payload: dict) -> dict:
        if payload.get("status") not in {"queued", "running"}:
            return payload

        worker_pid = payload.get("workerPid")
        with self._lock:
            worker = self._design_workers.get(job_id)

        is_running = bool(worker and worker.poll() is None)
        if not is_running and worker_pid:
            is_running = self._is_pid_running(int(worker_pid))

        if is_running:
            return payload

        self._update_status(
            job_dir,
            {
                "status": "failed",
                "phase": "failed",
                "updatedAt": self._now(),
                "finishedAt": self._now(),
                "workerPid": None,
                "error": {
                    "message": "Design worker exited unexpectedly.",
                    "details": "The PLAID layout solve stopped before returning a result.",
                },
            },
        )
        return self._read_status(job_dir / "status.json")

    def _terminate_design_worker(
        self,
        worker: subprocess.Popen[bytes] | subprocess.Popen[str] | None,
        worker_pid: int | None,
    ) -> None:
        pid = worker_pid or (worker.pid if worker else None)
        if pid is None:
            return

        self._signal_process_group(pid, signal.SIGTERM)
        if worker is not None:
            with contextlib.suppress(subprocess.TimeoutExpired):
                worker.wait(timeout=2)

        if self._is_pid_running(pid):
            self._signal_process_group(pid, signal.SIGKILL)
            if worker is not None:
                with contextlib.suppress(subprocess.TimeoutExpired):
                    worker.wait(timeout=1)

    @staticmethod
    def _signal_process_group(pid: int, sig: int) -> None:
        if hasattr(os, "killpg"):
            try:
                pgid = os.getpgid(pid)
            except ProcessLookupError:
                return
            with contextlib.suppress(ProcessLookupError):
                os.killpg(pgid, sig)
            return

        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, sig)

    @staticmethod
    def _is_pid_running(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _reap_design_workers(self) -> None:
        with self._lock:
            self._reap_design_workers_locked()

    def _reap_design_workers_locked(self) -> None:
        finished_job_ids = [
            job_id
            for job_id, worker in self._design_workers.items()
            if worker.poll() is not None
        ]
        for job_id in finished_job_ids:
            self._design_workers.pop(job_id, None)

    def _write_status(self, job_dir: Path, payload: dict) -> None:
        with self._lock:
            status_path = job_dir / "status.json"
            tmp_path = job_dir / "status.json.tmp"
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_path.replace(status_path)

    def _update_status(self, job_dir: Path, patch: dict) -> None:
        current = self._read_status(job_dir / "status.json")
        current.update(patch)
        self._write_status(job_dir, current)

    @staticmethod
    def _read_status(status_path: Path) -> dict:
        return json.loads(status_path.read_text(encoding="utf-8"))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
