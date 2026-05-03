# CLAUDE.md — iPLAID

## Project Context
**Name:** iPLAID
**Stack:** Python 3.11, FastAPI, uvicorn, numpy, pandas, Pydantic, React, TypeScript, Vite, MiniZinc, Docker
**Domain:** Lab automation — multi-dispenser liquid-handler protocol generation (iDOT + Echo)

iPLAID (iDOT Protocol Layout & Assay Integration Dispatcher) converts compound screening layouts into liquid-handler dispense outputs. Both **iDOT** (Assay Studio) and **Echo** (acoustic) dispensers are supported through a strategy registry under `src/iplaid/dispensers/`; the user selects the dispenser from a dropdown in the workbench. iPLAID can accept an existing layout CSV or design a new one using PLAID_Core (a constraint-solver-backed layout engine using MiniZinc). It handles compound-to-stock matching, solvent-family carrier volume normalization, and produces the dispenser-specific protocol CSV, liquids map CSV, iMETA CSV, and either source-plate preparation instructions or, when the user uploads their own source-plate layout CSV, a source-plate summary.

---

## Vault Pointer
Primary vault: `/Users/takar834/Documents/UU/TIMED/Tools/Nexus_OV/iPLAID_OV/`
Shared vault:  `/Users/takar834/Documents/UU/TIMED/Tools/Nexus_OV/_Commons_OV/`

---

## Session Start Ritual
1. Read `../Nexus_OV/iPLAID_OV/iPLAID_Home.md` — master index
2. Read `../Nexus_OV/iPLAID_OV/iPLAID_Current.md` — **live focus; trust this over Home.md**
3. Read the most recent file in `../Nexus_OV/iPLAID_OV/Sessions/` for context continuity
4. Skim `../Nexus_OV/_Commons_OV/Commons_Home.md` for cross-project patterns
5. Do NOT re-read the whole repo from scratch — the vault is the cached understanding

---

## Session End Ritual
1. Append a dated note to `../Nexus_OV/iPLAID_OV/Sessions/` using `Templates/iPLAID_Session_Note.md`
2. Update `../Nexus_OV/iPLAID_OV/iPLAID_Current.md` if focus, blockers, or next steps shifted
3. Add to `../Nexus_OV/iPLAID_OV/Decisions/` for any architectural choice made today
4. Escalate generalizable learnings to `../Nexus_OV/_Commons_OV/`

---

## Routing Table — Auto-Trigger Rules

| Situation | Action |
|-----------|--------|
| New feature / change >50 lines | `superpowers` plugin — brainstorm → plan → TDD |
| Frontend UI work (React) | `frontend-design` plugin + `/impeccable` (default) or `/emilkowalski-skill` for interaction-heavy work |
| Pre-commit / pre-PR on non-trivial diffs | `code-review` plugin |
| Auth, crypto, input validation, secrets, deps | `/security-review` — **mandatory** |
| MiniZinc constraint model changes | Extra care — run full regression tests; logic errors are silent |
| Design audit requested | `/impeccable /audit` then `/impeccable /polish` |

---

## Setup

Docker only (no host Python/Node/MiniZinc required):

```bash
docker compose build
docker compose up
```

- App: `http://127.0.0.1:8000`

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
| `data/idot_source_plate_specs.json`, `data/echo_source_plate_specs.json` | Per-dispenser source-plate catalogs read by `load_plate_specs_for_dispenser` |

---

## Known Issues / Gotchas
- MiniZinc is bundled in Docker only — not available on host
- `plaid_core` constraint solver: logic errors produce valid-looking but wrong layouts — always verify output visually
- iDOT protocol header row must use physical plate barcode (not logical name like `plate_1`)
- iMETA CSV rows are generated from finalized protocol dispense rows; keep volume rounding aligned with `format_protocol_volume_ul`
- Dispenser dispatch happens in `pipeline.py` via `get_dispenser(cfg["dispenser"])`; **never** add iDOT- or Echo-specific code outside `src/iplaid/dispensers/{idot,echo}.py` — the shared pipeline must stay dispenser-agnostic
- The optional **Source plate layout** CSV upload runs schema validation at `/api/source-layouts/preview` *before* state goes green; geometry/completeness checks against the chosen plate type still fire later in `output.py`. Don't move geometry checks to the preview endpoint — it doesn't know the run's plate type
- The Dispenser and Source-plate-type fields use the custom `ConfigDropdown` component, not native `<select>` — native dropdowns render as a macOS popover panel which doesn't match the dark UI

---

## Anti-Patterns
- Never load multiple taste/design skills simultaneously
- Never skip superpowers brainstorm on features >50 lines
- Never commit non-trivial diffs without code-review
- Never re-read the full repo from scratch — always start from vault

---

## Reference
Skills and workflow recipes: `~/claude-steroid/skills/` and `~/claude-steroid/workflows/`
