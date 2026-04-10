# iPLAID

**iDOT Protocol Layout & Assay Integration Dispatcher**

iPLAID converts screening layouts into iDOT Assay Studio dispense outputs. It can:

- use an existing target-layout CSV,
- design a new layout with PLAID_Core,
- match compounds to stock concentrations,
- normalize solvent-family carrier volumes,
- generate iDOT dispense and liquids CSVs,
- generate source-plate preparation instructions.

This README is the main operator guide for setting up and running the project on a new machine.

## What is in this repo

- `src/iplaid/`: the pipeline that turns a layout + metadata into iDOT outputs.
- `src/plaid_core/`: the bundled plate-layout design engine used by the web designer.
- `backend/`: FastAPI backend for the web workbench.
- `frontend/`: React + Vite frontend for the web workbench.

## System requirements

### Required for all usage modes

- Python 3.11+
- `pip`
- `pandas`, `numpy`, and other Python dependencies installed through this repo

### Required for the web workbench

- Node.js + npm

### Required for "Design with PLAID"

- MiniZinc 2.6+ with a working solver such as Gecode

If MiniZinc is missing, the upload-based workflow still works, but the PLAID designer will fail.

## Quick install

### Option A: Conda

```bash
conda env create -f environment.yml
conda activate PLAID
pip install -e .
```

### Option B: Virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
pip install -r backend/requirements.txt
```

### Frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### MiniZinc

Install MiniZinc separately if you want to use the layout designer.

- macOS: `brew install minizinc` or install from `https://www.minizinc.org/`
- Ubuntu/Debian: `sudo apt-get install minizinc`
- Windows: install from `https://www.minizinc.org/`

Verify:

```bash
minizinc --version
minizinc --solvers
```

On macOS, if MiniZinc was installed through the app bundle and is not on `PATH`, the code also checks `/Applications/MiniZincIDE.app/Contents/Resources/minizinc`.

## First-run verification

Run these checks before trying a real workflow:

```bash
python -c "import iplaid, plaid_core; print('Python packages OK')"
cd frontend && npm run build && cd ..
```

If you want to use the designer:

```bash
minizinc --version
```

## Input files

### Layout CSV

The pipeline expects a target-layout CSV with these columns:

| Column | Meaning |
|--------|---------|
| `plateID` or target-plate column | Target plate identifier |
| `well` or target-well column | Target well identifier |
| compound column | Compound name |
| concentration column | Target concentration in µM |

In practice, the loaders normalize common layout column names. The examples under `inputs/layouts/` show the accepted shape.

### Metadata CSV

The metadata CSV must contain:

| Column | Meaning |
|--------|---------|
| `cmpdname` | Compound name; must match the layout compound names exactly |
| `highest_stock_mM` | Highest available stock concentration in mM |
| `solvent` | Solvent family name for that compound |

Every solvent family used by compounds must also exist as its own metadata row with:

- `cmpdname = solvent name`
- `highest_stock_mM = 0`
- `solvent = solvent name`

Example:

```csv
cmpdname,highest_stock_mM,solvent
Etoposide,10,DMSO
VX-11e,5,Ethanol
DMSO,0,DMSO
Ethanol,0,Ethanol
```

The in-app metadata creator handles solvent rows automatically and does not ask the user for a stock value for solvents.
Internally, the design solver still receives these solvent entries as PLAID_Core control objects with one concentration level and replicate counts only. After solving, iPLAID converts them back into solvent rows with `CONCuM = 0` in the exported layout CSV.

## Configuration

The root pipeline uses `config/config.json`. The full template is in [config/config.template.json](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/config/config.template.json).

Minimal example:

```json
{
  "user_name": "YourName",
  "protocol_name": "MyExperiment",
  "layout_file": "Layout_1.csv",
  "meta_file": "cmpd_info.csv",
  "sourceplate_type": "S.100 Plate",
  "target_plate_type": "MWP 384",
  "working_volume_ul": 40,
  "max_dmso_pct": 0.1,
  "source_prep_overage_pct": 0.3,
  "min_pipette_volume_uL": 1.0,
  "dilution_solvent": "DMSO",
  "source_well_fill_pct": 0.7,
  "standard_prep_volume_uL": 1000.0,
  "output_timestamp_format": "%Y%m%d_%H%M%S"
}
```

Important fields:

| Key | Description |
|-----|-------------|
| `layout_file` | File name under `inputs/layouts/` for direct pipeline runs |
| `meta_file` | File name under `inputs/meta/` for direct pipeline runs |
| `sourceplate_type` | Must match a key in `data/source_plate_specs.json` |
| `target_plate_type` | Must match an entry in `data/target_plate_types.json` |
| `working_volume_ul` | Assay working volume in µL |
| `max_dmso_pct` | Default maximum solvent percentage used when no solvent-specific override is provided |
| `solvent_caps_pct` | Optional per-solvent percentage limits, for example `{ "DMSO": 0.1, "Ethanol": 0.2 }` |

## Running iPLAID

### 1. Direct Python pipeline

This is the canonical non-web entrypoint:

```python
from src.iplaid.pipeline import run_pipeline

run_pipeline(project_root=".", include_source_prep=True)
```

This reads:

- `config/config.json`
- `inputs/layouts/<layout_file>`
- `inputs/meta/<meta_file>`

and writes outputs to:

- `outputs/results/`

### 2. Notebook

```bash
jupyter lab
```

Then open:

- `notebooks/01_plaid_idot_pipeline.ipynb`

### 3. Web workbench

Launch both backend and frontend:

```bash
bash scripts/start_web_app.sh
```

On macOS you can also auto-open the browser:

