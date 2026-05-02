"""Dispenser registry. Add new dispensers by importing them and adding to _REGISTRY."""
from __future__ import annotations

from .base import Dispenser, DispenserSpec, SourceLayoutError, UnknownDispenserError

_REGISTRY: dict[str, Dispenser] = {}


def get_dispenser(name: str) -> Dispenser:
    if name not in _REGISTRY:
        raise UnknownDispenserError(
            f"Unknown dispenser '{name}'. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]


def list_dispensers() -> list[DispenserSpec]:
    return [d.spec for d in _REGISTRY.values()]


def _register(dispenser: Dispenser) -> None:
    """Internal: register a dispenser instance under its spec.name."""
    _REGISTRY[dispenser.spec.name] = dispenser


__all__ = [
    "Dispenser",
    "DispenserSpec",
    "SourceLayoutError",
    "UnknownDispenserError",
    "get_dispenser",
    "list_dispensers",
]
