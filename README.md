# iPLAID

**iDOT Protocol Layout & Assay Integration Dispatcher**

Convert compound screening layouts into iDOT Assay Studio dispense protocols — with automated stock selection, DMSO normalization, source plate preparation recipes, and an interactive web workbench.

---

## What it does

| Step | Description |
|------|-------------|
| **Layout design** | Optionally auto-generate a balanced target-plate layout using the PLAID_Core constraint solver |
| **Stock selection** | Matches each compound/concentration to the best available stock vial |
| **DMSO normalisation** | Adjusts top-up volumes so every target well stays within `max_dmso_pct` |
| **Protocol generation** | Writes iDOT-compatible dispense and liquids CSV files |
| **Source plate prep** | Calculates dilution recipes for every stock well, including volumes and overage |

### Output files (per run)

```
outputs/results/
  {User}_{Protocol}_protocol_{timestamp}.csv          ← iDOT dispense protocol
  {User}_{Protocol}_liquids_{timestamp}.csv           ← compound → source well map
  {User}_{Protocol}_source_plate_prep_{timestamp}.txt ← dilution recipes
```

---

## Quick start

### 1. Environment setup (first time only)

```bash
conda env create -f environment.yml
conda activate PLAID
pip install -e .           # installs src/iplaid and src/plaid_core in editable mode
```

### 2. Prepare inputs

| File | Required columns |
|------|------------------|
| `inputs/layouts/Layout_1.csv` | `Compound`, `Concentration`, `Target Plate`, `Target Well` |
| `inputs/meta/cmpd_info.csv` | `cmpdname`, `highest_stock_mM`, `solvent` |

### 3. Configure

Edit `config/config.json`. At minimum set:

```json
{
  "user_name": "YourName",
  "protocol_name": "MyExperiment",
  "layout_file": "Layout_1.csv",
  "meta_file": "cmpd_info.csv"
}
```

See `config/config.template.json` for every available parameter.

### 4. Run

| Method | Command |
|--------|---------|
| Notebook (recommended) | `jupyter notebook notebooks/01_plaid_idot_pipeline.ipynb` |
| Script | `python scripts/run_pipeline.py` |
| Python API | `from src.iplaid.pipeline import run_pipeline; run_pipeline(project_root=".", include_source_prep=True)` |

---

## Web workbench

An interactive browser UI for designing or uploading layouts, building or uploading compound metadata, visualising plate maps, running the pipeline, and downloading results.

### Install dependencies (first time only)

