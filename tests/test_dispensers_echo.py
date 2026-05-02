"""Echo dispenser unit tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.dispensers.echo import (  # noqa: E402
    _liquid_name_to_sample_name,
    _pad_source_well,
    _unpad_dest_well,
)


def test_pad_source_well_pads_single_digit() -> None:
    assert _pad_source_well("A1") == "A01"
    assert _pad_source_well("B7") == "B07"


def test_pad_source_well_leaves_double_digit() -> None:
    assert _pad_source_well("A12") == "A12"
    assert _pad_source_well("H24") == "H24"


def test_pad_source_well_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        _pad_source_well("BAD")


def test_unpad_dest_well_strips_leading_zero() -> None:
    assert _unpad_dest_well("A01") == "A1"
    assert _unpad_dest_well("B07") == "B7"


def test_unpad_dest_well_leaves_already_unpadded() -> None:
    assert _unpad_dest_well("A1") == "A1"
    assert _unpad_dest_well("H24") == "H24"


def test_liquid_name_to_sample_name() -> None:
    assert _liquid_name_to_sample_name("[gemcitabine][1.0]") == "gemcitabine[1.0]"
    assert _liquid_name_to_sample_name("[dmso][0.0]") == "dmso[0.0]"
