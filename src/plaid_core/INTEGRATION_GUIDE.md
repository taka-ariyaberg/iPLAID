# Integration Guide: PLAID_Core + iPLAID

Step-by-step guide for integrating PLAID_Core into iPLAID project.

## Architecture

```
iPLAID Workflow:

[User Input via UI/Notebook]
        ↓
[PLAID_Core Design Engine] ← NEW (this package)
        ↓
[Generated Layout CSV]
        ↓
[Existing iPLAID Pipeline]
(normalization → format conversion → iDOT protocol)
        ↓
[Output Protocol Files]
```

---

## Integration Steps

### Step 1: Copy PLAID_Core to iPLAID

```bash
# In your iPLAID repo directory
cp -r /path/to/PLAID_Core src/iplaid/plaid_core
```

### Step 2: Update Dependencies

Add to `environment.yml` (or `requirements.txt`):

```yaml
name: iplaid
channels:
  - conda-forge
dependencies:
  - python=3.9
  - pandas
  - pydantic
  # ... existing deps ...
```

Or install with pip:

```bash
pip install -r src/iplaid/plaid_core/requirements.txt
```

### Step 3: In Existing iPLAID Code

#### Option A: Use in Notebook

```python
# In notebooks/01_plaid_idot_pipeline.ipynb

from src.iplaid.plaid_core import PlateDesigner, PlateConfig, Compound, Control

# Define design
config = PlateConfig(
    plate_rows=8, plate_cols=12,
    compounds=[Compound(name="CompA", concentrations=3, replicates=3)],
    controls=[Control(name="Ctrl", concentration_levels=1, replicates=3)]
)

# Generate layout
designer = PlateDesigner()
layout = designer.design(config)

# Save to inputs/ for pipeline
csv_path = layout.save_csv("inputs/layouts/my_design.csv")

# Continue with existing pipeline
# from src.iplaid.pipeline import run_pipeline
# run_pipeline(csv_path)
```

#### Option B: Use in Existing Pipeline

```python
# In src/iplaid/pipeline.py

from plaid_core import PlateDesigner, PlateConfig

def run_pipeline(design_config_path=None, layout_csv_path=None):
    """
    Updated pipeline that can accept pre-generated layouts or design new ones.
    """
    
    # Generate layout if design config provided
    if design_config_path:
        designer = PlateDesigner()
        config = designer.load_config_from_json(design_config_path)
        layout = designer.design(config)
        layout_csv_path = layout.save_csv(f"inputs/layouts/auto_design_{time.time()}.csv")
    
    if not layout_csv_path:
        raise ValueError("Must provide either design_config_path or layout_csv_path")
    
    # Existing pipeline steps
    layout_df = loaders.load_layout_csv(layout_csv_path)
    compounds_meta = loaders.load_compounds_metadata(COMPOUNDS_CSV)
    # ... rest of existing pipeline
```

#### Option C: Use in Web API

```python
# In backend/app/main.py (FastAPI)

from fastapi import FastAPI, HTTPException
from src.iplaid.plaid_core import PlateDesigner, PlateConfig, PlateConfigJSON
import json

app = FastAPI()

@app.post("/api/design")
async def design_plate(config_json: dict):
    """
    POST endpoint to generate a microplate layout.
    
    Body: JSON PlateConfig
    Returns: JSON layout data
    """
    try:
        # Validate JSON
        config_model = PlateConfigJSON(**config_json)
        config = config_model.to_config()
        
        # Generate layout
        designer = PlateDesigner()
        layout = designer.design(config)
        
        # Return layout data
        return {
            "status": "success",
            "num_plates": layout.num_plates,
            "num_wells": len(layout.wells),
            "layout": layout.to_dict()
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/design-and-convert")
async def design_and_convert(config_json: dict):
    """
    Design layout AND convert to iDOT protocol in one call.
    """
    try:
        # Design
        config_model = PlateConfigJSON(**config_json)
        config = config_model.to_config()
        designer = PlateDesigner()
        layout = designer.design(config)
        
        # Save layout CSV
        layout_path = layout.save_csv("outputs/results/temp_layout.csv")
        
        # Convert using existing iPLAID pipeline
        from src.iplaid.pipeline import run_pipeline
        idot_result = run_pipeline(layout_csv_path=layout_path)
        
        return {
            "status": "success",
            "layout": layout.to_dict(),
            "idot_protocol": idot_result
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

#### Option D: Use in React Frontend

```typescript
// In frontend/src/services/designService.ts

export async function designPlate(config: PlateConfig): Promise<Layout> {
    const response = await fetch('/api/design', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    });
    
    if (!response.ok) {
        throw new Error(await response.text());
    }
    
    return response.json();
}

