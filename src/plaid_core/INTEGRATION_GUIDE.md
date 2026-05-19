# PLAID_Core Integration Guide

This repository already includes the PLAID_Core integration.

## Current integration points

- Backend bridge: [backend/app/designer.py](../../backend/app/designer.py)
- Backend API routes: [backend/app/main.py](../../backend/app/main.py)
- Frontend design client: [frontend/src/services/apiClient.ts](../../frontend/src/services/apiClient.ts)
- Frontend design UI: `frontend/src/components/design/` and `frontend/src/pages/WorkbenchPage.tsx`

## How it works here

1. The frontend sends a design configuration to `/api/design/validate` or `/api/design/solve`.
2. The backend converts the request model into `plaid_core.config.PlateConfig`.
3. `PlateDesigner` solves the layout through MiniZinc.
4. The backend converts the resulting layout into the CSV shape expected by the iPLAID pipeline.
5. The accepted layout is returned to the workbench and can then be run with a metadata CSV.

## Important limitation

PLAID_Core only creates layout assignments. It does not infer:

- `highest_stock_mM`
- `solvent`
- any source-stock or DMSO normalization data

Those inputs must still come from the metadata CSV before running the iPLAID pipeline.

## Historical note

Older versions of this document described how to copy PLAID_Core into iPLAID and wire endpoints from scratch. That guidance is now historical; the integration already exists in this repository.
