from __future__ import annotations

import math

try:
    from plaid_core.validators import validate_minizinc_available
except ImportError:
    from src.plaid_core.validators import validate_minizinc_available

from .designer import _to_plate_config, validate_design_config


class DesignPreflightError(ValueError):
    """Raised when the design preflight detects blocking issues."""

    def __init__(self, report: dict):
        self.report = report
        message = report["errors"][0] if report.get("errors") else "Design preflight failed."
        super().__init__(message)


def assess_design_preflight(cfg) -> dict:
    """Run fast design checks before handing the config to PLAID_Core."""
    errors = list(validate_design_config(cfg))
    warnings: list[str] = []

    for compound in cfg.compounds:
        name = compound.name.strip() or "Unnamed compound"
        if not compound.conc_entries:
            errors.append(f'Compound "{name}" has no concentration entries.')
            continue
        for index, entry in enumerate(compound.conc_entries, start=1):
            if entry.value_um <= 0:
                errors.append(f'Compound "{name}" concentration #{index} must be greater than 0.')

    if not validate_minizinc_available():
        errors.append("MiniZinc is not available. Install MiniZinc before using Design with PLAID.")

    summary = {
        "compoundCount": len(cfg.compounds),
        "concentrationEntryCount": sum(len(compound.conc_entries) for compound in cfg.compounds),
        "solventCount": len(cfg.solvents),
        "totalSamples": 0,
        "usableWellsPerPlate": 0,
        "estimatedMinimumPlates": 0,
    }

    if errors:
        return {
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "summary": summary,
        }

    plate_cfg = _to_plate_config(cfg)
    usable_wells = int(plate_cfg.usable_wells_per_plate)
    total_samples = int(plate_cfg.total_samples)
    estimated_minimum_plates = int(math.ceil(total_samples / usable_wells)) if usable_wells else 0

    summary = {
        "compoundCount": len(cfg.compounds),
        "concentrationEntryCount": sum(len(compound.conc_entries) for compound in cfg.compounds),
        "solventCount": len(cfg.solvents),
        "totalSamples": total_samples,
        "usableWellsPerPlate": usable_wells,
        "estimatedMinimumPlates": estimated_minimum_plates,
    }

    if estimated_minimum_plates > 1:
        warnings.append(
            f"This design needs at least {estimated_minimum_plates} plates with the current plate geometry."
        )
    if usable_wells and total_samples > int(usable_wells * 0.9):
        warnings.append("This design is a tight fit and may take longer to solve.")
    if cfg.timeout_seconds < 10 and total_samples > max(usable_wells // 2, 24):
        warnings.append("The solver timeout is quite short for this design.")
    if cfg.num_threads > 4:
        warnings.append("Higher solver thread counts may increase CPU load on this machine.")

    return {
        "ok": True,
        "errors": [],
        "warnings": warnings,
        "summary": summary,
    }
