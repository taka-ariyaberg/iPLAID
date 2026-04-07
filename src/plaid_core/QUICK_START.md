# PLAID_Core: Move-and-Integrate Instructions

**This is a self-contained Python package.** Simply copy the entire `PLAID_Core/` directory into your iPLAID project and integrate.

## ⚡ Quick Start (5 minutes)

### 1. Copy to iPLAID

```bash
cp -r PLAID_Core /path/to/iPLAID/src/iplaid/
```

### 2. Install Dependencies

```bash
cd /path/to/iPLAID
pip install -r src/iplaid/plaid_core/requirements.txt
```

** Ensure MiniZinc 2.6+ is installed:** https://www.minizinc.org/

### 3. Test Import

```python
from src.iplaid.plaid_core import PlateDesigner, PlateConfig, Compound, Control
print("✓ PLAID_Core ready!")
```

### 4. Use in Notebook/Code

```python
# Define design
config = PlateConfig(
    plate_rows=8, plate_cols=12,
    compounds=[Compound(name="A", concentrations=3, replicates=3)],
    controls=[Control(name="Ctrl", concentration_levels=1, replicates=3)]
)

# Generate
designer = PlateDesigner()
layout = designer.design(config)

# Save
layout.save_csv("my_layout.csv")
```

---

## 📁 What's Included

```
PLAID_Core/
├── Core Modules (7 files)
│   ├── designer.py          ← Main entry point
│   ├── config.py            ← Design parameters
│   ├── solver.py            ← MiniZinc interface
│   ├── output.py            ← Result handling
│   ├── validators.py        ← Input validation
│   ├── exceptions.py        ← Error types
│   └── __init__.py          ← Package exports
│
├── Templates (constraint models)
│   ├── templates/plate-design.mzn
│   └── templates/layout_predicates.mzn
│
├── Examples & Utilities
│   ├── examples/basic_usage.py        ← Start here
│   ├── examples/advanced_usage.py
│   ├── examples/config_examples.json
│   └── utils/dzn_generator.py
│
├── Documentation (4 guides)
│   ├── README.md                      ← Quick start
│   ├── INSTALLATION.md                ← Setup guide
│   ├── API_REFERENCE.md               ← API docs
│   ├── INTEGRATION_GUIDE.md           ← iPLAID specific
│   └── PACKAGE_STRUCTURE.md           ← This file overview
│
└── requirements.txt                   ← Python deps
```

---

## 🚀 Integration Methods

Pick the one that fits your iPLAID workflow:

### A. Notebook (Simplest)
```python
# In notebooks/01_plaid_idot_pipeline.ipynb
from src.iplaid.plaid_core import PlateDesigner, PlateConfig, Compound, Control

config = PlateConfig(...)
layout = PlateDesigner().design(config)
layout.save_csv("inputs/layouts/my_design.csv")
```

### B. Existing Pipeline (Minimal Change)
```python
# In src/iplaid/pipeline.py
from src.iplaid.plaid_core import PlateDesigner

def run_pipeline(design_config_path=None, layout_csv_path=None):
    if design_config_path:
        designer = PlateDesigner()
        config = designer.load_config_from_json(design_config_path)
        layout = designer.design(config)
        layout_csv_path = layout.save_csv("inputs/layouts/auto_design.csv")
    # ... rest of pipeline
```

### C. Web API (Full Stack)
```python
# In backend/app/main.py
from fastapi import FastAPI
from src.iplaid.plaid_core import PlateDesigner, PlateConfigJSON

app = FastAPI()

@app.post("/api/design")
def design_plate(config_json: dict):
    config = PlateConfigJSON(**config_json).to_config()
    layout = PlateDesigner().design(config)
    return layout.to_dict()
```

---

## 📚 Documentation Reading Order

