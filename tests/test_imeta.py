"""Tests for iplaid.imeta — build_imeta_dataframe."""
from __future__ import annotations

import pandas as pd
import pytest

from iplaid.imeta import IMETA_COLUMNS, build_imeta_dataframe


def _make_layout_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "plateID": "PB100001",
                "well": "A01",
                "Target Plate": "PB100001",
                "Target Well": "A1",
                "cmpdname": "DMSO",
                "CONCuM": 0.0,
                "stock_conc_mM": 0.0,
                "highest_stock_mM": 0.0,
                "solvent": "DMSO",
                "Volume [uL]": 0.0,
                "Liquid Name": "[DMSO][0.0]",
                "is_solvent_control": True,
            },
            {
                "plateID": "PB100001",
                "well": "B02",
                "Target Plate": "PB100001",
                "Target Well": "B2",
                "cmpdname": "NOCODAZOLE",
                "CONCuM": 10.0,
                "stock_conc_mM": 10.0,
                "highest_stock_mM": 100.0,
                "solvent": "DMSO",
                "Volume [uL]": 0.04,
                "Liquid Name": "[NOCODAZOLE][10.0]",
                "is_solvent_control": False,
            },
            {
                "plateID": "PB100001",
                "well": "C03",
                "Target Plate": "PB100001",
                "Target Well": "C3",
                "cmpdname": "DRUG_LOW",
                "CONCuM": 3.0,
                "stock_conc_mM": 10.0,
                "highest_stock_mM": 100.0,
                "solvent": "DMSO",
                "Volume [uL]": 0.012,
                "Liquid Name": "[DRUG_LOW][10.0]",
                "is_solvent_control": False,
            },
        ]
    )


def _make_dispense_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Target Plate": "PB100001",
                "Target Well": "A1",
                "Liquid Name": "[DMSO][0.0]",
                "Volume [uL]": 0.04,
                "Source Plate": "SRC_TEST",
                "Source Well": "A1",
            },
            {
                "Target Plate": "PB100001",
                "Target Well": "B2",
                "Liquid Name": "[NOCODAZOLE][10.0]",
                "Volume [uL]": 0.04,
                "Source Plate": "SRC_TEST",
                "Source Well": "B1",
            },
            {
                "Target Plate": "PB100001",
                "Target Well": "C3",
                "Liquid Name": "[DMSO][0.0]",
                "Volume [uL]": 0.028,
                "Source Plate": "SRC_TEST",
                "Source Well": "A1",
            },
            {
                "Target Plate": "PB100001",
                "Target Well": "C3",
                "Liquid Name": "[DRUG_LOW][10.0]",
                "Volume [uL]": 0.012,
                "Source Plate": "SRC_TEST",
                "Source Well": "C1",
            },
        ]
    )


_CONFIG = {"protocol_name": "TestProtocol", "working_volume_ul": 40.0}


class TestBuildImetaDataframe:
    def test_returns_dataframe_with_expected_columns(self):
        df = build_imeta_dataframe(_make_layout_df(), _make_dispense_rows(), _CONFIG)

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == IMETA_COLUMNS

    def test_row_count_matches_protocol_dispenses(self):
        df = build_imeta_dataframe(_make_layout_df(), _make_dispense_rows(), _CONFIG)

        assert len(df) == len(_make_dispense_rows())

    def test_software_and_protocol_provenance(self):
        df = build_imeta_dataframe(_make_layout_df(), _make_dispense_rows(), _CONFIG)

        assert set(df["software"]) == {"iPLAID"}
        assert set(df["software_version"]) == {"0.1.0"}
        assert set(df["protocol_name"]) == {"TestProtocol"}

    def test_compound_dispense_keeps_layout_target_and_source_details(self):
        dispense_rows = _make_dispense_rows()
        df = build_imeta_dataframe(_make_layout_df(), dispense_rows, _CONFIG)
        row = df.loc[df["compound_name"] == "NOCODAZOLE"].iloc[0]

        # Look up NOCODAZOLE's source plate/well from the same dispense_rows
        # that fed build_imeta_dataframe, rather than hardcoding coords that
        # depend on a specific source-well assignment algorithm.
        nocodazole_dispense = dispense_rows.loc[
            dispense_rows["Liquid Name"].str.startswith("[NOCODAZOLE]")
        ].iloc[0]

        assert row["dispense_role"] == "compound"
        assert row["target_plate"] == "PB100001"
        assert row["target_well"] == "B02"
        assert row["source_plate"] == nocodazole_dispense["Source Plate"]
        assert row["source_well"] == nocodazole_dispense["Source Well"]
        assert row["solvent"] == "DMSO"
        assert row["compound_stock_concentration_mM"] == pytest.approx(100.0)
        assert row["source_plate_concentration_mM"] == pytest.approx(10.0)
        assert row["dispensed_volume_uL"] == pytest.approx(0.04)
        assert row["target_well_volume_uL"] == pytest.approx(40.0)
        assert row["target_concentration_uM"] == pytest.approx(10.0)

    def test_protocol_volume_rounding_matches_idot_csv_precision(self):
        df = build_imeta_dataframe(_make_layout_df(), _make_dispense_rows(), _CONFIG)
        row = df.loc[df["compound_name"] == "DRUG_LOW"].iloc[0]

        assert row["dispensed_volume_uL"] == pytest.approx(0.01)
        assert row["target_concentration_uM"] == pytest.approx(2.5)

    def test_solvent_control_uses_actual_protocol_dispense_volume(self):
        df = build_imeta_dataframe(_make_layout_df(), _make_dispense_rows(), _CONFIG)
        row = df.loc[df["dispense_role"] == "solvent_control"].iloc[0]

        assert row["compound_name"] == "DMSO"
        assert row["target_well"] == "A01"
        assert row["source_well"] == "A1"
        assert row["dispensed_volume_uL"] == pytest.approx(0.04)
        assert row["target_concentration_uM"] == pytest.approx(0.0)

    def test_solvent_topup_rows_are_exported(self):
        df = build_imeta_dataframe(_make_layout_df(), _make_dispense_rows(), _CONFIG)
        row = df.loc[df["dispense_role"] == "solvent_topup"].iloc[0]

        assert row["compound_name"] == "DMSO"
        assert row["solvent"] == "DMSO"
        assert row["target_well"] == "C03"
        assert row["source_plate_concentration_mM"] == pytest.approx(0.0)
        assert row["dispensed_volume_uL"] == pytest.approx(0.03)
        assert row["target_concentration_uM"] == pytest.approx(0.0)

    def test_empty_inputs_return_empty_with_columns(self):
        df = build_imeta_dataframe(
            _make_layout_df().iloc[0:0],
            _make_dispense_rows().iloc[0:0],
            _CONFIG,
        )

        assert len(df) == 0
        assert list(df.columns) == IMETA_COLUMNS

    def test_missing_layout_row_is_blocking_error(self):
        dispense_rows = pd.DataFrame(
            [
                {
                    "Target Plate": "PB100001",
                    "Target Well": "D4",
                    "Liquid Name": "[DMSO][0.0]",
                    "Volume [uL]": 0.04,
                    "Source Plate": "SRC_TEST",
                    "Source Well": "A1",
                }
            ]
        )

        with pytest.raises(ValueError, match="no matching layout row"):
            build_imeta_dataframe(_make_layout_df(), dispense_rows, _CONFIG)
