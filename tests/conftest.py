"""Shared test fixtures and path setup.

Importable modules:
- `iplaid.*`        → resolved via `pythonpath = ["src", ...]` in pyproject.toml
- `backend.app.*`   → resolved via `pythonpath = [..., "."]` in pyproject.toml
- `src.iplaid.*`    → legacy form, also resolvable; prefer `iplaid.*` in new tests

Fixtures defined here are auto-discovered by pytest in any test under tests/.
"""
from __future__ import annotations

import datetime as _datetime
import json
import shutil
from pathlib import Path

import pytest


SCENARIOS_DIR = Path(__file__).parent / "scenarios"
FROZEN_NOW = _datetime.datetime(2026, 1, 1, 12, 0, 0)


@pytest.fixture
def freeze_now(monkeypatch: pytest.MonkeyPatch):
    """Freeze datetime.now() inside iplaid.output so the iDOT CSV header is deterministic."""
    import iplaid.output as _output

    class _FrozenDateTime(_datetime.datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return FROZEN_NOW if tz is None else FROZEN_NOW.replace(tzinfo=tz)

    monkeypatch.setattr(_output.datetime, "datetime", _FrozenDateTime)
    yield


@pytest.fixture
def load_golden(tmp_path: Path):
    """Copy a golden fixture into tmp_path and return (work_dir, config_dict).

    Usage:
        def test_x(load_golden):
            work, cfg = load_golden("idot_basic")
            ...
    """
    def _load(name: str) -> tuple[Path, dict]:
        src = SCENARIOS_DIR / name
        work = tmp_path / name
        work.mkdir(parents=True)
        shutil.copy(src / "layout.csv", work / "layout.csv")
        shutil.copy(src / "meta.csv", work / "meta.csv")
        cfg = json.loads((src / "config.json").read_text())
        (work / "out").mkdir()
        return work, cfg

    return _load


@pytest.fixture
def baseline_config() -> dict:
    """A minimal valid config dict suitable for pipeline runs in unit tests."""
    return {
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
    }
