# PLAID_Core Package Structure

Complete standalone Python package for microplate layout design. Ready to move into any Python project.

## Directory Structure

```
PLAID_Core/
│
├── README.md                       # Quick start guide
├── INSTALLATION.md                 # Setup & MiniZinc installation
├── API_REFERENCE.md                # Complete Python API documentation
├── INTEGRATION_GUIDE.md            # Integration with iPLAID (step-by-step)
├── requirements.txt                # Python dependencies (pandas, pydantic)
│
├── __init__.py                     # Package initialization
├── config.py                       # PlateConfig, Compound, Control classes
├── designer.py                     # Main PlateDesigner class (entry point)
├── solver.py                       # MiniZincSolver (subprocess wrapper)
├── output.py                       # Layout class (result handling)
├── validators.py                   # Input validation utilities
├── exceptions.py                   # Custom exception classes
│
├── templates/                      # MiniZinc model files
│   ├── plate-design.mzn            # Main constraint model
│   └── layout_predicates.mzn       # Predicate library
│
├── examples/                       # Example scripts & configs
│   ├── __init__.py
│   ├── basic_usage.py              # Simple 96-well design example
│   ├── advanced_usage.py           # Complex 384-well dose-response example
│   └── config_examples.json        # Pre-made design configurations
│
└── utils/                          # Utility modules
    ├── __init__.py
    └── dzn_generator.py            # Generate MiniZinc .dzn files from JSON
```

## Core Modules

| Module | Purpose | Key Classes |
|--------|---------|------------|
| `config.py` | Design parameter definitions | PlateConfig, Compound, Control |
| `designer.py` | Main user interface | PlateDesigner |
| `solver.py` | MiniZinc integration | MiniZincSolver |
| `output.py` | Layout result handling | Layout |
| `validators.py` | Input validation | validate_plate_config() |
| `exceptions.py` | Custom exceptions | PLAIDError, SolverError, etc. |

## Key Features

✅ **Easy-to-use Python API** - Object-oriented interface
✅ **Constraint-based** - Uses MiniZinc + Gecode solver
✅ **Flexible configurations** - 96/384-well plates, multiple constraints
✅ **JSON support** - Save/load designs as JSON
✅ **Multiple output formats** - CSV, DataFrame, JSON
✅ **Well-documented** - API docs, examples, integration guide
✅ **Production-ready** - Error handling, validation, logging-ready

## Quick Usage

```python
from plaid_core import PlateDesigner, PlateConfig, Compound, Control

# Define design
config = PlateConfig(
    plate_rows=8, plate_cols=12,
    compounds=[
        Compound(name="Drug_A", concentrations=3, replicates=3),
        Compound(name="Drug_B", concentrations=3, replicates=3),
    ],
    controls=[
        Control(name="Ctrl", concentration_levels=1, replicates=3)
    ]
)

# Generate layout
designer = PlateDesigner()
layout = designer.design(config)

# Save outputs
layout.save_csv("layout.csv")
print(layout.summary())
```

## Integration Modes

1. **Standalone Python Package** - Use directly in any project
2. **Web API Backend** - Deploy via FastAPI (see INTEGRATION_GUIDE.md)
3. **Jupyter Notebook** - Interactive analysis & design
4. **CLI Tool** - Command-line design generation

## Dependencies

| Package | Purpose | Min Version |
|---------|---------|------------|
| pandas | Data handling | 1.3.0 |
| pydantic | Validation | 1.9.0 |
| MiniZinc | Solver backend | 2.6.0 (external) |

External dependency: **MiniZinc 2.6+** must be installed separately from https://www.minizinc.org/

## Import Organization

```python
# Main interface
from plaid_core import PlateDesigner, PlateConfig, Compound, Control, Layout

# With exceptions
from plaid_core import PlateDesigner, NoSolutionFoundError, ValidationError

# Specific imports
from plaid_core.config import PlateConfig
from plaid_core.solver import MiniZincSolver
from plaid_core.output import Layout

# All exceptions
from plaid_core import (
    PLAIDError,
    ConfigurationError,
    SolverError,
    NoSolutionFoundError,
    TimeoutError,
    LayoutError,
    ValidationError,
)
```

## File Manifest

| File | Lines | Purpose |
|------|-------|---------|
| config.py | ~250 | Data structures |
| designer.py | ~100 | Main public API |
| solver.py | ~200 | MiniZinc wrapper |
| output.py | ~150 | Result handling |
| validators.py | ~80 | Validation logic |
| exceptions.py | ~35 | Exception classes |
| examples/basic_usage.py | ~100 | Basic example |
| examples/advanced_usage.py | ~150 | Advanced example |
| utils/dzn_generator.py | ~150 | Utility tool |
| INSTALLATION.md | ~150 | Setup guide |
| API_REFERENCE.md | ~450 | Complete API docs |
| INTEGRATION_GUIDE.md | ~350 | iPLAID integration |

**Total Python code:** ~900 lines (core modules)
**Total documentation:** ~950 lines

## Usage Patterns

### Pattern 1: Simple Design
```python
config = PlateConfig(plate_rows=8, plate_cols=12, compounds=[...])
layout = PlateDesigner().design(config)
layout.save_csv("output.csv")
```

### Pattern 2: Configuration from JSON
```python
config = designer.load_config_from_json("config.json")
layout = designer.design(config)
```

### Pattern 3: Web API
```python
@app.post("/design")
def design(config_json: dict):
    config = PlateConfigJSON(**config_json).to_config()
    layout = PlateDesigner().design(config)
    return layout.to_dict()
```

### Pattern 4: Error Handling
```python
try:
    layout = designer.design(config)
except NoSolutionFoundError:
    print("Try reducing replicates")
except ValidationError as e:
    print(f"Invalid config: {e}")
```

## Testing

Run examples to verify installation:

```bash
cd PLAID_Core
python examples/basic_usage.py
python examples/advanced_usage.py
```

Both should generate layouts and save CSV/JSON files.

## Next Steps

1. **For iPLAID integration:** See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
2. **For API docs:** See [API_REFERENCE.md](API_REFERENCE.md)
3. **For setup:** See [INSTALLATION.md](INSTALLATION.md)
4. **For examples:** See `examples/` directory

## License

Apache License 2.0 (same as PLAID)
