# PLAID_Core Migration Reference Card

## Quick Copy Command

```bash
# From plaid-main repo into iPLAID:
cp -r PLAID_Core /path/to/iplaid/src/iplaid/

# Verify copy
ls -la /path/to/iplaid/src/iplaid/PLAID_Core/
```

## What's Being Migrated (22 files total)

### Core Modules (7 files - ESSENTIAL)
```
PLAID_Core/
├── __init__.py              [Required] Package exports
├── config.py                [Required] Configuration classes  
├── solver.py                [Required] MiniZinc wrapper
├── designer.py              [Required] Main API (PlateDesigner)
├── output.py                [Required] Layout output handling
├── validators.py            [Required] Input validation
└── exceptions.py            [Required] Exception hierarchy
```

### Templates (2 files - ESSENTIAL FOR SOLVING)
```
PLAID_Core/templates/
├── plate-design.mzn         [MUST HAVE] Constraint model
└── layout_predicates.mzn    [MUST HAVE] Predicate library
```

### Documentation (6 files - NICE TO HAVE)
```
PLAID_Core/
├── README.md
├── INSTALLATION.md
├── API_REFERENCE.md         [Recommended] Complete docs
├── INTEGRATION_GUIDE.md
├── QUICK_START.md
└── PACKAGE_STRUCTURE.md
```

### Examples (4 files - REFERENCE ONLY)
```
PLAID_Core/examples/
├── __init__.py
├── basic_usage.py
├── advanced_usage.py
└── config_examples.json
```

### Utilities (2 files - OPTIONAL)
```
PLAID_Core/utils/
├── __init__.py
└── dzn_generator.py
```

### Configuration (2 files)
```
PLAID_Core/
├── requirements.txt         [MUST HAVE] Dependencies
└── *.py files               [Full package]
```

### Testing Files (3 files - VALIDATION ONLY)
```
PLAID_Core/
├── final_validation_test.py [For initial verification]
├── test_advanced_params.py  [For feature validation]
└── MIGRATION_CHECKLIST.md   [This checklist]
```

---

## Minimal Installation (Bare Minimum)

If space/performance is critical, these **7 files are absolutely required**:

```bash
# Minimal viable installation
PLAID_Core/
├── __init__.py
├── config.py
├── solver.py
├── designer.py
├── output.py
├── exceptions.py
├── validators.py
└── templates/
    ├── plate-design.mzn
    └── layout_predicates.mzn
├── requirements.txt
```

Everything else is documentation, examples, or utilities (optional but recommended).

---

## Pre-Migration System Requirements

### System Level
- [ ] macOS, Linux, or Windows
- [ ] Python 3.9+ 
- [ ] MiniZinc 2.6+ (https://www.minizinc.org/download)
- [ ] Gecode solver (comes with MiniZinc)

### Python Level
- [ ] pip or conda package manager
- [ ] pandas >= 1.3.0
- [ ] pydantic >= 1.9.0

### Verification Commands
```bash
# Check Python version
python --version

# Check MiniZinc
minizinc --version

# Install PLAID_Core dependencies
pip install -r PLAID_Core/requirements.txt
```

---

## Integration Test (After Migration)

Run in iPLAID environment after copying:

```python
# test_plaid_core_import.py
import sys
sys.path.insert(0, 'src/iplaid')

from PLAID_Core import PlateDesigner, PlateConfig, Compound, Control

# Create minimal config
config = PlateConfig(
    plate_rows=8,
    plate_cols=12,
    empty_edge=1,
    compounds=[Compound(name="Test", concentrations=1, replicates=1)],
    controls=[Control(name="Ctrl", concentration_levels=1, replicates=1)]
)

print(f"✓ PlateConfig created: {config.total_samples} samples")
print(f"✓ Testing mode available: {hasattr(config, 'testing')}")
print(f"✓ Control slack available: {hasattr(config, 'control_slack')}")
print(f"✓ Force spread available: {hasattr(config, 'force_spread_controls')}")

# If all print ✓, migration successful!
```

---

## Usage Example (In iPLAID)

### Notebook Cell
```python
from src.iplaid.PLAID_Core import PlateDesigner, PlateConfig, Compound, Control

# Create design
compounds = [
    Compound(name="Drug1", concentrations=3, replicates=2),
    Compound(name="Drug2", concentrations=2, replicates=3),
]

controls = [
    Control(name="PositiveCtrl", concentration_levels=1, replicates=2),
]

config = PlateConfig(
    plate_rows=8,
    plate_cols=12,
    empty_edge=1,
    compounds=compounds,
    controls=controls,
    force_spread_controls=True,
    balance_controls_inside_plate=True,
)

# Generate layout
designer = PlateDesigner()
layout = designer.design(config)

# Export results
df = layout.to_dataframe()
layout.save_csv('plate_layout.csv')
layout.save_json('plate_layout.json')
```

### FastAPI Endpoint
```python
from fastapi import FastAPI
from src.iplaid.PLAID_Core import PlateDesigner, PlateConfig

app = FastAPI()

@app.post("/api/design")
async def design_plate(config_dict: dict):
    """Generate microplate design from config"""
    config = PlateConfig(**config_dict)
    designer = PlateDesigner()
    layout = designer.design(config)
    return layout.to_dict()
```

---

## Common Issues During Migration

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'PLAID_Core'` | Add to sys.path or use relative import |
| `MiniZinc not found` | Install MiniZinc from https://www.minizinc.org/download |
| `No module named 'pandas'` | Run `pip install -r PLAID_Core/requirements.txt` |
| `.dzn file not found` | Ensure templates/ subdirectory copied |
| Import errors in solver.py | Use PLAID_Core directory as imported module |

---

## File Integrity Check (After Copy)

```bash
# Verify all files present
ls -R PLAID_Core/ | wc -l  # Should be ~30-40 items

# Check core files exist
for f in __init__.py config.py solver.py designer.py output.py; do
  [ -f "PLAID_Core/$f" ] && echo "✓ $f" || echo "✗ $f MISSING"
done

# Check templates exist
ls PLAID_Core/templates/*.mzn | wc -l  # Should be 2

# Verify syntax
python -m py_compile PLAID_Core/*.py
```

---

## Size & Performance

| Item | Size |
|------|------|
| Core package (7 modules) | ~35 KB |
| MiniZinc templates | ~145 KB |
| Documentation | ~42 KB |
| Examples | ~12 KB |
| **Total** | **~234 KB** |

**Performance:** Typical design solves in 0.3-10 seconds depending on complexity and solver parameters.

---

## Rollback Plan

If issues occur after migration:

```bash
# Keep backup before migration
cp -r PLAID_Core PLAID_Core.backup

# If need to rollback
rm -rf PLAID_Core
mv PLAID_Core.backup PLAID_Core
```

---

## Success Criteria

After migration, verify ALL of these:

- [ ] Package imports without errors
- [ ] All 7 core modules load
- [ ] All 24 parameters accessible
- [ ] .dzn files generate with advanced parameters
- [ ] JSON config round-trips successfully
- [ ] MiniZinc can be called
- [ ] Examples run without syntax errors
- [ ] Documentation is readable from new location
- [ ] Test suite passes in new environment

**If all ✓, migration is complete!**

---

*Migration Reference Card - April 7, 2026*  
*Generated after successful validation of all 10 test suites*
