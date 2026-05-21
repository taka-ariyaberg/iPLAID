"""Tests for /api/runs upload contract: exactly one of meta or source_layout, etc."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _layout_bytes() -> bytes:
    return (
        "plateID,well,cmpdname,CONCuM\n"
        "plate_1,A1,Dasatinib,1.0\n"
        "plate_1,A2,DMSO,0.0\n"
    ).encode("utf-8")


def _meta_bytes() -> bytes:
    return (
        "cmpdname,highest_stock_mM,solvent\n"
        "Dasatinib,1.0,DMSO\n"
        "DMSO,0.0,DMSO\n"
    ).encode("utf-8")


def _source_layout_bytes() -> bytes:
    return (
        "cmpdname,conc_mM,solvent,source_plate,source_well\n"
        "Dasatinib,1.0,DMSO,P1,A1\n"
        "DMSO,0.0,DMSO,P1,B1\n"
    ).encode("utf-8")


def _config_json() -> str:
    return json.dumps({
        "user_name": "tester",
        "protocol_name": "regression",
        "dispenser": "idot",
        "sourceplate_type": "S.100 Plate",
        "target_plate_type": "MWP 384",
        "dilution_solvent": "DMSO",
        "working_volume_ul": 50.0,
        "max_dmso_pct": 0.5,
        "source_prep_overage_pct": 0.1,
        "min_pipette_volume_uL": 1.0,
        "source_well_fill_pct": 0.8,
        "standard_prep_volume_uL": 50,
        "layout_file": "layout.csv",
        "meta_file": "meta.csv",
        "output_timestamp_format": "FROZEN-TIMESTAMP",
    })


def test_runs_rejects_both_files() -> None:
    files = {
        "layout_file": ("layout.csv", _layout_bytes(), "text/csv"),
        "meta_file": ("meta.csv", _meta_bytes(), "text/csv"),
        "source_layout_file": ("src.csv", _source_layout_bytes(), "text/csv"),
    }
    resp = client.post("/api/runs", files=files, data={"config_json": _config_json()})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "exactly one" in detail.lower()


def test_runs_rejects_neither() -> None:
    files = {
        "layout_file": ("layout.csv", _layout_bytes(), "text/csv"),
    }
    resp = client.post("/api/runs", files=files, data={"config_json": _config_json()})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    # Our custom error is a string; FastAPI's built-in field-missing error is a list.
    if isinstance(detail, str):
        assert "exactly one" in detail.lower() or "required" in detail.lower()
    else:
        # FastAPI built-in: list of validation errors — at least one mentions the field
        detail_str = json.dumps(detail).lower()
        assert "exactly one" in detail_str or "required" in detail_str


def test_runs_accepts_layout_only() -> None:
    files = {
        "layout_file": ("layout.csv", _layout_bytes(), "text/csv"),
        "source_layout_file": ("src.csv", _source_layout_bytes(), "text/csv"),
    }
    resp = client.post("/api/runs", files=files, data={"config_json": _config_json()})
    assert resp.status_code == 200, resp.text


def test_runs_accepts_meta_only() -> None:
    files = {
        "layout_file": ("layout.csv", _layout_bytes(), "text/csv"),
        "meta_file": ("meta.csv", _meta_bytes(), "text/csv"),
    }
    resp = client.post("/api/runs", files=files, data={"config_json": _config_json()})
    assert resp.status_code == 200, resp.text
