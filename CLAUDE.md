# CLAUDE.md — iPLAID

## Project Context
**Name:** iPLAID
**Stack:** Python 3.11, FastAPI, uvicorn, numpy, pandas, Pydantic, React, TypeScript, Vite, MiniZinc, Docker
**Domain:** Lab automation — multi-dispenser liquid-handler protocol generation (iDOT + Echo)

iPLAID converts compound screening layouts into liquid-handler dispense outputs across multiple dispensers. **iDOT** (Assay Studio) and **Echo** (acoustic) dispensers are supported through a strategy registry under `src/iplaid/dispensers/`; the user selects the dispenser from a dropdown in the workbench. *(The name "iPLAID" is historic — it originated as "iDOT Protocol Layout & Assay Integration Dispatcher" when the iDOT was the only target; the tool is now dispenser-agnostic.)* iPLAID can accept an existing layout CSV or design a new one using PLAID_Core (a constraint-solver-backed layout engine using MiniZinc). It handles compound-to-stock matching, solvent-family carrier volume normalization, and produces the dispenser-specific protocol CSV, liquids map CSV, iMETA CSV, and either source-plate preparation instructions or, when the user uploads their own source-plate layout CSV, a source-plate summary.

---

## Vault
- Project: `~/claude-workspace/Nexus_OV/iPLAID_OV/`
- Shared:  `~/claude-workspace/Nexus_OV/_Commons_OV/`

**Save-location rule:** Project-specific work → `iPLAID_OV/`. Cross-project workflow tooling, anything in `~/.claude/` or `~/claude-workspace/claude-steroid/` → `_Commons_OV/`. Applies to Specs, Plans, ADRs.

---

## Session Start
Read `~/claude-workspace/Nexus_OV/iPLAID_OV/iPLAID_Current.md`. That's it. Auto-memory loads MEMORY.md automatically; do not re-read iPLAID_Home.md or Sessions logs unless something forces it.

## Session End
Run `/end-session`. It updates `Current.md`, appends a 5-line note to `Sessions/`, and writes ADRs/Learnings only when warranted.

---

## Agent Model Override Rubric
User agents (`~/.claude/agents/`) have sensible default `model:`. Override at dispatch when:

| Override | When |
|---|---|
| `reviewer` → `model: opus` | Security-critical diffs, auth/crypto, architectural reviews |
| `planner` → `model: sonnet` | Trivial CRUD plan, single-file change, no novel design |
| `executor` → `model: opus` | Plan involves subtle reasoning per step (rare) |

Default models otherwise. Trust the skills — don't add a routing table here.

---

## Setup / Quick Run

Docker only (no host Python/Node/MiniZinc required). Canonical launcher is the wrapper script:

```bash
scripts/start.sh           # build only if image missing, then up
scripts/start.sh --build   # force rebuild (first build ~20–40 min for Gecode/MiniZinc)
scripts/stop.sh            # stop + remove containers (volumes preserved)
```

- App: `http://127.0.0.1:8000`
- After a Docker rebuild, hard-refresh the browser (`Cmd+Shift+R`) to bust the cached frontend bundle.

---

