# iPLAID

**iDOT Protocol Layout & Assay Integration Dispatcher**

iPLAID converts screening layouts into liquid-handler dispense outputs for both **iDOT** (Assay Studio) and **Echo** (acoustic) dispensers. The dispenser is selected from a dropdown in the workbench. iPLAID can:

- use an existing target-layout CSV,
- design a new layout with PLAID_Core,
- accept an optional pre-prepared **source-plate layout CSV** (validated on upload),
- match compounds to stock concentrations,
- normalize solvent-family carrier volumes,
- generate dispenser-specific dispense and liquids CSVs (iDOT or Echo),
- generate an iMETA CSV for downstream run metadata,
- generate source-plate preparation instructions, or — when a source-plate layout is supplied — a source-plate summary instead.

This repository now has one supported setup path for new machines: **Docker**.

## What is in this repo

- `src/iplaid/`: the pipeline that turns a layout + metadata into iDOT outputs.
- `src/plaid_core/`: the bundled plate-layout design engine used by the web designer.
- `backend/`: FastAPI backend for the web workbench.
- `frontend/`: React frontend that is built and served by the backend in Docker.

## Supported setup

### Host requirements

You only need:

- Docker
- Docker Compose v2 (`docker compose`)

You do **not** need to install Python, Node.js, Conda, npm, or MiniZinc on the host machine for normal iPLAID usage.

### What the Docker image includes

The Docker image builds and runs:

- the FastAPI backend,
- the production frontend bundle,
- all Python dependencies,
- MiniZinc for the PLAID designer.

## Quick start

Build the image:

```bash
docker compose build
```

Start iPLAID:

```bash
docker compose up
```

Then open:

- `http://127.0.0.1:8000`

Useful commands:

```bash
docker compose logs -f iplaid
docker compose down
```

If you change code and want the container to pick it up, rebuild:

```bash
docker compose up --build
```

## Persistent data

The compose setup keeps user-editable and generated data on the host:

- `config/` is mounted into the container
- `inputs/` is mounted into the container
- `outputs/` is mounted into the container
- `backend/data/jobs/` is mounted into the container

That means uploaded runs, generated artifacts, and direct pipeline outputs survive container restarts and rebuilds.

## Running the notebook

The Jupyter notebook in `notebooks/` runs the same pipeline interactively and can be started through Docker without installing anything on the host.

Build and start the notebook server:

```bash
docker compose --profile notebook up --build notebook
```

Then open the URL printed in the terminal (e.g. `http://127.0.0.1:8888`). Authentication is disabled, so the browser opens directly. The notebook mounts `config/`, `inputs/`, and `outputs/` from the host, so changes persist after the container stops.

Stop the notebook server:

```bash
docker compose --profile notebook down
```

The notebook and web app are independent — run whichever you need.

## Running the direct pipeline

The web app is the main workflow, but the direct pipeline is still supported through the same Docker setup.

Run the pipeline against `config/config.json` and the files under `inputs/`:

```bash
docker compose run --rm iplaid python scripts/run_pipeline.py
```

Skip source-plate preparation instructions if needed:

```bash
docker compose run --rm iplaid python scripts/run_pipeline.py --skip-source-prep
```

Direct pipeline outputs are written to:

- `outputs/results/`

## Input files

### Layout CSV

The pipeline expects a target-layout CSV with these columns:

| Column | Meaning |
|--------|---------|
| `plateID` or target-plate column | Target plate identifier |
| `well` or target-well column | Target well identifier |
| compound column | Compound name |
| concentration column | Target concentration in µM |

In practice, the loaders normalize common layout column names. `inputs/layouts/compound_layout_example.csv` shows the accepted shape.

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

The direct pipeline reads `config/config.json`. The template lives in `config/config.template.json`.

Minimal example:

```json
{
  "user_name": "YourName",
  "protocol_name": "MyExperiment",
  "layout_file": "compound_layout_example.csv",
  "meta_file": "meta_example.csv",
  "sourceplate_type": "S.100 Plate",
  "target_plate_type": "MWP 384",
  "working_volume_ul": 40,
  "max_dmso_pct": 0.1,
  "source_prep_overage_pct": 0.3,
  "min_pipette_volume_uL": 1.0,
  "dilution_solvent": "DMSO",
  "source_well_fill_pct": 0.7,
  "standard_prep_volume_uL": 1000.0,
  "output_timestamp_format": "%y-%m-%d-%H-%M-%S"
}
```

Important fields:

| Key | Description |
|-----|-------------|
| `layout_file` | File name under `inputs/layouts/` for direct pipeline runs |
| `meta_file` | File name under `inputs/meta/` for direct pipeline runs |
| `sourceplate_type` | Must match a key in the selected dispenser's source plate specs file, for example `data/idot_source_plate_specs.json` or `data/echo_source_plate_specs.json` |
| `target_plate_type` | Must match an entry in `data/target_plate_types.json` |
| `working_volume_ul` | Assay working volume in µL |
| `max_dmso_pct` | Default maximum solvent percentage used when no solvent-specific override is provided |
| `solvent_caps_pct` | Optional per-solvent percentage limits, for example `{ "DMSO": 0.1, "Ethanol": 0.2 }` |

