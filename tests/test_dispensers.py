"""Tests for iplaid.dispensers registry + Dispenser Protocol conformance."""
from __future__ import annotations

import pytest

from iplaid.dispensers import get_dispenser, list_dispensers
from iplaid.dispensers.base import Dispenser, DispenserSpec, UnknownDispenserError


def test_dispenser_spec_is_frozen_dataclass() -> None:
    spec = DispenserSpec(
        name="test",
        display_name="Test",
        plate_specs_path="test_specs.json",
        target_plate_specs_path="test_target_specs.json",
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


def test_each_registered_dispenser_satisfies_protocol() -> None:
    """Every registered dispenser must implement the Dispenser Protocol."""
    from iplaid.dispensers import _REGISTRY

    assert len(_REGISTRY) > 0, "Registry must have at least one dispenser"
    for name, disp in _REGISTRY.items():
        assert isinstance(disp, Dispenser), f"{name!r} does not implement Dispenser Protocol"
        assert disp.spec.name == name, f"Spec name {disp.spec.name!r} != registry key {name!r}"
        for method in [
            "load_plate_specs",
            "build_protocol",
            "write_protocol",
            "write_liquids",
            "validate_export",
        ]:
            assert callable(getattr(disp, method)), f"{name}.{method} not callable"
