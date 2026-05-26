from src.iplaid.solvents import load_default_caps, default_cap_for


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
