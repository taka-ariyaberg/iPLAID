# Installation & Setup

## Prerequisites

### 1. MiniZinc Installation (Required)

PLAID_Core requires MiniZinc compiler and Gecode solver.

#### macOS
```bash
# Download from https://www.minizinc.org/
# Or via Homebrew (if available)
brew install minizinc
```

**Verify installation:**
```bash
minizinc --version
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get install minizinc
```

#### Windows
Download installer from https://www.minizinc.org/

**Add to PATH if needed:**
- macOS: `/Applications/MiniZincIDE.app/Contents/Resources/minizinc`
- Linux: Usually automatic via package manager
- Windows: Usually automatic via installer

### 2. Python Installation

Requires Python 3.9 or later.

### 3. Install PLAID_Core Package

#### Option A: From Local Directory (Development)
```bash
cd path/to/PLAID_Core
pip install -e .
```

#### Option B: Direct Requirements Installation
```bash
pip install -r requirements.txt
```

**Or individual packages:**
```bash
pip install pandas>=1.3.0
pip install pydantic>=1.9.0
```

## Verification

**Test MiniZinc:**
```bash
minizinc --version
minizinc --solvers  # Should show 'Gecode' in list
```

**Test Python package:**
```python
from plaid_core import PlateDesigner, PlateConfig
print("PLAID_Core imported successfully")
```

**Run example:**
```bash
python examples/basic_usage.py
```

## Troubleshooting

### "minizinc: command not found"
- **macOS:** Add to `.zshrc` or `.bash_profile`:
  ```bash
  export PATH="/Applications/MiniZincIDE.app/Contents/Resources:$PATH"
  ```
  Then: `source ~/.zshrc`

- **Linux:** Reinstall: `sudo apt-get install --reinstall minizinc`

- **Windows:** Reinstall and ensure "Add to PATH" option is checked

### "Gecode solver not found"
- Ensure MiniZinc was installed with Gecode
- Verify: `minizinc --solvers` shows Gecode

### Import errors
- Verify Python 3.9+: `python --version`
- Reinstall package: `pip install -e . --force-reinstall`

## Integration with iPLAID

`plaid_core` is already bundled inside iPLAID at `src/plaid_core/` and declared as a package in the root `pyproject.toml`. No separate copy or install step is needed — running `pip install -e .` from the iPLAID project root installs both `iplaid` and `plaid_core` together.

```bash
conda activate PLAID           # the project conda env
pip install -e .               # installs src/iplaid + src/plaid_core
```

**Import:**
```python
from plaid_core import PlateDesigner, PlateConfig
```

## Environment Variables (Optional)

Set MiniZinc path explicitly if not in PATH:
```bash
export MINIZINC_PATH="/path/to/minizinc"
```

Or in Python:
```python
import os
os.environ['MINIZINC_PATH'] = '/path/to/minizinc'
```
