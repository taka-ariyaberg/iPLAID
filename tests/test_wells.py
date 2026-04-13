from pathlib import Path
import sys

import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.loaders import normalize_layout_df
from iplaid.wells import canonical_well_name, compact_well_name


def test_canonical_well_name_pads_columns() -> None:
    assert canonical_well_name("B2") == "B02"
    assert canonical_well_name("j6") == "J06"
    assert canonical_well_name("AA3") == "AA03"
    assert canonical_well_name("P24") == "P24"


def test_compact_well_name_removes_padding() -> None:
    assert compact_well_name("B02") == "B2"
    assert compact_well_name("J06") == "J6"
    assert compact_well_name("AA03") == "AA3"


def test_normalize_layout_df_rejects_duplicate_wells_after_normalization() -> None:
    df = pd.DataFrame(
        {
            "plateID": ["plate_1", "plate_1"],
            "well": ["B2", "B02"],
            "cmpdname": ["CmpdA", "CmpdB"],
            "CONCuM": [1, 2],
        }
    )

    with pytest.raises(ValueError, match="duplicate target wells"):
        normalize_layout_df(df)


def test_normalize_layout_df_canonicalizes_wells() -> None:
    df = pd.DataFrame(
        {
            "plateID": ["plate_1", "plate_1"],
            "well": ["B2", "J6"],
            "cmpdname": ["CmpdA", "CmpdB"],
            "CONCuM": [1, 2],
        }
    )

    normalized, _ = normalize_layout_df(df)
    assert normalized["well"].tolist() == ["B02", "J06"]
