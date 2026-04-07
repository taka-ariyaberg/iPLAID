# PLAID_Core: Constraint-Based Microplate Layout Engine

Core Python package for PLAID (Plate Layouts using Artificial Intelligence Design). Wraps the MiniZinc constraint solver to generate optimised microplate layouts.

In the iPLAID web workbench, PLAID_Core powers the **Design with PLAID** feature: the user defines compounds, controls, target concentrations (µM), and replicate counts in the browser; the solver produces a balanced multi-plate well assignment; the resulting layout CSV flows directly into the iPLAID pipeline.

---

## Quick start

```python
from plaid_core.config import PlateConfig, Compound, Control
from plaid_core.designer import PlateDesigner

config = PlateConfig(
    plate_rows=16,
    plate_cols=24,
    empty_edge=1,
    compounds=[
        Compound(name="Compound_A", concentrations=3, replicates=3),
        Compound(name="Compound_B", concentrations=3, replicates=3),
    ],
    controls=[
        Control(name="DMSO", concentration_levels=1, replicates=6)
    ]
)

designer = PlateDesigner()
layout = designer.design(config)

df = layout.to_dataframe()
layout.save_csv("my_layout.csv")
```

---

## Features

- **Multi-concentration support** — each compound can have multiple concentration levels, each with independent replicate counts
- **Control balancing** — controls are spread evenly across the plate; configurable slack and forced-spread options
- **Edge management** — configurable empty border rows/columns to reduce edge effects
- **Concentration spreading** — optionally enforce concentrations on different rows and/or columns
- **Replicate grouping** — keep replicates on the same plate or force them apart
- **Multi-plate scaling** — automatically splits assignments across plates when well count exceeds a single plate
- **Cell-line grid support** — define horizontal and vertical cell-line segments within a plate
- **Solver timeout & threading** — configurable MiniZinc timeout and thread count
- **Output formats** — CSV, DataFrame, JSON

---

## Integration with iPLAID

PLAID_Core is the upstream design stage for the iPLAID pipeline:

```
PLAID_Core (Design with PLAID — browser UI or Python API)
    ↓  outputs layout CSV  (cmpdname, well, plate, concentration_uM)
iPLAID Pipeline (stock selection, DMSO normalisation, iDOT protocol generation)
    ↓
iDOT Assay Studio protocol files
```

**Important:** PLAID_Core only handles well assignments. It has no knowledge of stock concentrations (mM) or solvents. Those must be provided separately via a metadata CSV (`cmpdname`, `highest_stock_mM`, `solvent`) before the iPLAID pipeline can run.

---

## Web workbench (Design with PLAID)

The browser UI exposes PLAID_Core through the backend design API:

| Endpoint | Description |
|----------|-------------|
| `POST /api/design/validate` | Fast pre-solve validation (no MiniZinc call) |
| `POST /api/design/solve` | Start an async solver job; returns a `job_id` |
| `GET /api/design/jobs/{job_id}` | Poll status (`queued` / `running` / `completed` / `failed`) and layout preview |
| `GET /api/design/jobs/{job_id}/artifacts/designed_layout.csv` | Download the solved layout CSV |

The frontend `DesignPanel` (React) drives these endpoints. On completion the user confirms the layout with **Use this layout**, which loads it into the workbench. The metadata CSV must then be provided independently.

---

## Requirements

- Python 3.11+
- MiniZinc 2.6+ (must be installed separately — see [INSTALLATION.md](INSTALLATION.md))
- `pandas`
- `pydantic`

---

## Installation

See [INSTALLATION.md](INSTALLATION.md). For use within the iPLAID project, install with:

```bash
pip install -e /path/to/iPLAID   # installs both src/iplaid and src/plaid_core
```

---

## Documentation

- [API Reference](API_REFERENCE.md) — complete Python API docs
- [INSTALLATION.md](INSTALLATION.md) — setup & MiniZinc dependency
- [examples/basic_usage.py](examples/basic_usage.py) — simple example
- [examples/advanced_usage.py](examples/advanced_usage.py) — complex configurations

---

## License

Apache License 2.0

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


## Quick Start

```python
from plaid_core import PlateDesigner, PlateConfig, Compound, Control

# Define design parameters
config = PlateConfig(
    plate_rows=8,
    plate_cols=12,
    empty_edge=1,
    compounds=[
        Compound(name="Compound_A", concentrations=3, replicates=3),
        Compound(name="Compound_B", concentrations=3, replicates=3),
        Compound(name="Compound_C", concentrations=3, replicates=3),
        Compound(name="Compound_D", concentrations=3, replicates=3),
    ],
    controls=[
        Control(name="Positive_Control", concentration_levels=1, replicates=3)
    ]
)

# Generate layout
designer = PlateDesigner()
layout = designer.design(config)

# Output as DataFrame and CSV
df = layout.to_dataframe()
layout.save_csv("my_layout.csv")
```

## Features

- **Compound Distribution:** Multi-concentration, multi-replicate support
- **Control Balancing:** Automatic control spacing & balancing across plates
- **Edge Management:** Configurable empty borders to reduce edge effects
- **Concentration Spreading:** Separate concentrations across rows/columns
- **Replicate Grouping:** Keep replicates on same or different plates
- **Multi-Plate Support:** Automatic scaling to multiple plates when needed
- **Output Formats:** CSV, DataFrame, JSON

## Installation

See [INSTALLATION.md](INSTALLATION.md)

## Integration with iPLAID

This package is designed to be the upstream design stage for iPLAID:

```
PLAID_Core (design)
    ↓ outputs layout CSV
iPLAID Pipeline (normalize + convert to iDOT)
    ↓
iDOT Protocol
```

## Documentation

- [API Reference](API_REFERENCE.md) - Complete Python API docs
- [INSTALLATION.md](INSTALLATION.md) - Setup & dependencies
- [examples/basic_usage.py](examples/basic_usage.py) - Simple example
- [examples/advanced_usage.py](examples/advanced_usage.py) - Complex configurations

## Requirements

- Python 3.9+
- MiniZinc 2.6+ (must be installed separately)
- pandas
- pydantic

## License

Apache License 2.0 (same as PLAID)

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
