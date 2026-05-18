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

> **Use at your own risk.** iPLAID is research software for academic lab automation. Outputs (dispense protocols, source-plate preparation instructions, iMETA CSVs) **must be reviewed against the intended layout before being executed on physical instruments**. Errors in dispense volumes, source-plate assignments, or solvent caps can damage stocks, contaminate plates, waste reagent, or invalidate downstream assay results. iPLAID is provided **as is**, without warranty of any kind; the authors and contributors accept no liability for outcomes — biological, chemical, instrumental, or otherwise — resulting from its use. Verify, then run. See [`LICENSE.md`](LICENSE.md) and [`NOTICE.md`](NOTICE.md) for the full terms and third-party attribution.

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

Start iPLAID with the bundled launcher script:

```bash
scripts/start.sh           # build only if the image is missing, then start
scripts/start.sh --build   # force a rebuild before starting
scripts/start.sh --no-open # skip auto-opening the browser
```

The script runs `docker compose up -d iplaid`, waits for `/api/health` to come up, and opens `http://127.0.0.1:8000` in your default browser. Set `IPLAID_PORT=8001` to use a different port.

Stop iPLAID:

```bash
scripts/stop.sh            # stop and remove containers (volumes preserved)
scripts/stop.sh --volumes  # also remove named volumes
```

Useful commands while running:

```bash
docker compose logs -f iplaid
```

If you change code and want the running container to pick it up, restart with `--build`:

