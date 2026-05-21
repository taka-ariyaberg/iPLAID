"""Tests for iplaid.io — config validation and run-output path construction."""
from __future__ import annotations

import pytest

from iplaid.io import build_output_paths, validate_config_dict


# ---- build_output_paths -----------------------------------------------------


def test_output_paths_use_shared_timestamp_for_all_artifacts(tmp_path):
    cfg = {
        "user_name": "Your Name",
        "protocol_name": "My Protocol",
        "dispenser": "idot",
        "output_timestamp_format": "%y-%m-%d-%H-%M-%S",
    }
    paths = build_output_paths(tmp_path, cfg, timestamp="26-04-23-11-22-33")

    assert paths["run_timestamp"] == "26-04-23-11-22-33"
    assert paths["out_idot"].name == "iPLAID_Your_Name_My_Protocol_idot_protocol_26-04-23-11-22-33.csv"
    assert paths["out_protocol"] == paths["out_idot"]
    assert paths["out_liquids"].name == "iPLAID_Your_Name_My_Protocol_liquids_map_26-04-23-11-22-33.csv"


def test_output_paths_use_dispenser_name_in_filename(tmp_path):
    cfg = {
        "user_name": "Your Name",
        "protocol_name": "My Protocol",
        "dispenser": "echo",
        "output_timestamp_format": "%y-%m-%d-%H-%M-%S",
    }
    paths = build_output_paths(tmp_path, cfg, timestamp="26-04-23-11-22-33")
    assert paths["out_idot"].name == "iPLAID_Your_Name_My_Protocol_echo_protocol_26-04-23-11-22-33.csv"


# ---- validate_config_dict ---------------------------------------------------


def _full_config() -> dict:
    return {
        "layout_file": "layout.csv",
        "meta_file": "meta.csv",
        "user_name": "tester",
        "protocol_name": "p",
        "sourceplate_type": "S.100 Plate",
        "target_plate_type": "MWP 384",
        "working_volume_ul": 50.0,
        "max_dmso_pct": 0.5,
        "source_prep_overage_pct": 0.1,
        "min_pipette_volume_uL": 1.0,
        "dilution_solvent": "DMSO",
        "source_well_fill_pct": 0.8,
        "standard_prep_volume_uL": 50,
        "output_timestamp_format": "%y-%m-%d-%H-%M-%S",
    }


def test_validate_config_defaults_dispenser_to_idot():
    cfg = _full_config()
    out = validate_config_dict(cfg)
    assert out["dispenser"] == "idot"


def test_validate_config_rejects_missing_required_keys():
    cfg = _full_config()
    del cfg["user_name"]
    with pytest.raises(KeyError, match="user_name"):
        validate_config_dict(cfg)


def test_validate_config_rejects_unknown_dispenser():
    cfg = _full_config()
    cfg["dispenser"] = "not_a_dispenser"
    with pytest.raises(ValueError, match="Invalid dispenser"):
        validate_config_dict(cfg)
