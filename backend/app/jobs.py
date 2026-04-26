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

            artifacts = []
            for key, label in [
                ("out_idot", "Protocol CSV"),
                ("out_liquids", "Liquids CSV"),
                ("out_imeta", "iMETA CSV"),
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
