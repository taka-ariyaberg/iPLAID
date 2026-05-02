"""Echo dispenser implementation.

Vendor format: single-section CSV, 10 fixed columns. Source wells zero-padded ("A07"),
destination wells unpadded ("B2"). Volumes in nL, multiples of 2.5, written as %.1f.
Encoding: utf-8 (no BOM), line terminator: LF.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .base import DispenserSpec
from . import _register


_WELL_RE = re.compile(r"^([A-Z])(\d+)$")
_LIQUID_RE = re.compile(r"^\[(.*?)\]\[(.*?)\]$")


def _pad_source_well(well: str) -> str:
    """A1 -> A01, B12 -> B12. Always 2-digit number."""
    m = _WELL_RE.match(well)
    if not m:
        raise ValueError(f"Bad well: {well!r}")
    return f"{m.group(1)}{int(m.group(2)):02d}"


def _unpad_dest_well(well: str) -> str:
    """A01 -> A1, B12 -> B12."""
    m = _WELL_RE.match(well)
    if not m:
        raise ValueError(f"Bad well: {well!r}")
    return f"{m.group(1)}{int(m.group(2))}"


def _liquid_name_to_sample_name(liquid_name: str) -> str:
    """[compound][stock_mM] -> compound[stock_mM] (Echo Sample Name format)."""
    m = _LIQUID_RE.match(liquid_name)
    if not m:
        raise ValueError(f"Liquid Name not in [compound][stock] format: {liquid_name!r}")
    return f"{m.group(1)}[{m.group(2)}]"
