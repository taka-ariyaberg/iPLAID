# CLAUDE.md — iPLAID

## Project Context
**Name:** iPLAID
**Stack:** Python 3.11, FastAPI, uvicorn, numpy, pandas, Pydantic, React, TypeScript, Vite, MiniZinc, Docker
**Domain:** Lab automation — iDOT liquid handler protocol generation

iPLAID (iDOT Protocol Layout & Assay Integration Dispatcher) converts compound screening layouts into iDOT Assay Studio dispense outputs. It can accept an existing layout CSV or design a new one using PLAID_Core (a constraint-solver-backed layout engine using MiniZinc). It handles compound-to-stock matching, solvent-family carrier volume normalization, and produces the iDOT dispense + liquids CSVs. Its output (`iPLAID_..._idot_protocol.csv`) is one of three input files consumed by iMETA.

---

## Vault Pointer
Primary vault: `/Users/takar834/Documents/UU/TIMED/Tools/Nexus_OV/iPLAID_OV/`
Shared vault:  `/Users/takar834/Documents/UU/TIMED/Tools/Nexus_OV/_Commons_OV/`

---

## Session Start Ritual
1. Read `../Nexus_OV/iPLAID_OV/Home.md` — master index
2. Read `../Nexus_OV/iPLAID_OV/Current.md` — **live focus; trust this over Home.md**
3. Read the most recent file in `../Nexus_OV/iPLAID_OV/Sessions/` for context continuity
4. Skim `../Nexus_OV/_Commons_OV/Home.md` for cross-project patterns
5. Do NOT re-read the whole repo from scratch — the vault is the cached understanding

---

## Session End Ritual
1. Append a dated note to `../Nexus_OV/iPLAID_OV/Sessions/` using `Templates/Session Note.md`
2. Update `../Nexus_OV/iPLAID_OV/Current.md` if focus, blockers, or next steps shifted
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
| `src/iplaid/` | Main pipeline — layout → iDOT dispense output |
| `src/plaid_core/` | Plate-layout design engine (MiniZinc constraint solver) |
| `backend/` | FastAPI backend for the web workbench |
| `frontend/src/` | React + TypeScript UI |
| `compose.yml` | Docker Compose config |

---

## Known Issues / Gotchas
- MiniZinc is bundled in Docker only — not available on host
- `plaid_core` constraint solver: logic errors produce valid-looking but wrong layouts — always verify output visually
- iDOT protocol header row must use physical plate barcode (not logical name like `plate_1`) — iMETA's parser guards against this

---

## Anti-Patterns
- Never load multiple taste/design skills simultaneously
- Never skip superpowers brainstorm on features >50 lines
- Never commit non-trivial diffs without code-review
- Never re-read the full repo from scratch — always start from vault

---

## Reference
Skills and workflow recipes: `~/claude-steroid/skills/` and `~/claude-steroid/workflows/`
