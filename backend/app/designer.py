"""
Bridge between the DesignConfigModel (Pydantic) and PLAID_Core's PlateDesigner.
Also contains the helper that converts a solved Layout into the layout CSV
that the iPLAID pipeline expects.
"""
from __future__ import annotations

import re
import csv
import io
from typing import TYPE_CHECKING

try:
    from plaid_core.config import Compound, Control, PlateConfig
    from plaid_core.designer import PlateDesigner
    from plaid_core.validators import validate_plate_config
except ImportError:
    from src.plaid_core.config import Compound, Control, PlateConfig
    from src.plaid_core.designer import PlateDesigner
    from src.plaid_core.validators import validate_plate_config
from src.iplaid.wells import canonical_well_name

if TYPE_CHECKING:
    from .models import DesignConfigModel


# ---------------------------------------------------------------------------
# Validation (fast, no solver)
# ---------------------------------------------------------------------------

def validate_design_config(cfg: "DesignConfigModel") -> list[str]:
    """
    Run PLAID_Core's validation checks and return a list of error strings.
    Empty list = all OK.
    """
    errors: list[str] = []
    if not cfg.compounds and not cfg.solvents:
        errors.append("Add at least one compound or solvent.")
        return errors

    compound_names: dict[str, str] = {}
    duplicate_compounds: set[str] = set()
    for compound in cfg.compounds:
        key = compound.name.strip().casefold()
        if not key:
            continue
        if key in compound_names:
            duplicate_compounds.add(compound_names[key])
        else:
            compound_names[key] = compound.name.strip()

    solvent_names: dict[str, str] = {}
    duplicate_solvents: set[str] = set()
    for solvent in cfg.solvents:
        key = solvent.name.strip().casefold()
        if not key:
            continue
        if key in solvent_names:
            duplicate_solvents.add(solvent_names[key])
        else:
            solvent_names[key] = solvent.name.strip()

    overlaps = sorted(
        compound_names[key]
        for key in compound_names.keys() & solvent_names.keys()
    )

    for name in sorted(duplicate_compounds):
        errors.append(f'Compound "{name}" is listed more than once.')
    for name in sorted(duplicate_solvents):
        errors.append(f'Solvent "{name}" is listed more than once.')
    for name in overlaps:
        errors.append(f'"{name}" cannot be used as both a compound and a solvent.')

    if errors:
        return errors

    try:
        plate_cfg = _to_plate_config(cfg)
    except (ValueError, Exception) as exc:
        errors.append(str(exc))
        return errors

    try:
        validate_plate_config(plate_cfg)
    except Exception as exc:
        errors.append(str(exc))

    return errors


# ---------------------------------------------------------------------------
# Solve
# ---------------------------------------------------------------------------

def run_design(cfg: "DesignConfigModel"):
    """
    Run the PLAID_Core solver and return (Layout, plate_config).
    Raises on solver failure.
    """
    plate_cfg = _to_plate_config(cfg)
    designer = PlateDesigner()
    layout = designer.design(plate_cfg)
    return layout, plate_cfg


# ---------------------------------------------------------------------------
# CSV generation
# ---------------------------------------------------------------------------

def layout_to_csv_bytes(layout, cfg: "DesignConfigModel") -> bytes:
    """
    Serialise a Layout to the iPLAID layout CSV format:
        plateID, well, cmpdname, CONCuM, cmpdnum
    Since each (compound, concentration) pair is flattened to a unique internal
    PLAID_Core entry (name suffixed with __c{i} or __solvent), we strip the
    suffix to restore the clean compound name and resolve the µM value.
    """
    df = layout.to_dataframe()

    # Build lookup: internal_name + conc_label → µM value.
    # Compounds use label "Conc_1" (single concentration each).
    # Solvents are exported as pure vehicle rows with 0 µM.
    conc_map: dict[tuple[str, str], float] = {}
    for cmpd in cfg.compounds:
        for i, entry in enumerate(cmpd.conc_entries):
            internal = f"{cmpd.name}__c{i}"
            conc_map[(internal, "Conc_1")] = entry.value_um
    for solvent in cfg.solvents:
        internal = f"{solvent.name}__solvent"
        conc_map[(internal, "Conc_1")] = 0
        conc_map[(internal, f"{internal}_conc_1")] = 0

    _suffix_re = re.compile(r"__c\d+$|__solvent$")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["plateID", "well", "cmpdname", "CONCuM", "cmpdnum"])
    for _, row in df.iterrows():
        internal_name = str(row.get("cmpdname", ""))
        conc_label = str(row.get("CONCuM", ""))
        conc_um = conc_map.get((internal_name, conc_label), conc_label)
        clean_name = _suffix_re.sub("", internal_name)
        writer.writerow([
            row.get("plateID", "plate_1"),
            canonical_well_name(row.get("well", "")),
            clean_name,
            conc_um,
            row.get("cmpdnum", ""),
        ])
    return output.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_plate_config(cfg: "DesignConfigModel") -> PlateConfig:
    """Convert DesignConfigModel → PlateConfig dataclass.

    Each (compound, concentration) pair is flattened to its own PLAID_Core
    Compound with a unique internal name ("name__cN"). Solvents are exported as
    single PLAID_Core controls with one concentration level and a replicate
    count only, which keeps the resulting layout compatible with iPLAID's
    solvent rows (0 µM on the target plate, 0 mM in metadata).
    """
    compounds = [
        Compound(
            name=f"{c.name}__c{i}",
            concentrations=1,
            replicates=entry.replicates,
        )
        for c in cfg.compounds
        for i, entry in enumerate(c.conc_entries)
    ]
    controls = [
        Control(
            name=f"{solvent.name}__solvent",
            concentration_levels=1,
            replicates=solvent.replicates,
        )
        for solvent in cfg.solvents
    ]
    return PlateConfig(
        plate_rows=cfg.plate_rows,
        plate_cols=cfg.plate_cols,
        empty_edge=cfg.empty_edge,
        compounds=compounds,
        controls=controls,
        concentrations_on_different_rows=cfg.concentrations_on_different_rows,
        concentrations_on_different_columns=cfg.concentrations_on_different_columns,
        replicates_on_same_plate=cfg.replicates_on_same_plate,
        replicates_on_different_plates=cfg.replicates_on_different_plates,
        allow_empty_wells=cfg.allow_empty_wells,
        balance_controls_inside_plate=cfg.balance_controls_inside_plate,
        interconnected_plates=cfg.interconnected_plates,
        control_slack=cfg.control_slack,
        force_spread_controls=cfg.force_spread_controls,
        force_spread_concentrations=cfg.force_spread_concentrations,
        horizontal_cell_lines=cfg.horizontal_cell_lines,
        vertical_cell_lines=cfg.vertical_cell_lines,
        timeout_seconds=cfg.timeout_seconds,
        num_threads=cfg.num_threads,
        random_seed=cfg.random_seed,
    )
