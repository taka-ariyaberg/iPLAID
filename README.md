# iPLAID

**iDOT Protocol Layout & Assay Integration Dispatcher**

Convert compound screening layouts into iDOT Assay Studio dispense protocols — with automated stock selection, DMSO normalization, source plate preparation recipes, and an interactive web workbench.

---

## What it does

| Step | Description |
|------|-------------|
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
conda activate iplaid
pip install -e .           # installs the src/iplaid package in editable mode
```

### 2. Prepare inputs

| File | Columns required |
|------|-----------------|
| `inputs/layouts/Layout_1.csv` | `Compound`, `Concentration`, `Target Plate`, `Target Well` |
| `inputs/meta/cmpd_info.csv` | `Compound ID`, `Stock Concentration`, `DMSO Soluble` |

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

An interactive browser UI for uploading layouts, visualising plate maps, running the pipeline, and downloading results.

### Install dependencies (first time only)

```bash
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

### Launch

```bash
bash scripts/start_web_app.sh           # starts backend + frontend
bash scripts/start_web_app.sh --open    # same, and opens the browser
```

Press `Ctrl+C` to stop both services.

| Service | URL |
|---------|-----|
| Frontend | http://127.0.0.1:5173 |
| Backend API | http://127.0.0.1:8000 |
| Logs | `outputs/logs/backend-dev.log`, `outputs/logs/frontend-dev.log` |

### Workflow

1. Upload a layout CSV and compound metadata CSV on the **Workbench** page
2. Inspect the rendered plate map and compound legend
3. Set pipeline parameters and click **Run**
4. Review the **Results** page — source plate layout, target plate map, and dispense summary
5. Download the three output files directly from the results view

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
│   └── start_web_app.sh               # Web app launcher
├── src/iplaid/                        # Core Python library
│   ├── pipeline.py                    # Main orchestrator
│   ├── io.py                          # Config loading & path resolution
│   ├── loaders.py                     # CSV ingestion & normalisation
│   ├── calculations.py                # Stock selection & volume math
│   ├── normalization.py               # DMSO normalisation logic
│   ├── output.py                      # Protocol building & file writing
│   ├── validators.py                  # Post-run validation checks
│   ├── validators_preflight.py        # Pre-run validation checks
│   ├── log_parser.py                  # Log parsing utilities
│   └── source_plate_prep.py           # Source plate dilution recipes
├── backend/                           # FastAPI backend for the web app
│   ├── app/
│   │   ├── main.py                    # API routes & app factory
│   │   ├── jobs.py                    # Background job runner
│   │   ├── models.py                  # Pydantic request/response models
│   │   └── preview.py                 # Plate preview generation
│   └── requirements.txt
├── frontend/                          # React + TypeScript + Vite web UI
│   └── src/
│       ├── components/                # PlateGrid, workbench panels
│       ├── pages/                     # WorkbenchPage, ResultsPage
│       ├── services/                  # API client
│       └── styles/
├── tests/                             # Pytest unit tests
├── environment.yml                    # Conda environment (Python deps)
├── pyproject.toml                     # Python package metadata
└── README.md
```

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
| `Liquid not found in stock` | Compound missing from metadata or wrong name | Check compound name in `cmpd_info.csv` matches the layout CSV exactly |
| DMSO % violation in output | Requested concentration exceeds solubility ceiling | Reduce target concentration or increase `max_dmso_pct` |
| `outputs/results/` not found | Directory does not exist | `mkdir -p outputs/results` |
| `config.json` parse error | Invalid JSON | Validate at [jsonlint.com](https://jsonlint.com) |

---

## Modules

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

---

## License

MIT — see [LICENSE.md](LICENSE.md)