export async function designAndConvert(config: PlateConfig): Promise<{
    layout: Layout,
    idot_protocol: string
}> {
    const response = await fetch('/api/design-and-convert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    });
    
    if (!response.ok) {
        throw new Error(await response.text());
    }
    
    return response.json();
}
```

```jsx
// In frontend/src/pages/WorkbenchPage.tsx

import { designPlate } from '../services/designService';
import PlateGrid from '../components/PlateGrid';

export function DesignTab() {
    const [config, setConfig] = useState(defaultConfig);
    const [layout, setLayout] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    
    async function handleDesign() {
        setLoading(true);
        setError(null);
        try {
            const result = await designPlate(config);
            setLayout(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }
    
    return (
        <div>
            {/* Design configuration UI */}
            <DesignConfigPanel 
                config={config}
                onConfigChange={setConfig}
                onDesign={handleDesign}
                loading={loading}
            />
            
            {error && <ErrorMessage message={error} />}
            {layout && (
                <div>
                    <PlateGrid layout={layout} />
                    <LayoutStats layout={layout} />
                </div>
            )}
        </div>
    );
}
```

---

## Config File Format

Use JSON files to define designs (compatible with PLAID_Core):

```json
{
  "plate_rows": 8,
  "plate_cols": 12,
  "empty_edge": 1,
  "compounds": [
    {
      "name": "Compound_A",
      "concentrations": 3,
      "replicates": 3,
      "concentration_names": ["Low", "Medium", "High"]
    }
  ],
  "controls": [
    {
      "name": "Positive_Control",
      "concentration_levels": 1,
      "replicates": 3
    }
  ],
  "concentrations_on_different_rows": true,
  "concentrations_on_different_columns": true,
  "replicates_on_same_plate": true,
  "timeout_seconds": 10
}
```

Store in `config/design_configs/` directory for your UI to load.

---

## Data Flow

### Via Notebook

```
User Input (Notebook cells)
     ↓
config = PlateDesigner.load_config_from_json()
     ↓
layout = designer.design(config)
     ↓
layout.save_csv() → inputs/layouts/
     ↓
... existing pipeline
```

### Via Web API

```
Frontend Form
     ↓
POST /api/design (JSON config)
     ↓
Designer.design(config)
     ↓
Return layout JSON to frontend
     ↓
PlateGrid visualization
     ↓
User downloads CSV or continues to conversion
```

### Via CLI

```bash
# Design only
python -m src.iplaid.plaid_core.designer config.json

# Design + convert (if implemented)
python scripts/run_pipeline.py --design config.json --output output.csv
```

---

## File Organization in iPLAID

After integration:

```
iPLAID/
├── config/
│   ├── design_configs/          # NEW: Store design JSONs
│   │   ├── simple_96.json
│   │   └── advanced_384.json
│   └── config.json
│
├── inputs/
│   └── layouts/                 # Designs go here (from PLAID_Core)
│
├── src/iplaid/
│   ├── plaid_core/              # NEW: Copy of this package
│   │   ├── __init__.py
│   │   ├── designer.py
│   │   ├── config.py
│   │   └── ...
│   └── pipeline.py              # UPDATED: Accept design inputs
│
└── notebooks/
    └── 01_plaid_idot_pipeline.ipynb  # UPDATED: Add design cells
```

---

## Testing

```python
# tests/test_plaid_integration.py

import pytest
from src.iplaid.plaid_core import PlateDesigner, PlateConfig, Compound, Control

def test_simple_design():
    """Test basic design works."""
    config = PlateConfig(
        plate_rows=8, plate_cols=12, empty_edge=1,
        compounds=[Compound(name="A", concentrations=2, replicates=2)],
        controls=[Control(name="C", concentration_levels=1, replicates=2)]
    )
    
    designer = PlateDesigner()
    layout = designer.design(config)
    
    assert layout.num_plates > 0
    assert len(layout.wells) > 0

def test_pipeline_integration():
    """Test design CSV output integrates with pipeline."""
    config = PlateConfig(...)
    designer = PlateDesigner()
    layout = designer.design(config)
    csv_path = layout.save_csv("test_output.csv")
    
    # Test existing pipeline can read it
    from src.iplaid import loaders
    df = loaders.load_layout_csv(csv_path)
    assert df is not None
```

---

## Performance Considerations

- **Timeout settings:** Increase `timeout_seconds` for complex designs
- **Threads:** Use `num_threads` to match your CPU cores
- **Backend caching:** Cache designer instance to avoid repeated MiniZinc startup

```python
# Singleton pattern
class DesignerService:
    _instance = None
    
    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = PlateDesigner()
        return cls._instance

designer = DesignerService.get()  # Reused across requests
```

---

## Troubleshooting

**"MiniZinc not found"**
- Install from https://www.minizinc.org/
- Ensure in PATH or set MINIZINC_PATH

**"No solution found"**
- Reduce replicates/compounds
- Disable `concentrations_on_different_rows/columns`
- Increase `timeout_seconds`

**Import errors**
- Ensure `src/iplaid/` is in Python path
- Use `from src.iplaid.plaid_core import ...`

---

## Next Steps

1. ✅ Copy PLAID_Core to your repo
2. ✅ Update dependencies
3. ✅ Pick integration option (A, B, C, or D)
4. ✅ Test with simple design
5. ✅ Add to UI/web API
6. ✅ Integrate with existing pipeline
7. ✅ Update documentation

Need help? See [INSTALLATION.md](INSTALLATION.md) and [API_REFERENCE.md](API_REFERENCE.md).