1. **First time:** [README.md](README.md) (2 min)
2. **Setup issues:** [INSTALLATION.md](INSTALLATION.md) (5 min)
3. **Using the API:** [API_REFERENCE.md](API_REFERENCE.md) (10 min)
4. **iPLAID integration:** [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) (15 min)
5. **Architecture overview:** [PACKAGE_STRUCTURE.md](PACKAGE_STRUCTURE.md) (5 min)

---

## 🔌 Integration Checklist

- [ ] Copy `PLAID_Core/` to `src/iplaid/`
- [ ] Install `pip install -r src/iplaid/plaid_core/requirements.txt`
- [ ] Verify MiniZinc: `minizinc --version`
- [ ] Test import: `from src.iplaid.plaid_core import PlateDesigner`
- [ ] Run example: `python src/iplaid/plaid_core/examples/basic_usage.py`
- [ ] Choose integration method (A, B, C, or D from above)
- [ ] Add design UI/endpoint to your app
- [ ] Connect output to existing pipeline

---

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| "ModuleNotFoundError: plaid_core" | Check import path: `from src.iplaid.plaid_core ...` |
| "minizinc: command not found" | Install MiniZinc from https://www.minizinc.org/ |
| "No solution found" | Try: fewer replicates, fewer compounds, increase timeout |
| Import errors | Run: `pip install -r requirements.txt` |

---

## 📊 Package Stats

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Example scripts | 2 |
| Config examples | 3 |
| Documentation files | 5 |
| Total code lines | ~900 |
| Total docs lines | ~950 |
| MiniZinc model | Included (plate-design.mzn) |

---

## 🎯 Next Steps

### Immediate (this session)
1. Copy to iPLAID
2. Install deps
3. Test import
4. Run examples

### Short-term (this week)
1. Choose integration method
2. Add to web API or notebook
3. Test with real designs
4. Integrate with pipeline

### Medium-term (next week)
1. Build design UI components
2. Add to frontend
3. Full end-to-end testing
4. Documentation updates

---

## 📖 Usage Example

```python
"""Complete workflow: Design → Save → Use"""

from src.iplaid.plaid_core import (
    PlateDesigner, 
    PlateConfig, 
    Compound, 
    Control,
    ValidationError,
    NoSolutionFoundError
)

# Step 1: Define compounds & controls
compounds = [
    Compound(
        name="Drug_A",
        concentrations=3,
        replicates=4,
        concentration_names=["0.1µM", "1µM", "10µM"]
    ),
    Compound(
        name="Drug_B",
        concentrations=3,
        replicates=4,
        concentration_names=["0.1µM", "1µM", "10µM"]
    ),
]

controls = [
    Control(name="Positive", concentration_levels=1, replicates=6),
    Control(name="Negative", concentration_levels=1, replicates=6),
]

# Step 2: Create config
config = PlateConfig(
    plate_rows=8,        # 96-well
    plate_cols=12,
    empty_edge=1,        # Exclude outer rows/cols
    compounds=compounds,
    controls=controls,
    concentrations_on_different_rows=True,
    concentrations_on_different_columns=True,
    replicates_on_same_plate=True,
    timeout_seconds=15,
)

# Step 3: Generate layout
try:
    designer = PlateDesigner()
    layout = designer.design(config)
    
    # Step 4: Output results
    print(layout.summary())
    layout.save_csv("design_output.csv")
    layout.save_json("design_output.json")
    designer.save_config_to_json(config, "design_config.json")
    
    # Step 5: Use layout in pipeline
    df = layout.to_dataframe()
    print(f"Generated {layout.num_plates} plates with {len(df)} wells")
    
except ValidationError as e:
    print(f"Invalid config: {e}")
except NoSolutionFoundError:
    print("No solution found - try reducing complexity")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
```

---

## 📞 Support

- **API docs:** See [API_REFERENCE.md](API_REFERENCE.md)
- **Integration help:** See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
- **Installation issues:** See [INSTALLATION.md](INSTALLATION.md)
- **Example code:** See `examples/` directory

---

**Ready to integrate! Copy PLAID_Core/ to your iPLAID repo and start using it.** 🚀