```bash
conda activate PLAID      # or activate your venv
pip install -e .           # installs src/iplaid + src/plaid_core
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

### Launch

```bash
bash scripts/start_web_app.sh           # starts backend + frontend
bash scripts/start_web_app.sh --open    # same, also opens browser
```

The script checks that all Python packages (`fastapi`, `uvicorn`, `iplaid`, `plaid_core`) and Node modules are installed, installs any that are missing, then starts both services. Press `Ctrl+C` to stop everything.

| Service | URL |
|---------|-----|
| Frontend | http://127.0.0.1:5173 |
| Backend API | http://127.0.0.1:8000 |
| Logs | `outputs/logs/backend-dev.log`, `outputs/logs/frontend-dev.log` |

### Workbench workflow

#### Option A — Upload existing files
1. Drop a **layout CSV** into the Layout upload zone (turns green when loaded)
2. Drop or build a **metadata CSV** in the Metadata column (upload or use the built-in creator)
3. Inspect the rendered plate map in the centre viewer
4. Set pipeline parameters in the Run Configuration panel and click **Run**
5. Review and download results on the Results page

#### Option B — Design with PLAID
1. Click **Design with PLAID** in the Layout column to open the constraint-solver designer
2. Add compounds and controls with their target concentrations (µM) and replicate counts
3. Configure plate geometry and solver settings
4. Click **Generate Layout** — the solver produces a balanced multi-plate assignment
5. Click **Use this layout** to return to the workbench with the designed layout loaded
6. The layout upload zone stays idle; the **Design with PLAID** button turns green to signal the active source
7. Provide a **metadata CSV** separately (upload or use the creator) — it must contain stock concentrations (mM) and solvents, which cannot be inferred from the design step

> **Visual cue system:** In the Input panel, exactly one control per column lights up green at a time — the upload zone if the file came from a CSV upload, or the action button (Design / Create Meta) if the file was produced in the UI. The hero status badge shows **Ready to run** as soon as both a layout and a metadata file are present, regardless of their source.

---

## Metadata CSV format

The metadata CSV (`cmpd_info.csv`) is the same format whether uploaded directly or built with the in-app **Create Meta File** tool.

| Column | Type | Description |
|--------|------|-------------|
| `cmpdname` | string | Compound name — must match names used in the layout CSV exactly |
| `highest_stock_mM` | float ≥ 0 | Highest available stock concentration in mM |
| `solvent` | string | Stock solvent (typically `DMSO`) |

DMSO must always appear as its own row with `highest_stock_mM = 0`. The **Create Meta File** tool adds this row automatically.

---

## Configuration reference

### Core identifiers

| Key | Type | Description |
|-----|------|-------------|
| `user_name` | string | Appears in output filenames |
| `protocol_name` | string | Appears in output filenames |
| `layout_file` | string | Layout CSV filename inside `inputs/layouts/` |
| `meta_file` | string | Compound metadata CSV filename inside `inputs/meta/` |

### Plate types

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `sourceplate_type` | string | `"S.100 Plate"` | Source plate model; must match a key in `data/source_plate_specs.json` |
| `target_plate_type` | string | `"MWP 384"` | Target plate model |

### Volume & DMSO

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `working_volume_ul` | number | `40` | Assay volume per target well (µL) |
| `max_dmso_pct` | number | `0.1` | Maximum DMSO fraction in target well (0.0 – 1.0) |

### Source plate preparation

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `source_prep_overage_pct` | number | `0.30` | Extra volume factor to account for pipetting loss |
| `min_pipette_volume_uL` | number | `1.0` | Minimum pipettable volume; steps below this are flagged |
| `dilution_solvent` | string | `"DMSO"` | Diluent used for stock dilutions |
| `source_well_fill_pct` | number | `0.70` | Fraction of source well capacity to target |
| `standard_prep_volume_uL` | number | `1000.0` | Total prep volume before overage is added |

### Output

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `output_timestamp_format` | string | `"%Y%m%d_%H%M%S"` | Python `strftime` format for file timestamps |

---

## Project structure

```
iPLAID/
├── config/
│   ├── config.json                    # Active configuration (edit this)
│   └── config.template.json           # All parameters with descriptions
├── data/
│   ├── source_plate_specs.json        # Plate capacity & geometry definitions
│   └── target_plate_types.json        # Target plate geometry definitions
├── inputs/
│   ├── layouts/                        # Layout CSVs go here
│   └── meta/                          # Compound metadata CSVs go here
├── notebooks/
│   └── 01_plaid_idot_pipeline.ipynb   # Interactive notebook entry point
├── outputs/
│   ├── logs/                          # Runtime logs
│   └── results/                       # Generated protocols & prep files
├── scripts/
│   ├── run_pipeline.py                # CLI entry point
│   └── start_web_app.sh               # Web app launcher (backend + frontend)
├── src/
│   ├── iplaid/                        # iPLAID pipeline library
│   │   ├── pipeline.py                # Main orchestrator
│   │   ├── loaders.py                 # CSV ingestion & normalisation
│   │   ├── calculations.py            # Stock selection & volume math
│   │   ├── normalization.py           # DMSO normalisation logic
│   │   ├── output.py                  # Protocol building & file writing
│   │   ├── validators.py              # Post-run validation checks
│   │   ├── validators_preflight.py    # Pre-run validation checks
│   │   ├── source_plate_prep.py       # Source plate dilution recipes
│   │   └── log_parser.py             # iDOT export log parsing
│   └── plaid_core/                    # Constraint-solver layout designer
│       ├── designer.py                # PlateDesigner entry point
│       ├── solver.py                  # MiniZinc model interface
│       ├── config.py                  # PlateConfig, Compound, Control dataclasses
│       ├── validators.py              # Pre-solve constraint checks
│       └── output.py                  # Layout → DataFrame / CSV
├── backend/                           # FastAPI backend for the web app
│   ├── app/
│   │   ├── main.py                    # API routes (runs + design endpoints)
│   │   ├── jobs.py                    # Background job runner (pipeline + solver)
│   │   ├── designer.py                # DesignConfigModel → PLAID_Core bridge
│   │   ├── models.py                  # Pydantic request/response models
│   │   └── preview.py                 # Plate preview generation
│   └── requirements.txt
├── frontend/                          # React 19 + TypeScript + Vite web UI
│   └── src/
│       ├── components/
│       │   ├── design/                # Design-mode panels (CompoundPanel, PlateConfigPanel, etc.)
│       │   ├── workbench/             # Input panel, plate viewer, run config, modals
│       │   └── results/               # Results viewer
│       ├── pages/                     # WorkbenchPage, ResultsPage
│       ├── services/                  # apiClient (typed fetch wrappers)
│       ├── utils/                     # colorUtils, etc.
│       └── styles/
├── tests/                             # Pytest unit tests
├── environment.yml                    # Conda environment
├── pyproject.toml                     # Python package metadata (iplaid + plaid_core)
└── README.md
```

---

## Backend API

All endpoints are served at `http://127.0.0.1:8000`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/bootstrap` | Plate specs, config template, source plate definitions |
| `POST` | `/api/layouts/preview` | Parse an uploaded layout CSV and return a well map |
| `POST` | `/api/runs` | Submit a pipeline run (layout + metadata + config) |
| `GET` | `/api/runs/{job_id}` | Poll run status and retrieve results |
| `GET` | `/api/runs/{job_id}/artifacts/{name}` | Download a result file |
| `POST` | `/api/design/validate` | Validate a design config without solving |
| `POST` | `/api/design/solve` | Start a PLAID_Core solver job (async, returns job ID) |
| `GET` | `/api/design/jobs/{job_id}` | Poll solver job status and layout preview |
| `GET` | `/api/design/jobs/{job_id}/artifacts/{name}` | Download the designed layout CSV |

