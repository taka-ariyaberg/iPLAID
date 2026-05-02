"""Dispenser registry and interface conformance tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.dispensers import get_dispenser, list_dispensers
from iplaid.dispensers.base import Dispenser, DispenserSpec, UnknownDispenserError


def test_dispenser_spec_is_frozen_dataclass() -> None:
    spec = DispenserSpec(
        name="test",
        display_name="Test",
        plate_specs_path="test_specs.json",
        min_increment_nL=0.0,
        default_sourceplate_type="X",
        default_target_plate_type="Y",
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        spec.name = "other"  # type: ignore[misc]


def test_get_dispenser_unknown_raises() -> None:
    with pytest.raises(UnknownDispenserError):
        get_dispenser("nope")


def test_list_dispensers_returns_specs() -> None:
    specs = list_dispensers()
    assert len(specs) >= 1
    assert all(isinstance(s, DispenserSpec) for s in specs)