```bash
bash scripts/start_web_app.sh --open
```

The launcher script:

- finds a usable Python interpreter,
- installs missing backend Python packages if needed,
- installs the repo in editable mode if needed,
- installs frontend dependencies if `frontend/node_modules` is missing,
- starts backend on `127.0.0.1:8000`,
- starts frontend on `127.0.0.1:5173`,
- writes logs to `outputs/logs/`.

Services:

| Service | URL |
|---------|-----|
| Frontend | `http://127.0.0.1:5173` |
| Backend API | `http://127.0.0.1:8000` |
| Backend health | `http://127.0.0.1:8000/api/health` |

Logs:

- `outputs/logs/backend-dev.log`
- `outputs/logs/frontend-dev.log`

### Frontend API base URL override

The frontend uses `http://localhost:8000` by default. To point it at another backend, set:

```bash
VITE_API_BASE_URL=http://your-host:8000
```

before running the frontend, or put it in a frontend `.env` file if you are managing the dev server manually.

## Web workbench workflow

### Upload workflow

1. Upload a layout CSV.
2. Upload a metadata CSV, or build one with the metadata creator.
3. Inspect the previewed plate map.
4. Adjust run settings.
5. Submit the run.
6. Review results and download artifacts.

### Design workflow

1. Open **Design with PLAID**.
2. Add compounds with concentration entries, plus any solvent-only wells as replicate counts.
3. Configure plate geometry and solver options.
4. Generate a layout.
5. Accept the designed layout back into the workbench.
6. Provide metadata separately, because the design step does not know stock concentrations; solvent metadata rows should still be present and use `highest_stock_mM = 0`.
7. Run the pipeline.

Notes:

- Solvents in the design panel are replicate-only entries. They do not take a target concentration.
- The UI sends solvent entries to the backend as `solvents`, the backend translates them to PLAID_Core `Control` objects for solving, and the solved layout is translated back into solvent rows for the pipeline.
- Only one design solve runs at a time, and cancelling design mode also cancels the backend solver job.

## Outputs

### Direct pipeline outputs

Direct pipeline runs write to `outputs/results/`:

```text
outputs/results/
  {User}_{Protocol}_protocol_{timestamp}.csv
  {User}_{Protocol}_liquids_{timestamp}.csv
  {User}_{Protocol}_source_plate_prep_{timestamp}.txt
```

### Web-app outputs

Web-app jobs are isolated under:

```text
backend/data/jobs/<job_id>/
```

with uploaded files, status JSON, and generated artifacts under that job directory.

The UI downloads result files through the backend artifact endpoints rather than from `outputs/results/`.

## Backend API

All endpoints are served by the FastAPI app in [backend/app/main.py](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/backend/app/main.py).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/bootstrap` | Config template, source plate specs, target plate definitions |
| `POST` | `/api/layouts/preview` | Parse and preview an uploaded layout |
| `POST` | `/api/runs` | Submit a pipeline run |
| `GET` | `/api/runs/{job_id}` | Poll a pipeline run |
| `GET` | `/api/runs/{job_id}/artifacts/{name}` | Download a pipeline artifact |
| `POST` | `/api/design/validate` | Validate a design config without solving |
| `POST` | `/api/design/solve` | Start a design solve job |
| `GET` | `/api/design/jobs/{job_id}` | Poll a design job |
| `POST` | `/api/design/jobs/{job_id}/cancel` | Cancel a design job |
| `GET` | `/api/design/jobs/{job_id}/artifacts/{name}` | Download a design artifact |

## Project structure

```text
iPLAID/
├── backend/
├── config/
├── data/
├── frontend/
├── inputs/
├── notebooks/
├── outputs/
├── scripts/
├── src/
│   ├── iplaid/
│   └── plaid_core/
├── tests/
├── environment.yml
├── pyproject.toml
└── README.md
```

Key files:

- [src/iplaid/pipeline.py](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/src/iplaid/pipeline.py): direct pipeline entrypoint
- [scripts/start_web_app.sh](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/scripts/start_web_app.sh): launch script for frontend + backend
- [backend/app/main.py](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/backend/app/main.py): API routes
- [frontend/src/services/apiClient.ts](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/frontend/src/services/apiClient.ts): frontend API wiring

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ModuleNotFoundError: iplaid` or `plaid_core` | Repo not installed in environment | Run `pip install -e .` from repo root |
| `minizinc` not found | MiniZinc not installed or not on `PATH` | Install MiniZinc and verify `minizinc --version` |
| Designer fails but upload workflow works | MiniZinc missing or solver unavailable | Install MiniZinc/Gecode; upload workflow does not require the solver |
| Frontend loads but API calls fail | Backend not running or wrong API base URL | Check `http://127.0.0.1:8000/api/health`; verify `VITE_API_BASE_URL` |
| Layout preview or run fails with missing compounds | Layout names do not match metadata names | Ensure `cmpdname` matches exactly |
| Pre-flight validation fails | Requested concentrations are infeasible under the DMSO limit | Reduce target concentration or adjust config after reviewing feasibility |
| Solver timeout | Design is too constrained or too large | Increase `timeout_seconds`, reduce replicate count, or relax constraints |
| Port already in use | Another process is using 5173 or 8000 | Stop the conflicting process or launch the services manually on different ports |

## Notes on bundled PLAID_Core docs

`src/plaid_core/` is already bundled inside this repo. You do not need to copy it into iPLAID or install it as a separate standalone project when working from this repository.

The bundled package docs are intended to explain the design engine itself. For actual setup and operation of this repository, use this root README first.

## License

MIT. See [LICENSE.md](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/LICENSE.md).
