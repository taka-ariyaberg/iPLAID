from fastapi.testclient import TestClient

from src.iplaid.solvents import load_default_caps, default_cap_for
from backend.app.preview import extract_solvent_families
from backend.app.main import app

client = TestClient(app)

META_CSV = b"cmpdname,highest_stock_mM,solvent\nEncorafenib,10,DMSO\nFoo,10,dmso\nBar,10,Water\n"
SRC_CSV = b"cmpdname,conc_mM,solvent,source_plate,source_well\nDMSO,0,DMSO,P,A1\nEncorafenib,10,dmso,P,B1\n"


def test_load_default_caps_has_known_solvents():
    caps = load_default_caps()
    assert caps["dmso"] == 0.1
    assert caps["water"] == 5.0
    assert caps["default"] == 0.1


def test_default_cap_for_normalizes_casing():
    assert default_cap_for("DMSO") == 0.1
    assert default_cap_for("DmSo") == 0.1
    assert default_cap_for("Ethanol") == 0.5


def test_default_cap_for_unknown_falls_back():
    assert default_cap_for("Acetonitrile") == 0.1


def test_extract_families_from_meta_merges_casing():
    fams = extract_solvent_families("meta.csv", META_CSV)
    keys = sorted(f["solventKey"] for f in fams)
    assert keys == ["dmso", "water"]  # DMSO + dmso merged


def test_extract_families_returns_default_caps():
    fams = extract_solvent_families("meta.csv", META_CSV)
    by_key = {f["solventKey"]: f for f in fams}
    assert by_key["dmso"]["defaultCapPct"] == 0.1
    assert by_key["water"]["defaultCapPct"] == 5.0


def test_extract_families_from_source_layout_shape():
    fams = extract_solvent_families("source.csv", SRC_CSV)
    assert sorted(f["solventKey"] for f in fams) == ["dmso"]


def test_solvents_endpoint_returns_families():
    resp = client.post(
        "/api/meta/solvents",
        files={"file": ("meta.csv", META_CSV, "text/csv")},
    )
    assert resp.status_code == 200
    fams = resp.json()["families"]
    assert sorted(f["solventKey"] for f in fams) == ["dmso", "water"]


def test_solvents_endpoint_rejects_missing_solvent_column():
    resp = client.post(
        "/api/meta/solvents",
        files={"file": ("bad.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert resp.status_code == 422
