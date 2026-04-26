# Design: Compound CSV Import for Design Plate Layout

**Date:** 2026-04-26  
**Branch:** imeta-csv-export (to be implemented on a new branch)  
**Scope:** Frontend only — no backend changes required

---

## Problem

In Design Plate Layout, users must add compounds one-by-one manually. For long compound lists this is tedious. A CSV upload path is needed as an alternative entry point that populates the same compound/solvent state the manual path uses.

---

## CSV Format

One row per compound-concentration pair (long format). Columns:

| Column | Type | Notes |
|---|---|---|
| `compound_name` | string | repeated rows = multiple concentrations for same compound |
| `concentration_uM` | number | µM value; ignored for solvents |
| `replicate_number` | integer | replicates for this concentration |
| `role` | string | `treatment` → Compounds section; `solvent` → Solvents section |

**Example (multi-concentration compound):**
```
compound_name,concentration_uM,replicate_number,role
CompoundA,100,3,treatment
CompoundA,10,2,treatment
CompoundB,50,3,treatment
DMSO,0,14,solvent
```

Accepted file types: `.csv`, `.xlsx`.

Test fixture: `inputs/plaid_feeder/plaid_compound_feeder.xlsx`

---

## Architecture

The import is **purely client-side**. No backend changes. After confirmation the panel receives plain `CompoundDef[]` and `SolventDef[]` — identical to what manual entry produces. The `CompoundPanel` has no knowledge of how the data arrived.

```
CSV file
  └─► parseCompoundCSV()         // new utility
        └─► { compounds, solvents, errors }
              └─► CompoundCSVImportModal   // new component
                    └─► [on confirm] onCompoundsChange() + onSolventsChange()
                                           // same callbacks as manual entry
                          └─► CompoundPanel (normal card-edit mode)
```

---

## New Files

| File | Purpose |
|---|---|
| `frontend/src/utils/parseCompoundCSV.ts` | CSV/XLSX parsing and grouping logic |
| `frontend/src/components/design/CompoundCSVImportModal.tsx` | Preview + edit modal |

---

## parseCompoundCSV

```ts
type ParseResult = {
  compounds: CompoundDef[];
  solvents: SolventDef[];
  errors: string[];   // hard errors that block confirmation
  warnings: string[]; // non-blocking (e.g. unknown role values skipped)
};

function parseCompoundCSV(text: string): ParseResult
```

Rules:
- Required columns: `compound_name`, `concentration_uM`, `replicate_number`, `role`. Missing column → error.
- Rows with `role === 'treatment'`: grouped by `compound_name` (case-insensitive trim). Each row → one `ConcEntry { value_um, replicates }`.
- Rows with `role === 'solvent'`: each unique name → `SolventDef { name, replicates }`. Concentration ignored.
- Non-numeric `concentration_uM` or `replicate_number` → error on that row.
- Empty `compound_name` → row skipped with warning.
- Unknown `role` values → row skipped with warning.
- XLSX support: convert to CSV text before passing in using **SheetJS** (`xlsx` npm package — standard browser-side XLSX reader, no openpyxl).

---

## CompoundCSVImportModal

### Trigger

An **"Upload CSV"** button is added in the Compounds section of `CompoundPanel`, beneath the "Add Compound" button. It activates a hidden `<input type="file" accept=".csv,.xlsx">`. The button is always visible regardless of whether compounds already exist.

### Modal layout

1. **Warning banner** (shown only when `compounds.length > 0 || solvents.length > 0`):  
   "Uploading will replace your current [N] compound(s) and [M] solvent(s)."

2. **Parse error block** (shown only when `errors.length > 0`):  
   Hard errors listed; Confirm button is disabled.

3. **Editable table** — flat, one row per CSV row (not card format):
   - Columns: `Compound name`, `Conc (µM)`, `Reps`, `Role`, `×` (remove row)
   - `Conc (µM)` and `Reps` are inline-editable via SpinInput
   - `Compound name` is an inline text input
   - `Role` is a read-only badge (`treatment` / `solvent`)
   - Removing all rows of a compound removes it entirely

4. **Live well counter**: same `needed / usable` math as `CompoundPanel`'s well badge. Updates on every table edit.

5. **Validation strip**: same rules as `CompoundPanel` — blank concentrations, duplicate compound names, compound/solvent name overlap, well overflow. Non-blocking warnings shown; overflow shown but does not block Confirm.

6. **Footer**: `Cancel` | `Confirm Import`
   - `Confirm Import` disabled only when hard parse errors exist.

### On confirm

Calls `onCompoundsChange(parsedCompounds)` and `onSolventsChange(parsedSolvents)` — the same prop callbacks used by manual entry. Modal closes. `CompoundPanel` is now in its normal card-edit mode: every compound is a `CompoundEntryEditor` card, every solvent is a `SolventEntryEditor` card, all editable exactly as if typed manually.

### On cancel

No state change. Modal closes.

---

## CompoundPanel changes

Minimal. Two additions only:

1. Hidden `<input type="file">` ref wired to the Upload CSV button.
2. "Upload CSV" button in the Compounds section header area (below "Add Compound").
3. `CompoundCSVImportModal` rendered conditionally when a file has been selected and parsed.

The existing manual-entry flow, all validation logic, `SpinInput`, duplicate detection, overflow popup — **untouched**.

---

## Single-path guarantee

After modal confirmation, `CompoundPanel` holds `CompoundDef[]` and `SolventDef[]`. It does not know or care whether those came from the CSV path or manual entry. There is no "csv mode" flag. All downstream behavior — editing, removing, adding more compounds, the Generate button — is identical regardless of how the list was populated.

---

## Out of scope

- Solvents-only CSV upload (solvents are included via `role === 'solvent'` rows in the same file)
- Backend parsing endpoint
- Exporting the current compound list back to CSV
- Undo/redo
