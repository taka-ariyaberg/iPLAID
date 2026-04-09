# PLAID_Core Quick Start

This file is kept as a short pointer for developers browsing `src/plaid_core/`.

## Recommended setup path

If you are using this repository:

1. Follow the root [README.md](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/README.md).
2. Install the repo with `pip install -e .`.
3. Install MiniZinc if you want to use the solver.

## Minimal direct usage

```python
from plaid_core import PlateDesigner, PlateConfig, Compound, Control

config = PlateConfig(
    plate_rows=8,
    plate_cols=12,
    compounds=[Compound(name="A", concentrations=3, replicates=3)],
    controls=[Control(name="Ctrl", concentration_levels=1, replicates=3)],
)

layout = PlateDesigner().design(config)
layout.save_csv("my_layout.csv")
```

## Historical note

Earlier versions of this file described a manual "copy PLAID_Core into iPLAID" workflow. That is no longer the recommended path for this repository because `plaid_core` is already bundled here.
