# PLAID_Core

PLAID_Core is the bundled layout-design engine used by iPLAID.

Within this repository, it powers the **Design with PLAID** workflow in the web workbench and can also be used directly from Python.

## Important context

- `plaid_core` is already included in this repo under `src/plaid_core/`.
- When working from this repository, install from the repo root with `pip install -e .`.
- You do not need to copy `PLAID_Core` into iPLAID manually.
- You do need MiniZinc installed separately if you want to solve layouts.

For full repo setup instructions, start with the root [README.md](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/README.md).

## Requirements

- Python 3.11+
- MiniZinc 2.6+
- `pandas`
- `pydantic`

## Install inside this repo

For normal iPLAID usage, Docker handles installation automatically — no manual steps needed. See the root [README.md](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/README.md).

For direct Python scripting outside Docker:

```bash
pip install -e /path/to/iPLAID
```

Verify:

```bash
python -c "import plaid_core; print('plaid_core OK')"
minizinc --version
```

## Basic Python usage

```python
from plaid_core import PlateDesigner, PlateConfig, Compound, Control

config = PlateConfig(
    plate_rows=8,
    plate_cols=12,
    empty_edge=1,
    compounds=[
        Compound(name="Compound_A", concentrations=3, replicates=3),
        Compound(name="Compound_B", concentrations=3, replicates=3),
    ],
    controls=[
        Control(name="DMSO", concentration_levels=1, replicates=6),
    ],
)

designer = PlateDesigner()
layout = designer.design(config)

layout.save_csv("my_layout.csv")
print(layout.summary())
```

## Relationship to iPLAID

PLAID_Core only designs well assignments. It does not know:

- stock concentrations in mM,
- solvents,
- DMSO normalization targets,
- iDOT export rules.

Those are handled by the iPLAID pipeline after a layout has been generated.

## Web workbench usage

The iPLAID backend exposes PLAID_Core through these endpoints:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/design/validate` | Validate a design config without solving |
| `POST /api/design/solve` | Start an async solve job |
| `GET /api/design/jobs/{job_id}` | Poll solver status and preview |
| `GET /api/design/jobs/{job_id}/artifacts/{name}` | Download the designed layout CSV |

The frontend `DesignPanel` uses these endpoints and returns the accepted layout to the workbench.

## Docs in this folder

- [INSTALLATION.md](INSTALLATION.md): MiniZinc and package setup notes
- [API_REFERENCE.md](API_REFERENCE.md): Python API details
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md): how plaid_core wires into the iPLAID backend
- [PACKAGE_STRUCTURE.md](PACKAGE_STRUCTURE.md): directory map
- [QUICK_START.md](QUICK_START.md): minimal usage pointer
- [examples/basic_usage.py](examples/basic_usage.py): basic example
- [examples/advanced_usage.py](examples/advanced_usage.py): advanced example

## License

The contents of `src/plaid_core/` are derived from [pharmbio/plaid](https://github.com/pharmbio/plaid) and are governed by the Apache License 2.0. See [`LICENSES/Apache-2.0.txt`](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/LICENSES/Apache-2.0.txt) for the full license text and [`NOTICE.md`](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/NOTICE.md) for attribution. The rest of the iPLAID repository is MIT-licensed; see the project [`LICENSE.md`](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/LICENSE.md).

## Citation

Original PLAID model:

```bibtex
@article{PLAID2023,
  author = {Francisco Rodríguez, María Andreína and Carreras Puigvert, Jordi and Spjuth, Ola},
  title = {Designing Microplate Layouts Using Artificial Intelligence},
  year = {2023},
  doi = {10.1016/j.ailsci.2023.100073},
  journal = {Artificial Intelligence in the Life Sciences},
  volume = {3}
}
```
