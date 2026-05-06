from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

from .design_preflight import assess_design_preflight
from .jobs import JobStore
from .models import DesignConfigModel, RunConfigModel
from .preview import build_layout_preview_from_upload, validate_source_layout_upload


app = FastAPI(title="PLAID iDOT API", version="0.1.0")
job_store = JobStore()
repo_root = Path(__file__).resolve().parents[2]
frontend_dist = repo_root / "frontend" / "dist"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/bootstrap")
def bootstrap() -> dict:
    return job_store.bootstrap_payload()


@app.post("/api/layouts/preview")
async def preview_layout(layout_file: UploadFile = File(...)) -> dict:
    try:
        file_bytes = await layout_file.read()
        return build_layout_preview_from_upload(layout_file.filename or "layout.csv", file_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/source-layouts/preview")
async def preview_source_layout(source_layout_file: UploadFile = File(...)) -> dict:
    """Schema-level validation for the optional Source plate layout CSV.

    Returns 400 with a user-readable detail if the file isn't shaped the way
    the pipeline will need; geometry/completeness checks happen at run time.
    """
    try:
        file_bytes = await source_layout_file.read()
        return validate_source_layout_upload(
            source_layout_file.filename or "source_layout.csv", file_bytes
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runs")
async def create_run(
    layout_file: UploadFile = File(...),
    config_json: str = Form(...),
    meta_file: UploadFile | None = File(None),
    source_layout_file: UploadFile | None = File(None),
) -> dict:
    if (meta_file is None) == (source_layout_file is None):
        raise HTTPException(
            status_code=422,
            detail=(
                "Provide exactly one of: meta_file, source_layout_file. "
                "Source plate layout already includes the metadata."
            ),
        )

    try:
        config = RunConfigModel.model_validate_json(config_json).model_dump()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid config payload: {exc}") from exc

    meta_bytes = await meta_file.read() if meta_file is not None else None
    meta_filename = meta_file.filename if meta_file is not None else None

    source_layout_bytes = None
    source_layout_filename = None
    if source_layout_file is not None:
        source_layout_bytes = await source_layout_file.read()
        source_layout_filename = source_layout_file.filename or "source_layout.csv"

    try:
        return job_store.create_job(
            layout_bytes=await layout_file.read(),
            layout_filename=layout_file.filename or "layout.csv",
            meta_bytes=meta_bytes,
            meta_filename=meta_filename,
            config=config,
            source_layout_bytes=source_layout_bytes,
            source_layout_filename=source_layout_filename,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs/{job_id}")
def get_run(job_id: str) -> dict:
    try:
        return job_store.get_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Run not found: {job_id}") from exc


@app.get("/api/runs/{job_id}/artifacts/{artifact_name}")
def download_artifact(job_id: str, artifact_name: str) -> FileResponse:
    try:
        artifact_path = job_store.resolve_artifact(job_id, artifact_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_name}") from exc

    return FileResponse(path=artifact_path, filename=artifact_path.name)


# ---------------------------------------------------------------------------
# Design (PLAID_Core) endpoints
# ---------------------------------------------------------------------------

@app.post("/api/design/validate")
async def validate_design(body: DesignConfigModel) -> dict:
    """
    Fast pre-flight validation — no solver call.
    Returns a structured preflight report without running PLAID_Core.
    """
    return assess_design_preflight(body)


@app.post("/api/design/solve")
async def solve_design(body: DesignConfigModel) -> dict:
    """Start a PLAID_Core solver job. Returns initial job record."""
    preflight = assess_design_preflight(body)
    if not preflight["ok"]:
        raise HTTPException(status_code=422, detail={"errors": preflight["errors"]})
    try:
        return job_store.create_design_job(design_config=body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/design/jobs/{job_id}")
def get_design_job(job_id: str) -> dict:
    """Poll a solver job status."""
    try:
        return job_store.get_design_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Design job not found: {job_id}") from exc


@app.post("/api/design/jobs/{job_id}/cancel")
def cancel_design_job(job_id: str) -> dict:
    try:
        return job_store.cancel_design_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Design job not found: {job_id}") from exc


@app.get("/api/design/jobs/{job_id}/artifacts/{artifact_name}")
def download_design_artifact(job_id: str, artifact_name: str) -> FileResponse:
    try:
        artifact_path = job_store.resolve_design_artifact(job_id, artifact_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_name}") from exc
    return FileResponse(path=artifact_path, filename=artifact_path.name)


@app.on_event("shutdown")
def shutdown_event() -> None:
    job_store.shutdown()


def _resolve_frontend_asset(path: str) -> Path | None:
    if not frontend_dist.exists():
        return None

    candidate = (frontend_dist / path).resolve()
    if candidate != frontend_dist and frontend_dist not in candidate.parents:
        return None
    if candidate.is_file():
        return candidate
    return None


if frontend_dist.exists():
    @app.get("/", include_in_schema=False)
    def serve_frontend_index() -> FileResponse:
        return FileResponse(frontend_dist / "index.html")


    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend_app(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        asset = _resolve_frontend_asset(full_path)
        if asset is not None:
            return FileResponse(asset)

        if "." in Path(full_path).name:
            raise HTTPException(status_code=404, detail="Asset not found")

        return FileResponse(frontend_dist / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def frontend_not_built() -> PlainTextResponse:
        return PlainTextResponse(
            "iPLAID frontend build not found. Build the frontend or run the Docker image.",
            status_code=503,
        )