```bash
scripts/stop.sh
scripts/start.sh --build
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

### Source plate layout CSV (optional)

If you have a predesigned source plate, upload a layout CSV instead of metadata — it is a superset and supersedes the metadata file (the two are mutually exclusive). Required columns:

| Column | Meaning |
|--------|---------|
| `cmpdname` | Compound name; must match the layout compound names exactly |
| `conc_mM` | Stock concentration in this source well, in mM |
| `solvent` | Solvent family for that compound; must be consistent across all rows of the same compound |
| `source_plate` | Source plate identifier |
| `source_well` | Well address on the source plate (e.g. `A1`, `B01`) |

Solvent-control wells are rows where `cmpdname == solvent` and `conc_mM == 0`. iPLAID derives `highest_stock_mM` per compound as `max(conc_mM)` across its rows, then runs the same downstream pipeline. Examples are under `inputs/source_plate_layout/`.

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
| `target_plate_type` | Must match an entry in the selected dispenser's target-plate catalog: `data/idot_target_plate_specs.json` (iDOT) or `data/echo_target_plate_specs.json` (Echo) |
| `working_volume_ul` | Assay working volume in µL |
| `max_dmso_pct` | Default maximum solvent percentage used when no solvent-specific override is provided |
| `solvent_caps_pct` | Optional per-solvent percentage limits, for example `{ "DMSO": 0.1, "Ethanol": 0.2 }` |

## Echo destination plates (Plate Type Editor setup)

The Echo dispenser writes the destination plate name verbatim into column 8 of the Echo Cherry Pick CSV. That string **must** match a plate definition in your Echo machine's Plate Type Editor library — otherwise Echo Cherry Pick rejects the file at import.

iPLAID standardises on the naming pattern `<Vendor>_384_<part-number>`. Each entry below has a matching block in [`data/echo_target_plate_specs.json`](data/echo_target_plate_specs.json). To use any of them, open `Tools → Labware Definitions → Add` on your Echo and fill the fields using the table — the **Name** must match the iPLAID id exactly.

> Source for the Plate Type Editor field set: *Echo Cherry Pick User Manual*, Labcyte P/N 001-5723 Rev 2 (Feb 2008), §4.3.2.

### Revvity_384_6007660 *(default)*

Revvity CulturPlate-384, black, TC-treated. ([Revvity TDS](https://resources.revvity.com/pdfs/Technical_Data_Sheet_OptiPlate-384_CulturPlate-384_SpectraPlate-384_AlphaPlate-384(7).pdf), drawing 0PD 384AP-24431.) Run without lid — with lid would exceed Echo's 16 mm height limit.

| Plate Type Editor field | Value |
|---|---|
| Name | `Revvity_384_6007660` |
| Manufacturer | Revvity |
| Part Number | 6007660 |
| Rows / Columns | 16 / 24 |
| A1 X Offset (mm) | 12.13 |
| A1 Y Offset (mm) | 8.99 |
| X / Y Center Spacing (mm) | 4.5 / 4.5 |
| Plate Height (mm) | 14.35 |
| Flange Height (mm) | 2.85 |
| Well Width (mm) | 3.65 |
| Well Capacity (µL) | 110 |

### Greiner_384_781096

Greiner 384-well polystyrene flat-bottom. Echo Cherry Pick already ships a factory plate definition for this part as `Greiner_384PS_781096`; to use the iPLAID-standardised name, select the factory entry in `Tools → Labware Definitions`, click **Copy**, and rename the copy to `Greiner_384_781096` (the geometry is preserved). No re-measurement needed.

| Plate Type Editor field | Value |
|---|---|
| Name | `Greiner_384_781096` |
| Manufacturer | Greiner Bio-One |
| Part Number | 781096 |
| Rows / Columns | 16 / 24 |
| A1 X Offset (mm) | 12.13 |
| A1 Y Offset (mm) | 8.99 |
| X / Y Center Spacing (mm) | 4.5 / 4.5 |
| Plate Height (mm) | 14.4 |
| Flange Height (mm) | 2.85 |
| Well Width (mm) | 3.7 |
| Well Capacity (µL) | 130 |

### Corning_384_3784

Corning 384-well polystyrene flat-bottom. Standard Corning 384-well dimensions listed below; **verify against your specific Corning 3784 datasheet** before committing — this SKU isn't in Corning's current public e-catalog and may be a regional/legacy variant.

| Plate Type Editor field | Value |
|---|---|
| Name | `Corning_384_3784` |
| Manufacturer | Corning |
| Part Number | 3784 |
| Rows / Columns | 16 / 24 |
| A1 X Offset (mm) | 12.13 |
| A1 Y Offset (mm) | 8.99 |
| X / Y Center Spacing (mm) | 4.5 / 4.5 |
| Plate Height (mm) | 14.4 |
| Flange Height (mm) | 2.85 |
| Well Width (mm) | 3.63 |
| Well Capacity (µL) | 112 |

### ibidi_384_88406

ibidi µ-Plate 384 Well Black ibiTreat. Microscopy-grade #1.5 polymer coverslip bottom, black walls, ANSI/SLAS 1-2004 compliant. ([ibidi instruction manual v1.0, 2023-03-02](https://ibidi.com/img/cms/products/labware/plates/P_884XX_Plate_384well/IN_8840X_384well.pdf).) Run **without** lid — with lid the plate is 17.2 mm tall, exceeding Echo's 16 mm limit. Recommended dispense volume is 50 µL (working range 20–100 µL).

| Plate Type Editor field | Value |
|---|---|
| Name | `ibidi_384_88406` |
| Manufacturer | ibidi |
| Part Number | 88406 |
| Rows / Columns | 16 / 24 |
| A1 X Offset (mm) | 12.0 |
| A1 Y Offset (mm) | 9.0 |
| X / Y Center Spacing (mm) | 4.5 / 4.5 |
| Plate Height (mm) | 15.0 |
| Flange Height (mm) | 2.3 |
| Well Width (mm) | 3.4 |
| Well Capacity (µL) | 100 |

### Adding your own plates

To add a 384-well plate not in the catalog above, append a new entry to [`data/echo_target_plate_specs.json`](data/echo_target_plate_specs.json) following the same shape (id = `<Vendor>_384_<part-number>`), then add the matching definition to your Echo Plate Type Editor with identical **Name**. Echo accepts any ANSI/SLAS 1-2004 skirted flat-bottom plate at 8–16 mm height — the named plate definition in Plate Type Editor is what makes Echo Cherry Pick recognise it.

## Web workbench workflow

### Upload workflow

1. Open the app at `http://127.0.0.1:8000`.
2. Upload a layout CSV.
3. Upload a metadata CSV, or build one with the metadata creator.
4. Inspect the previewed plate map.
5. Adjust run settings: pick the **Dispenser** (iDOT / Echo), the **Source plate type** for that dispenser, and optionally upload a **Source plate layout** CSV (`cmpdname, conc_mM, solvent, source_plate, source_well`). When uploaded, it replaces the metadata file (mutual exclusion — the workbench prompts before swapping). The upload is validated immediately; invalid CSVs trigger a popup warning and the field stays empty.
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
- `compose.yml`: docker compose service definitions; the `notebook` service requires `--profile notebook`
- `scripts/start.sh`, `scripts/stop.sh`: launcher / shutdown wrappers around `docker compose` for the web app
- `scripts/run_pipeline.py`: direct pipeline runner inside the container
- `src/iplaid/imeta.py`: iMETA CSV export builder
- `notebooks/iPLAID.ipynb`: interactive pipeline notebook
- `backend/app/main.py`: API routes and frontend serving
- `frontend/src/services/apiClient.ts`: frontend API wiring

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `docker: command not found` | Docker is not installed | Install Docker Desktop or Docker Engine + Compose |
| `Cannot connect to the Docker daemon` | Docker is installed but not running | Start Docker and rerun `scripts/start.sh` |
| `bind: address already in use` on port 8000 | Another process is using port 8000 | Stop the conflicting process or run `IPLAID_PORT=8001 scripts/start.sh` |
| Designer fails unexpectedly | Container image is stale or MiniZinc runtime is unhealthy | Rebuild with `scripts/start.sh --build`; verify with `docker compose run --rm iplaid minizinc --version` |
| Frontend loads but API calls fail | Container is not healthy yet | Check `docker compose logs -f iplaid` and verify `/api/health` |
| Layout preview or run fails with missing compounds | Layout names do not match metadata names | Ensure `cmpdname` matches exactly |
| Pre-flight validation fails | Requested concentrations are infeasible under the DMSO limit | Reduce target concentration or adjust config after reviewing feasibility |
| Code changes do not appear | Running image was not rebuilt | Run `scripts/stop.sh && scripts/start.sh --build` |

