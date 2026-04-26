"""iMETA export module for iPLAID."""

from __future__ import annotations

import pandas as pd

from .output import format_protocol_volume_ul

_SOFTWARE = "iPLAID"
_SOFTWARE_VERSION = "0.1.0"

IMETA_COLUMNS = [
    "software",
    "software_version",
    "protocol_name",
    "target_plate",
    "target_well",
    "source_plate",
    "source_well",
    "compound_name",
    "solvent",
    "compound_stock_concentration_mM",
    "source_plate_concentration_mM",
    "dispensed_volume_uL",
    "target_well_volume_uL",
    "target_concentration_uM",
    "dispense_role",
]


def _parse_liquid_name(liquid_name: object) -> tuple[str, float]:
    text = str(liquid_name)
    if not text.startswith("[") or "][" not in text or not text.endswith("]"):
        raise ValueError(f"Liquid Name is not in [Compound][Stock] format: {text}")

    compound, stock_text = text[1:-1].rsplit("][", 1)
    return compound, float(stock_text)


def _protocol_volume_as_float(volume_ul: object) -> float:
    return float(format_protocol_volume_ul(float(volume_ul)))


def build_imeta_dataframe(
    df: pd.DataFrame,
    dispense_rows: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    """
    Build an iMETA export DataFrame from finalized protocol dispense rows.

    Parameters
    ----------
    df:
        Full pipeline layout DataFrame after target and solvent-normalization columns
        have been added.
    dispense_rows:
        Final dispense rows after source wells have been attached. These rows are
        the same rows used to build the iDOT protocol, including solvent top-ups.
    config:
        Pipeline config dict; uses ``protocol_name`` and ``working_volume_ul``.

    Returns
    -------
    pd.DataFrame with IMETA_COLUMNS, one row per protocol dispense event.
    ``target_concentration_uM`` is calculated from the rounded protocol volume.
    """
    if df.empty or dispense_rows.empty:
        return pd.DataFrame(columns=IMETA_COLUMNS)

    protocol_name = str(config.get("protocol_name", ""))
    working_volume_ul = float(config.get("working_volume_ul", 0))

    layout_by_target: dict[tuple[str, str], pd.Series] = {
        (str(row["Target Plate"]), str(row["Target Well"])): row
        for _, row in df.iterrows()
    }

    rows = []
    for _, dispense in dispense_rows.iterrows():
        target_plate = str(dispense["Target Plate"])
        target_well_protocol = str(dispense["Target Well"])
        liquid_name = str(dispense["Liquid Name"])
        liquid_compound, liquid_stock_mM = _parse_liquid_name(liquid_name)
        layout_row = layout_by_target.get((target_plate, target_well_protocol))

        if layout_row is None:
            raise ValueError(
                "Cannot build iMETA export because a protocol dispense row has no "
                f"matching layout row: {target_plate} / {target_well_protocol}"
            )

        protocol_volume_ul = _protocol_volume_as_float(dispense["Volume [uL]"])
        is_layout_liquid = str(layout_row["Liquid Name"]) == liquid_name
        is_solvent_control = bool(layout_row.get("is_solvent_control", False))

        if is_layout_liquid and not is_solvent_control:
            dispense_role = "compound"
            compound_name = str(layout_row["cmpdname"])
            solvent = str(layout_row["solvent"])
            compound_stock_mM = float(layout_row["highest_stock_mM"])
            target_concentration_uM = (
                liquid_stock_mM * 1000.0 * protocol_volume_ul / working_volume_ul
                if working_volume_ul else 0.0
            )
        elif is_layout_liquid and is_solvent_control:
            dispense_role = "solvent_control"
            compound_name = str(layout_row["cmpdname"])
            solvent = str(layout_row["solvent"])
            compound_stock_mM = 0.0
            target_concentration_uM = 0.0
        else:
            dispense_role = "solvent_topup"
            compound_name = liquid_compound
            solvent = liquid_compound
            compound_stock_mM = 0.0
            target_concentration_uM = 0.0

        rows.append({
            "software":                        _SOFTWARE,
            "software_version":                _SOFTWARE_VERSION,
            "protocol_name":                   protocol_name,
            "target_plate":                    target_plate,
            "target_well":                     str(layout_row["well"]),
            "source_plate":                    str(dispense["Source Plate"]),
            "source_well":                     str(dispense["Source Well"]),
            "compound_name":                   compound_name,
            "solvent":                         solvent,
            "compound_stock_concentration_mM": compound_stock_mM,
            "source_plate_concentration_mM":   liquid_stock_mM,
            "dispensed_volume_uL":             protocol_volume_ul,
            "target_well_volume_uL":           working_volume_ul,
            "target_concentration_uM":         target_concentration_uM,
            "dispense_role":                   dispense_role,
        })

    result = pd.DataFrame(rows, columns=IMETA_COLUMNS)
    return result.sort_values(["target_plate", "target_well", "dispense_role"]).reset_index(drop=True)


__all__ = ["build_imeta_dataframe", "IMETA_COLUMNS"]
