# PLAID_Core API Reference

Complete Python API documentation for PLAID_Core package.

## Core Classes

### PlateDesigner

Main interface for generating microplate layouts.

```python
from plaid_core import PlateDesigner, PlateConfig, Compound, Control

designer = PlateDesigner(minizinc_path=None)
```

#### Methods

##### `design(config: PlateConfig) -> Layout`

Generate a microplate layout.

```python
config = PlateConfig(plate_rows=8, plate_cols=12, ...)
layout = designer.design(config)
```

**Args:**
- `config` (PlateConfig): Configuration object with design parameters

**Returns:**
- `Layout`: Generated layout object

**Raises:**
- `ValidationError`: If configuration is invalid
- `SolverError`: If solver fails
- `NoSolutionFoundError`: If no valid layout exists
- `TimeoutError`: If solver exceeds timeout

**Example:**
```python
layout = designer.design(config)
print(layout.summary())
```

---

##### `load_config_from_json(json_path: str) -> PlateConfig`

Load configuration from JSON file.

**Args:**
- `json_path` (str): Path to JSON config file

**Returns:**
- `PlateConfig`: Configuration object

**Example:**
```python
config = designer.load_config_from_json("config.json")
layout = designer.design(config)
```

---

##### `save_config_to_json(config: PlateConfig, json_path: str) -> None`

Save configuration to JSON file.

**Args:**
- `config` (PlateConfig): Configuration object
- `json_path` (str): Output file path

**Example:**
```python
designer.save_config_to_json(config, "my_config.json")
```

---

### PlateConfig

Configuration object specifying plate design parameters.

```python
from plaid_core import PlateConfig, Compound, Control

config = PlateConfig(
    plate_rows=8,
    plate_cols=12,
    empty_edge=1,
    compounds=[...],
    controls=[...],
    concentrations_on_different_rows=True,
    concentrations_on_different_columns=True,
    replicates_on_same_plate=True,
    timeout_seconds=10,
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| **Plate Configuration** | | | |
| `plate_rows` | int | Required | Number of plate rows (e.g., 8 for 96-well) |
| `plate_cols` | int | Required | Number of plate columns (e.g., 12 for 96-well) |
| `empty_edge` | int | 1 | Rows/columns to exclude from edges (0-2 typical) |
| `horizontal_cell_lines` | int | 1 | Number of horizontal divisions |
| `vertical_cell_lines` | int | 1 | Number of vertical divisions |
| **Compounds & Controls** | | | |
| `compounds` | List[Compound] | [] | List of compound definitions |
| `controls` | List[Control] | [] | List of control definitions |
| **Basic Distribution Constraints** | | | |
| `concentrations_on_different_rows` | bool | True | Force concentrations to different rows |
| `concentrations_on_different_columns` | bool | True | Force concentrations to different columns |
| `replicates_on_same_plate` | bool | True | Keep all replicates on same plate |
| `replicates_on_different_plates` | bool | False | Spread replicates across multiple plates |
| `allow_empty_wells` | bool | True | Allow unused wells in plate |
| **Advanced Control Constraints** | | | |
| `balance_controls_inside_plate` | bool | True | Balance controls evenly within each plate |
| `interconnected_plates` | bool | True | Connect plates for global distribution optimization |
| `control_slack` | int | 0 | Slack for control distribution (higher = more flexible, 0-5 typical) |
| `force_spread_controls` | bool | False | Force controls to use proven spread bounds |
| **Advanced Compound Constraints** | | | |
| `force_spread_concentrations` | bool | False | Force concentration spreading using proven bounds |
| **Solver Configuration** | | | |
| `timeout_seconds` | int | 10 | Solver timeout in seconds (5-60 typical) |
| `num_threads` | int | 10 | Number of solver threads (≤ CPU cores) |
| `random_seed` | Optional[int] | None | Random seed for reproducible design (None = random) |
| **Testing & Debug** | | | |
| `testing` | bool | False | Enable testing mode debug output |
| `sorted_compounds` | Optional[bool] | None | Optional: force compound sorting (None = auto) |

#### Properties

##### `total_samples: int`

Total number of sample wells needed across all compounds and controls.

```python
total = config.total_samples
```

---

##### `usable_wells_per_plate: int`

Number of available wells per plate (after excluding edges).

```python
available = config.usable_wells_per_plate
```

---

##### `plate_name: str`

Human-readable plate format name.

```python
name = config.plate_name  # "96-well", "384-well", etc.
```

---

### Compound

Specifies a single compound with concentrations and replicates.

```python
from plaid_core import Compound