## Notes on bundled PLAID_Core

`src/plaid_core/` is bundled inside this repo. You do not need to copy it in or install it separately — `scripts/start.sh --build` handles everything.

The docs under `src/plaid_core/` explain the design engine itself (Python API, MiniZinc solver, layout logic). For setup and operation of iPLAID as a whole, this root README is the authoritative source.

## Credits

iPLAID's *Design with PLAID* step is built on top of [**PLAID** (Plate Layouts using Artificial Intelligence Design)](https://github.com/pharmbio/plaid) by **Maria Andreina Francisco Rodríguez** and **Ola Spjuth** (pharmbio group, Uppsala University). The MiniZinc model and constraint-programming logic in [`src/plaid_core/`](src/plaid_core/) are derived from that project and remain governed by its Apache License 2.0. See [`NOTICE.md`](NOTICE.md) for the full attribution and citation.

If your work uses iPLAID's design step (or PLAID directly), please cite:

> Francisco Rodríguez, M. A.; Carreras Puigvert, J.; Spjuth, O. *Designing Microplate Layouts Using Artificial Intelligence.* Artificial Intelligence in the Life Sciences **3**, 100073 (2023). [doi:10.1016/j.ailsci.2023.100073](https://doi.org/10.1016/j.ailsci.2023.100073)

## License

iPLAID is dual-licensed: `src/plaid_core/` is **Apache License 2.0** (from upstream PLAID); the rest of the repository is **MIT**. See [`LICENSE.md`](LICENSE.md), [`NOTICE.md`](NOTICE.md), and [`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt).