---

## Common workflows

### New compound set

1. Drop your layout CSV into `inputs/layouts/` and your metadata CSV into `inputs/meta/`
2. Set `layout_file` and `meta_file` in `config/config.json`
3. Run the notebook or script

### Tighten DMSO budget

```json
{ "max_dmso_pct": 0.05 }
```

### Change target plate geometry

```json
{ "target_plate_type": "MWP 96" }
```

Available plate types are listed in `data/source_plate_specs.json` and `data/target_plate_types.json`.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Liquid not found in stock` | Compound missing from metadata or name mismatch | Check `cmpdname` in `cmpd_info.csv` matches the layout CSV exactly |
| DMSO % violation in output | Requested concentration exceeds solubility ceiling | Reduce target concentration or increase `max_dmso_pct` |
| `outputs/results/` not found | Directory does not exist | `mkdir -p outputs/results` |
| `config.json` parse error | Invalid JSON | Validate at [jsonlint.com](https://jsonlint.com) |
| `plaid_core` import error | Package not installed | Run `pip install -e .` from project root |
| Solver timeout | Design is too complex for the time budget | Increase `timeout_seconds` in the designer or reduce compound/replicate count |

---

## Modules

### src/iplaid

| Module | Role |
|--------|------|
| `pipeline.py` | Top-level orchestrator; calls all modules in order |
| `io.py` | Config loading, path resolution, plate spec lookup |
| `loaders.py` | Layout & metadata CSV ingestion and column normalisation |
| `calculations.py` | Stock selection heuristics, volume-from-stock math |
| `normalization.py` | DMSO top-up calculation and volume cap enforcement |
| `output.py` | Dispense row building, protocol CSV + liquids CSV writing |
| `validators.py` | Post-generation validation (DMSO limits, export file integrity) |
| `validators_preflight.py` | Pre-run checks (missing compounds, impossible concentrations) |
| `source_plate_prep.py` | Dilution recipe generation for source plate setup |
| `log_parser.py` | Parse iDOT export logs for dispense traceability |

### src/plaid_core

| Module | Role |
|--------|------|
| `designer.py` | `PlateDesigner` — public entry point; wraps solver and output |
| `solver.py` | MiniZinc model interface; translates `PlateConfig` to constraints |
| `config.py` | `PlateConfig`, `Compound`, `Control` dataclasses |
| `validators.py` | Pre-solve constraint checks (well count, replicate feasibility) |
| `output.py` | Converts solved layout to DataFrame / CSV / JSON |

---

## License

MIT — see [LICENSE.md](LICENSE.md)

