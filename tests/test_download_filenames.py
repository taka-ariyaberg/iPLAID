"""Tests for iplaid.download_filenames — artifact filename + path builders."""
from pathlib import Path

from iplaid.download_filenames import (
    build_download_filename,
    build_source_prep_output_path,
    find_latest_download_artifact,
)


def test_build_download_filename_standardizes_segments() -> None:
    filename = build_download_filename(
        project_details=("Taka User", "TIMED/CLEO EXP 01"),
        artifact="iDOT protocol",
        extension="csv",
        timestamp="26-04-23-11-22-33",
    )

    assert filename == "iPLAID_Taka_User_TIMED_CLEO_EXP_01_iDOT_protocol_26-04-23-11-22-33.csv"


def test_build_source_prep_output_path_uses_prep_suffix() -> None:
    config = {
        "user_name": "Your Name",
        "protocol_name": "My Protocol",
        "output_timestamp_format": "%y-%m-%d-%H-%M-%S",
    }

    path = build_source_prep_output_path(
        Path("outputs/results"),
        config,
        timestamp="26-04-23-11-22-33",
    )

    assert path.name == "iPLAID_Your_Name_My_Protocol_source_plate_prep_26-04-23-11-22-33.txt"


def test_build_source_prep_output_path_uses_summary_suffix_when_supplied() -> None:
    config = {
        "user_name": "Your Name",
        "protocol_name": "My Protocol",
        "output_timestamp_format": "%y-%m-%d-%H-%M-%S",
    }

    path = build_source_prep_output_path(
        Path("outputs/results"),
        config,
        timestamp="26-04-23-11-22-33",
        source_layout_provided=True,
    )

    assert path.name == "iPLAID_Your_Name_My_Protocol_source_plate_summary_26-04-23-11-22-33.txt"


def test_find_latest_download_artifact_returns_newest_match(tmp_path) -> None:
    older = tmp_path / "iPLAID_Your_Name_My_Protocol_idot_protocol_26-04-22-11-22-33.csv"
    newer = tmp_path / "iPLAID_Your_Name_My_Protocol_idot_protocol_26-04-23-11-22-33.csv"
    older.write_text("old", encoding="utf-8")
    newer.write_text("new", encoding="utf-8")

    latest = find_latest_download_artifact(
        tmp_path,
        artifact="idot_protocol",
        extension=".csv",
        project_details=("Your Name", "My Protocol"),
    )

    assert latest == newer
