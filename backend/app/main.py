from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .jobs import JobStore
from .models import RunConfigModel
from .preview import build_layout_preview_from_upload


app = FastAPI(title="PLAID iDOT API", version="0.1.0")
job_store = JobStore()

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


@app.post("/api/runs")
async def create_run(
    layout_file: UploadFile = File(...),
    meta_file: UploadFile = File(...),
    config_json: str = Form(...),
) -> dict:
    try:
        config = RunConfigModel.model_validate_json(config_json).model_dump()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid config payload: {exc}") from exc

    try:
        return job_store.create_job(
            layout_bytes=await layout_file.read(),
            layout_filename=layout_file.filename or "layout.csv",
            meta_bytes=await meta_file.read(),
            meta_filename=meta_file.filename or "meta.csv",
            config=config,
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