## Key Files
| File | Purpose |
|------|---------|
| `src/iplaid/` | Main pipeline — layout → dispenser-specific output |
| `src/iplaid/dispensers/` | Strategy subpackage; `idot.py` and `echo.py` implement the `Dispenser` Protocol declared in `base.py`; `__init__.py` is the registry |
| `src/plaid_core/` | Plate-layout design engine (MiniZinc constraint solver) |
| `backend/app/main.py` | FastAPI routes (run submission, layout/source-layout previews, design jobs, artifacts) |
| `backend/app/preview.py` | CSV preview/validation helpers (`build_layout_preview_from_upload`, `validate_source_layout_upload`) |
| `frontend/src/pages/WorkbenchPage.tsx` | Top-level workbench page; orchestrates upload, design, run, and warning modals |
| `frontend/src/components/workbench/RunConfigPanel.tsx` | Configuration form (six entry fields + numeric SpinInputs) |
| `frontend/src/components/workbench/ConfigDropdown.tsx` | Custom div/button dropdown used for Dispenser + Source plate type (replaces native `<select>`) |
| `compose.yml` | Docker Compose config |
| `src/iplaid/imeta.py` | iMETA CSV export from finalized protocol dispense rows |
| `src/iplaid/source_plate_layout.py` | Pipette-friendly source-plate well-assignment algorithm. `assign_source_wells(compounds, solvents, geometry) -> AssignmentResult` lays each compound's stocks contiguously on a row in ascending concentration, reserves solvents at the bottom-right, with 3-tier fallback (Phase B same-# clustering → Tier 2 scatter → Tier 3 exclusion). Called only from `output.py:build_liquid_table` when `existing_layout is None` |
| `data/idot_source_plate_specs.json`, `data/echo_source_plate_specs.json` | Per-dispenser source-plate catalogs loaded via `Dispenser.load_plate_specs(project_root)` and exposed in the bootstrap as `source_plate_definitions_by_dispenser`. Geometry (rows/cols) is threaded into the source-plate algorithm via `build_liquid_table(..., source_specs=...)` |
| `data/idot_target_plate_specs.json`, `data/echo_target_plate_specs.json` | Per-dispenser destination-plate catalogs (path on each `DispenserSpec.target_plate_specs_path`); exposed in the bootstrap as `target_plate_definitions_by_dispenser`. Cross-field validated against `cfg["target_plate_type"]` in `_validate_target_plate_against_catalog` (pipeline.py) — single chokepoint for UI/CLI/API |
| `tests/scenarios/` | End-to-end pipeline fixtures (inputs + expected outputs). Subdirs: `idot_basic`, `idot_with_layout`, `echo_basic`, `echo_with_layout`, `tier2_scatter`, `tier3_exclusion`. Each has `layout.csv`, `meta.csv`, `config.json`, optional `source_layout.csv`, and `expected_*.csv` files locked by `tests/test_pipeline_golden.py`. The `tier2_*`/`tier3_*` scenarios are also uploadable in the UI for visual smoke tests |

---

## Known Issues / Gotchas
- MiniZinc is bundled in Docker only — not available on host
- `plaid_core` constraint solver: logic errors produce valid-looking but wrong layouts — always verify output visually
- iDOT protocol header row must use physical plate barcode (not logical name like `plate_1`)
- iMETA CSV rows are generated from finalized protocol dispense rows; keep volume rounding aligned with `format_protocol_volume_ul`
- Dispenser dispatch happens in `pipeline.py` via `get_dispenser(cfg["dispenser"])`; **never** add iDOT- or Echo-specific code outside `src/iplaid/dispensers/{idot,echo}.py` — the shared pipeline must stay dispenser-agnostic
- The optional **Source plate layout** CSV upload runs schema validation at `/api/source-layouts/preview` *before* state goes green; geometry/completeness checks against the chosen plate type still fire later in `output.py`. Don't move geometry checks to the preview endpoint — it doesn't know the run's plate type
- The Dispenser and Source-plate-type fields use the custom `ConfigDropdown` component, not native `<select>` — native dropdowns render as a macOS popover panel which doesn't match the dark UI
- Source-plate algorithm warnings flow on `liquid_table.attrs["scatter_warnings"]` / `["excluded_compounds"]` (pandas sideband), then onto `result["warnings"]` (unified soft+loud list) and `result["excluded_compounds"]` / `result["excluded_target_wells"]` for the frontend. The pipeline filters `all_rows` by liquid-name membership BEFORE the source-well merge in `attach_and_sort_dispense_rows` so Tier 3 exclusions never leak NaN into the protocol — don't move that filter
- Frontend bundle is baked into the Docker image at build time; the `compose.override.yml` (gitignored) only bind-mounts Python. **Rebuild after any frontend change**: `scripts/start.sh --build`, then hard-refresh the browser
- Per-solvent carrier caps in CLI/notebook runs: add `solvent_caps_pct` to `config/config.json` as a map of `{solvent_key: max_pct}` (e.g. `{"dmso": 0.1, "water": 5.0}`) for runs with multiple solvent families. When `null` (default), iPLAID applies the legacy single `max_dmso_pct` to every family. The web workbench writes this map automatically; the CLI/notebook path requires editing the JSON.

---

## Reference
- Skill descriptions: `~/claude-workspace/claude-steroid/skills/`
- Anti-patterns: `~/claude-workspace/claude-steroid/rules/anti-patterns.md`
