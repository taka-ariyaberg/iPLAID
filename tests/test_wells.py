"""Tests for iplaid.wells — well-address canonicalization."""
from __future__ import annotations

from iplaid.wells import canonical_well_name, compact_well_name


def test_canonical_well_name_pads_columns():
    assert canonical_well_name("B2") == "B02"
    assert canonical_well_name("j6") == "J06"
    assert canonical_well_name("AA3") == "AA03"
    assert canonical_well_name("P24") == "P24"


def test_compact_well_name_removes_padding():
    assert compact_well_name("B02") == "B2"
    assert compact_well_name("J06") == "J6"
    assert compact_well_name("AA03") == "AA3"