compound = Compound(
    name="Drug_A",
    concentrations=3,
    replicates=5,
    concentration_names=["Low", "Medium", "High"]
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | Required | Compound identifier |
| `concentrations` | int | Required | Number of concentration levels |
| `replicates` | int | Required | Number of replicates per concentration |
| `concentration_names` | Optional[List[str]] | Auto-generated | Names for each concentration level |

---

### Control

Specifies a single control with concentration levels and replicates.

```python
from plaid_core import Control

control = Control(
    name="Positive_Control",
    concentration_levels=1,
    replicates=6,
    concentration_names=["100"]
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | Required | Control identifier |
| `concentration_levels` | int | Required | Number of concentration levels (usually 1) |
| `replicates` | int | Required | Number of replicates |
| `concentration_names` | Optional[List[str]] | Auto-generated | Names for each concentration |

---

### Layout

Represents generated microplate layout.

```python
layout = designer.design(config)
```

#### Methods

##### `to_dataframe() -> pd.DataFrame`

Convert layout to pandas DataFrame.

**Returns:**
- DataFrame with columns: plateID, well, cmpdname, CONCuM, cmpdnum, VOLuL

**Example:**
```python
df = layout.to_dataframe()
print(df.head())
```

---

##### `to_dict() -> Dict`

Convert layout to dictionary.

**Returns:**
- Dict with keys: num_plates, num_wells, wells (list), plate_ids

---

##### `to_json() -> str`

Convert layout to JSON string.

**Example:**
```python
json_str = layout.to_json()
```

---

##### `save_csv(path: str) -> str`

Save layout to CSV file.

**Args:**
- `path` (str): Output file path

**Returns:**
- str: Path to saved file

**Example:**
```python
csv_path = layout.save_csv("layout.csv")
```

---

##### `save_json(path: str) -> str`

Save layout to JSON file.

**Args:**
- `path` (str): Output file path

**Returns:**
- str: Path to saved file

---

##### `get_plate_data(plate_id: str) -> pd.DataFrame`

Get data for specific plate.

**Args:**
- `plate_id` (str): Plate identifier (e.g., 'plate_1')

**Returns:**
- DataFrame with wells for this plate

**Example:**
```python
plate1_df = layout.get_plate_data('plate_1')
```

---

##### `summary() -> str`

Get text summary of layout.

**Returns:**
- Formatted summary string

**Example:**
```python
print(layout.summary())
```

---

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `plate_ids` | List[str] | List of generated plate IDs |
| `num_plates` | int | Number of plates generated |
| `wells` | List[Dict] | List of well data dictionaries |

---

## Exceptions

All exceptions inherit from `PLAIDError`.

```python
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

---

## Advanced Parameters Guide

### Control Distribution

#### `balance_controls_inside_plate` (bool, default=True)
Balances the number of controls within each plate for statistical consistency.
- **True:** Controls evenly distributed within plates
- **False:** May lead to imbalanced distribution

```python
config = PlateConfig(
    # ... other params ...
    balance_controls_inside_plate=True  # Recommended
)
```

#### `interconnected_plates` (bool, default=True)
Connects optimization across all plates for globally optimal distribution.
- **True:** Solver considers all plates together (slower but better quality)
- **False:** Each plate optimized independently (faster, less balanced)

```python
# For global optimization (recommended)
config.interconnected_plates = True

# For independent plate optimization
config.interconnected_plates = False
```

#### `control_slack` (int, default=0, range 0-5)
Flexibility in control distribution constraints.
- **0:** Strict distribution (harder to solve)
- **1-3:** Balanced flexibility
- **4-5:** Very loose distribution (easier to solve)

```python
# Strict control distribution
config1 = PlateConfig(..., control_slack=0)

# Flexible distribution for difficult problems
config2 = PlateConfig(..., control_slack=3)
```

### Advanced Spreading

#### `force_spread_controls` (bool, default=False)
Uses proven mathematical bounds to force control spreading patterns.
- Enables only when `force_spread_concentrations=False`
- May reduce solution space but can speed up solving

```python
# Use proven spreading bounds for controls
config = PlateConfig(..., force_spread_controls=True)
```

#### `force_spread_concentrations` (bool, default=False)
Forces concentrations to use proven spreading bounds.
- May reduce solution space but ensures robust distribution
- Compatible with `force_spread_controls=False`

```python
# Enforce proven concentration spreading
config = PlateConfig(..., force_spread_concentrations=True)
```

### Testing & Debugging

#### `testing` (bool, default=False)
Enables MiniZinc testing mode with debug output.

```python
config = PlateConfig(..., testing=True)
layout = designer.design(config)
# Outputs additional MiniZinc debug information
```

#### `sorted_compounds` (Optional[bool], default=None)
Forces compound sorting strategy.
- **None:** Automatic (default)
- **True:** Compounds sorted during solving
- **False:** No sorting

```python
# Force sorting
config = PlateConfig(..., sorted_compounds=True)
```

---

## Performance Tuning

| Goal | Configuration |
|------|---------------|
| **Fast solve** | `interconnected_plates=False`, `control_slack=3`, `timeout_seconds=10` |
| **Best quality** | `interconnected_plates=True`, `control_slack=0`, `timeout_seconds=30` |
| **Balanced** | `interconnected_plates=True`, `control_slack=1`, `timeout_seconds=15` |
| **Complex problem** | `control_slack=2`, `num_threads=CPU_cores`, `timeout_seconds=60` |
| **Research/Debug** | `testing=True`, `random_seed=42` |

---

## Full Example

```python
from plaid_core import PlateDesigner, PlateConfig, Compound, Control

# Define compounds
compounds = [
    Compound(name="Drug_A", concentrations=3, replicates=4),
    Compound(name="Drug_B", concentrations=3, replicates=4),
]

# Define controls
controls = [
    Control(name="Positive", concentration_levels=1, replicates=6),
    Control(name="Negative", concentration_levels=1, replicates=6),
]

# Create configuration
config = PlateConfig(
    plate_rows=8,
    plate_cols=12,
    empty_edge=1,
    compounds=compounds,
    controls=controls,
    timeout_seconds=10,
)

# Generate layout
designer = PlateDesigner()
layout = designer.design(config)

# Analyze and save
print(layout.summary())
layout.save_csv("my_layout.csv")
layout.save_json("my_layout.json")

# Access data
df = layout.to_dataframe()
print(df.head())
```

---

## Import Patterns

### Basic usage
```python
from plaid_core import PlateDesigner, PlateConfig, Compound, Control
```

### With exceptions
```python
from plaid_core import (
    PlateDesigner,
    PlateConfig,
    NoSolutionFoundError,
    ValidationError,
)
```

### Advanced
```python
import plaid_core as pc

config = pc.PlateConfig(...)
designer = pc.PlateDesigner()
try:
    layout = designer.design(config)
except pc.NoSolutionFoundError:
    print("No solution found")
```