## Web workbench workflow

### Upload workflow

1. Open the app at `http://127.0.0.1:8000`.
2. Upload a layout CSV.
3. Upload a metadata CSV, or build one with the metadata creator.
4. Inspect the previewed plate map.
5. Adjust run settings: pick the **Dispenser** (iDOT / Echo), the **Source plate type** for that dispenser, and optionally upload a **Source plate layout** CSV (`Liquid Name`, `Source Well`, optional `Source Plate`). The upload is validated immediately — invalid CSVs trigger a popup warning and the field stays empty.
6. Submit the run.
7. Review results and download the dispenser-specific protocol CSV, liquids map CSV, iMETA CSV, and either the source-prep TXT or the source-plate summary TXT.

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
  iPLAID_{User}_{Protocol}_{dispenser}_protocol_{yy-mm-dd-hh-mm-ss}.csv
  iPLAID_{User}_{Protocol}_liquids_map_{yy-mm-dd-hh-mm-ss}.csv
  iPLAID_{User}_{Protocol}_imeta_{yy-mm-dd-hh-mm-ss}.csv
  iPLAID_{User}_{Protocol}_source_plate_prep_{yy-mm-dd-hh-mm-ss}.txt
  iPLAID_{User}_{Protocol}_source_plate_summary_{yy-mm-dd-hh-mm-ss}.txt
```

The protocol artifact uses the selected dispenser name, for example
`idot_protocol` or `echo_protocol`. Source-layout uploads switch the source
artifact from preparation instructions to `source_plate_summary`.

### iMETA CSV

Each pipeline run now writes an iMETA CSV from the finalized protocol dispense rows.
It has one row per actual dispense event, including solvent top-ups and solvent-control wells, so it matches the iDOT protocol rather than only the input layout.

The export includes:

- software and protocol provenance,
- target plate and well,
- source plate and well,
- compound and solvent identity,
- compound stock and source-plate concentration,
- dispensed volume rounded the same way as the iDOT protocol CSV,
- working volume and calculated target concentration,
- dispense role: `compound`, `solvent_topup`, or `solvent_control`.

### Web-app outputs

Web-app jobs are isolated under:

```text
backend/data/jobs/<job_id>/
```

with uploaded files, status JSON, and generated artifacts under that job directory.

Completed jobs expose the same run artifacts through the backend: dispenser-specific Protocol CSV, Liquids CSV, iMETA CSV, and either Source Prep TXT or Source Plate Summary TXT.
The UI downloads result files through the backend artifact endpoints rather than from `outputs/results/`.

## Backend API

All endpoints are served by the FastAPI app in `backend/app/main.py`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/bootstrap` | Config template, dispensers, per-dispenser source plate specs, target plate definitions |
| `POST` | `/api/layouts/preview` | Parse and preview an uploaded layout |
| `POST` | `/api/source-layouts/preview` | Schema-validate an uploaded source-plate layout CSV (returns 400 with a user-readable message on invalid format) |
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
├── .dockerignore
├── Dockerfile
├── compose.yml
├── pyproject.toml
└── README.md
```

Key files:

- `Dockerfile`: multi-stage build — `runtime` (web app) and `notebook` targets
- `compose.yml`: operator entrypoint; the `notebook` service requires `--profile notebook`
- `scripts/run_pipeline.py`: direct pipeline runner inside the container
- `src/iplaid/imeta.py`: iMETA CSV export builder
- `notebooks/01_plaid_idot_pipeline.ipynb`: interactive pipeline notebook
- `backend/app/main.py`: API routes and frontend serving
- `frontend/src/services/apiClient.ts`: frontend API wiring

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `docker: command not found` | Docker is not installed | Install Docker Desktop or Docker Engine + Compose |
| `Cannot connect to the Docker daemon` | Docker is installed but not running | Start Docker and rerun `docker compose up --build` |
| `bind: address already in use` on port 8000 | Another process is using port 8000 | Stop the conflicting process or run `IPLAID_PORT=8001 docker compose up` |
| Designer fails unexpectedly | Container image is stale or MiniZinc runtime is unhealthy | Rebuild with `docker compose up --build`; verify with `docker compose run --rm iplaid minizinc --version` |
| Frontend loads but API calls fail | Container is not healthy yet | Check `docker compose logs -f iplaid` and verify `/api/health` |
| Layout preview or run fails with missing compounds | Layout names do not match metadata names | Ensure `cmpdname` matches exactly |
| Pre-flight validation fails | Requested concentrations are infeasible under the DMSO limit | Reduce target concentration or adjust config after reviewing feasibility |
| Code changes do not appear | Running image was not rebuilt | Rerun `docker compose up --build` |

## Notes on bundled PLAID_Core

`src/plaid_core/` is bundled inside this repo. You do not need to copy it in or install it separately — `docker compose build` handles everything.

The docs under `src/plaid_core/` explain the design engine itself (Python API, MiniZinc solver, layout logic). For setup and operation of iPLAID as a whole, this root README is the authoritative source.

## License

MIT. See `LICENSE.md`.
