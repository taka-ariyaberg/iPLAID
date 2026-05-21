"""Cross-field validator: target_plate_type must be in the active dispenser's
destination-plate catalog.

Single backend chokepoint catching a mismatched (dispenser, target_plate_type)
regardless of caller — UI, CLI, notebook, or direct API submission.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from iplaid.dispensers import get_dispenser
from iplaid.pipeline import _validate_target_plate_against_catalog


REPO_ROOT = Path(__file__).resolve().parents[1]


# ---- Happy-path accepts ------------------------------------------------------


def test_validator_accepts_idot_default() -> None:
    """iDOT + MWP 384 is the canonical iDOT combo and must pass."""
    disp = get_dispenser("idot")
    cfg = {"target_plate_type": "MWP 384"}
    _validate_target_plate_against_catalog(disp, cfg, REPO_ROOT)


def test_validator_accepts_echo_revvity_default() -> None:
    """Echo + Revvity_384_6007660 is the canonical Echo combo and must pass."""
    disp = get_dispenser("echo")
    cfg = {"target_plate_type": "Revvity_384_6007660"}
    _validate_target_plate_against_catalog(disp, cfg, REPO_ROOT)


def test_validator_accepts_every_id_in_each_dispenser_catalog() -> None:
    """Every entry in the catalog must round-trip through the validator."""
    for disp_name in ("idot", "echo"):
        disp = get_dispenser(disp_name)
        catalog_path = REPO_ROOT / "data" / disp.spec.target_plate_specs_path
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            ids = [p["id"] for p in raw]
        else:
            ids = list(raw.keys())
        for plate_id in ids:
            _validate_target_plate_against_catalog(disp, {"target_plate_type": plate_id}, REPO_ROOT)


# ---- Reject cases ------------------------------------------------------------


def test_validator_rejects_idot_label_on_echo_dispenser() -> None:
    """The exact bug we're fixing: dispenser=echo + target_plate_type=MWP 384."""
    disp = get_dispenser("echo")
    cfg = {"target_plate_type": "MWP 384"}
    with pytest.raises(ValueError, match="not in the Echo destination-plate catalog"):
        _validate_target_plate_against_catalog(disp, cfg, REPO_ROOT)


def test_validator_rejects_echo_label_on_idot_dispenser() -> None:
    """Inverse: dispenser=idot + target_plate_type=Revvity_384_6007660."""
    disp = get_dispenser("idot")
    cfg = {"target_plate_type": "Revvity_384_6007660"}
    with pytest.raises(ValueError, match="not in the iDOT destination-plate catalog"):
        _validate_target_plate_against_catalog(disp, cfg, REPO_ROOT)


def test_validator_rejects_typo() -> None:
    """Case-sensitive exact match — typos must fail loudly, not be silently coerced."""
    disp = get_dispenser("echo")
    cfg = {"target_plate_type": "revvity_384_6007660"}  # wrong case
    with pytest.raises(ValueError):
        _validate_target_plate_against_catalog(disp, cfg, REPO_ROOT)


def test_validator_rejects_missing_field() -> None:
    """target_plate_type absent → rejected (None is not a valid catalog key)."""
    disp = get_dispenser("echo")
    cfg: dict = {}
    with pytest.raises(ValueError):
        _validate_target_plate_against_catalog(disp, cfg, REPO_ROOT)


def test_validator_error_message_lists_valid_options(tmp_path: Path) -> None:
    """The error must enumerate valid plate names so the caller can fix the typo."""
    disp = get_dispenser("echo")
    cfg = {"target_plate_type": "not_a_real_plate"}
    with pytest.raises(ValueError) as excinfo:
        _validate_target_plate_against_catalog(disp, cfg, REPO_ROOT)
    msg = str(excinfo.value)
    assert "Revvity_384_6007660" in msg
    assert "Valid options" in msg


# ---- Graceful degradation ----------------------------------------------------


def test_validator_skips_when_catalog_file_missing(tmp_path: Path) -> None:
    """No catalog file in project_root/data → no-op (don't block the run)."""
    disp = get_dispenser("echo")
    cfg = {"target_plate_type": "literally_anything"}
    # tmp_path has no data/echo_target_plate_specs.json → validator must return
    _validate_target_plate_against_catalog(disp, cfg, tmp_path)


def test_validator_skips_when_catalog_json_is_garbage(tmp_path: Path) -> None:
    """Unreadable/garbage catalog → no-op (graceful, don't crash)."""
    disp = get_dispenser("echo")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / disp.spec.target_plate_specs_path).write_text("{not valid json")
    cfg = {"target_plate_type": "literally_anything"}
    _validate_target_plate_against_catalog(disp, cfg, tmp_path)
