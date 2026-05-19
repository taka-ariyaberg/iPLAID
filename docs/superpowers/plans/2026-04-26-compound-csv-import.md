# Compound CSV Import Implementation Plan

> **Status:** Implemented and merged. This plan is the historical execution record; the live code is in `frontend/src/components/design/CompoundCSVImportModal.tsx` and the **Upload CSV** path in `CompoundPanel`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Upload CSV" button to the CompoundPanel that parses a compound list CSV, opens a preview/edit modal, and on confirmation populates the same `CompoundDef[]`/`SolventDef[]` state that manual entry uses.

**Architecture:** Pure client-side — a parse utility converts CSV text to flat rows, a modal lets the user review and edit those rows, and on confirm the rows are grouped into `CompoundDef[]`/`SolventDef[]` and handed to the existing `onCompoundsChange`/`onSolventsChange` callbacks. CompoundPanel has no mode flag and no knowledge of how its data arrived.

**Tech Stack:** React 19, TypeScript 5, Vite 7 — no new dependencies

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/utils/parseCompoundCSV.ts` | **Create** | CSV text → `FlatRow[]`; `FlatRow[]` → `CompoundDef[]` + `SolventDef[]` |
| `frontend/src/components/design/CompoundCSVImportModal.tsx` | **Create** | Editable preview modal with well counter + validation |
| `frontend/src/components/design/CompoundCSVImportModal.css` | **Create** | Modal styles (co-located) |
| `frontend/src/components/design/CompoundPanel.tsx` | **Modify** | Add file input, upload button, modal state, modal render |
| `frontend/src/styles/DesignMode.css` | **Modify** | Add `.cp-upload-csv-btn` style |

No changes to `DesignPanel.tsx`, `types.ts`, backend, or any other file.

---

## Task 1: CSV parsing utility

**Files:**
- Create: `frontend/src/utils/parseCompoundCSV.ts`

### CSV format (for reference)
```
compound_name,concentration_uM,replicate_number,role
CompoundA,100,3,treatment
CompoundA,10,2,treatment
DMSO,0,14,solvent
```
- Header is case-insensitive (lowercased before lookup)
- `role=treatment` rows → `CompoundDef`; same compound name = multiple `ConcEntry`
- `role=solvent` rows → `SolventDef`; concentration column is ignored

- [ ] **Step 1: Create the file with types and `parseCSVText`**

Create `frontend/src/utils/parseCompoundCSV.ts`:

```typescript
import type { CompoundDef, SolventDef } from "../types";

export type FlatRow = {
  id: string;
  compound_name: string;
  concentration_uM: number;
  replicate_number: number;
  role: "treatment" | "solvent";
};

export type ParseResult = {
  rows: FlatRow[];
  errors: string[];
  warnings: string[];
};

export function parseCSVText(text: string): ParseResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const rows: FlatRow[] = [];

  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (lines.length === 0) {
    errors.push("File is empty.");
    return { rows, errors, warnings };
  }

  const header = lines[0].split(",").map((h) => h.trim().toLowerCase());
  const idx = {
    compound_name:    header.indexOf("compound_name"),
    concentration_um: header.findIndex((h) => h === "concentration_um"),
    replicate_number: header.indexOf("replicate_number"),
    role:             header.indexOf("role"),
  };

  const missing = (Object.entries(idx) as [string, number][])
    .filter(([, i]) => i === -1)
    .map(([col]) => col);
  if (missing.length > 0) {
    errors.push(`Missing required column(s): ${missing.join(", ")}.`);
    return { rows, errors, warnings };
  }

  lines.slice(1).forEach((line, lineIdx) => {
    const rowNum = lineIdx + 2;
    const cells = line.split(",").map((c) => c.trim());
    const name     = cells[idx.compound_name]    ?? "";
    const concRaw  = cells[idx.concentration_um] ?? "";
    const repsRaw  = cells[idx.replicate_number] ?? "";
    const roleLower = (cells[idx.role] ?? "").toLowerCase();

    if (!name) {
      warnings.push(`Row ${rowNum}: empty compound_name — skipped.`);
      return;
    }
    if (roleLower !== "treatment" && roleLower !== "solvent") {
      warnings.push(`Row ${rowNum}: unknown role "${roleLower}" — skipped.`);
      return;
    }

    const conc = parseFloat(concRaw);
    const reps = parseInt(repsRaw, 10);

    if (Number.isNaN(conc)) {
      errors.push(`Row ${rowNum} (${name}): concentration_uM "${concRaw}" is not a number.`);
      return;
    }
    if (Number.isNaN(reps) || reps < 1) {
      errors.push(`Row ${rowNum} (${name}): replicate_number "${repsRaw}" must be a positive integer.`);
      return;
    }

    rows.push({
      id: `row-${rowNum}`,
      compound_name:   name,
      concentration_uM: conc,
      replicate_number: reps,
      role: roleLower as "treatment" | "solvent",
    });
  });

  return { rows, errors, warnings };
}

export function groupRowsToCompounds(rows: FlatRow[]): {
  compounds: CompoundDef[];
  solvents: SolventDef[];
} {
  const compoundMap = new Map<string, CompoundDef>();
  const solventMap  = new Map<string, SolventDef>();

  for (const row of rows) {
    const key = row.compound_name.trim().toLowerCase();
    if (row.role === "treatment") {
      if (!compoundMap.has(key)) {
        compoundMap.set(key, { name: row.compound_name, conc_entries: [] });
      }
      compoundMap.get(key)!.conc_entries.push({
        value_um:   row.concentration_uM,
        replicates: row.replicate_number,
      });
    } else {
      solventMap.set(key, { name: row.compound_name, replicates: row.replicate_number });
    }
  }

  return {
    compounds: Array.from(compoundMap.values()),
    solvents:  Array.from(solventMap.values()),
  };
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/utils/parseCompoundCSV.ts
git commit -m "feat: add parseCompoundCSV utility (FlatRow type + parseCSVText + groupRowsToCompounds)"
```

---

## Task 2: Import modal CSS

**Files:**
- Create: `frontend/src/components/design/CompoundCSVImportModal.css`

- [ ] **Step 1: Create the CSS file**

Create `frontend/src/components/design/CompoundCSVImportModal.css`:

```css
/* ── Backdrop + modal shell ──────────────────────────────── */

.ci-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.ci-modal {
  background: #1a1a26;
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 18px;
  padding: 1.75rem;
  width: min(720px, 96vw);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6);
}

/* ── Header ──────────────────────────────────────────────── */

.ci-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.ci-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--icell-text);
}

.ci-close {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: transparent;
  color: var(--icell-text-dim);
  font-size: 1.1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  line-height: 1;
  transition: background 140ms, border-color 140ms, color 140ms;
}

.ci-close:hover {
  background: rgba(255, 59, 85, 0.10);
  border-color: rgba(255, 59, 85, 0.26);
  color: #ff3b55;
}

/* ── Banners ─────────────────────────────────────────────── */

.ci-warning-banner {
  flex-shrink: 0;
  padding: 0.65rem 0.9rem;
  border-radius: 10px;
  border: 1px solid rgba(251, 191, 36, 0.25);
  background: rgba(251, 191, 36, 0.08);
  color: #fbbf24;
  font-size: 0.84rem;
  line-height: 1.5;
}

.ci-error-block {
  flex-shrink: 0;
  padding: 0.65rem 0.9rem;
  border-radius: 10px;
  border: 1px solid rgba(255, 59, 85, 0.25);
  background: rgba(255, 59, 85, 0.08);
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.ci-error-line {
  color: var(--icell-danger);
  font-size: 0.84rem;
}

.ci-warning-block {
  flex-shrink: 0;
  padding: 0.65rem 0.9rem;
  border-radius: 10px;
  border: 1px solid rgba(249, 115, 22, 0.20);
  background: rgba(249, 115, 22, 0.07);
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.ci-warning-line {
  color: var(--icell-warning);
  font-size: 0.84rem;
}

/* ── Well counter badge ──────────────────────────────────── */

.ci-well-badge {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-family: "IBM Plex Mono", monospace;
}

.ci-well-count  { font-weight: 700; color: var(--icell-text); }
.ci-well-sep    { color: var(--icell-text-dim); }
.ci-well-total  { color: var(--icell-text-muted); }
.ci-well-label  { color: var(--icell-text-dim); font-size: 11px; }

.ci-well-bar-track {
  flex: 1;
  height: 4px;
  background: rgba(255, 255, 255, 0.07);
  border-radius: 2px;
  overflow: hidden;
  min-width: 60px;
  max-width: 180px;
}

.ci-well-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 200ms ease, background 200ms ease;
}

/* ── Scrollable table ────────────────────────────────────── */

.ci-table-wrapper {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  border: 1px solid var(--icell-border);
  border-radius: var(--icell-radius-control);
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.08) transparent;
}

.ci-table-wrapper::-webkit-scrollbar { width: 4px; }
.ci-table-wrapper::-webkit-scrollbar-track { background: transparent; }
.ci-table-wrapper::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.10);
  border-radius: 4px;
}

.ci-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
}

.ci-table thead th {
  position: sticky;
  top: 0;
  background: var(--icell-panel-soft);
  color: var(--icell-text-muted);
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid var(--icell-border);
  z-index: 1;
}

.ci-row td {
  padding: 5px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  vertical-align: middle;
}

.ci-row:last-child td { border-bottom: none; }

.ci-row-solvent { background: rgba(255, 255, 255, 0.015); }

/* Editable name input */
.ci-name-input {
  width: 100%;
  min-width: 140px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--icell-text);
  font-size: 0.84rem;
  padding: 4px 6px;
  transition: border-color 120ms, background 120ms;
}

.ci-name-input:focus {
  outline: none;
  border-color: var(--icell-accent);
  background: rgba(129, 140, 248, 0.06);
}

/* SpinInput sizing overrides */
.spin-input.ci-spin        { min-width: 72px; }
.spin-input.ci-spin--blank { border-color: #facc15; }

.ci-conc-dash {
  color: var(--icell-text-dim);
  font-size: 0.9rem;
  padding-left: 8px;
}

/* Role badge */
.ci-role-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.ci-role-treatment {
  background: rgba(129, 140, 248, 0.12);
  color: #818cf8;
}

.ci-role-solvent {
  background: rgba(249, 115, 22, 0.12);
  color: var(--icell-warning);
}

/* Remove row button */
.ci-remove-btn {
  background: transparent;
  border: none;
  color: var(--icell-text-dim);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  line-height: 1;
  transition: color 120ms, background 120ms;
}

.ci-remove-btn:hover {
  color: var(--icell-danger);
  background: rgba(255, 59, 85, 0.10);
}

.ci-empty {
  padding: 1.5rem;
  text-align: center;
  color: var(--icell-text-dim);
  font-style: italic;
  font-size: 0.85rem;
}

/* ── Footer ──────────────────────────────────────────────── */

.ci-footer {
  flex-shrink: 0;
  display: flex;
  gap: 0.6rem;
  justify-content: flex-end;
  padding-top: 0.25rem;
}

.ci-cancel-btn {
  appearance: none;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: transparent;
  color: var(--icell-text-muted);
  padding: 0.55rem 1.1rem;
  border-radius: 10px;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 140ms, color 140ms;
}

.ci-cancel-btn:hover {
  border-color: rgba(255, 255, 255, 0.22);
  color: var(--icell-text);
}

.ci-confirm-btn {
  appearance: none;
  border: 1px solid rgba(129, 140, 248, 0.35);
  background: rgba(129, 140, 248, 0.12);
  color: #818cf8;
  padding: 0.55rem 1.25rem;
  border-radius: 10px;
  font-size: 0.88rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 140ms, border-color 140ms, color 140ms;
}

.ci-confirm-btn:hover:not(:disabled) {
  background: rgba(129, 140, 248, 0.22);
  border-color: rgba(129, 140, 248, 0.55);
  color: #a5b4fc;
}

.ci-confirm-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/design/CompoundCSVImportModal.css
git commit -m "feat: add CompoundCSVImportModal styles"
```

---

## Task 3: Import modal component

**Files:**
- Create: `frontend/src/components/design/CompoundCSVImportModal.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/design/CompoundCSVImportModal.tsx`:

```typescript
import { useState } from "react";
import type { CompoundDef, SolventDef } from "../../types";
import type { FlatRow } from "../../utils/parseCompoundCSV";
import { groupRowsToCompounds } from "../../utils/parseCompoundCSV";
import { totalWellsNeeded } from "./designUtils";
import { SpinInput } from "./SpinInput";
import "./CompoundCSVImportModal.css";

interface CompoundCSVImportModalProps {
  initialRows: FlatRow[];
  parseErrors: string[];
  parseWarnings: string[];
  usableWells: number;
  hasExistingData: boolean;
  onConfirm: (compounds: CompoundDef[], solvents: SolventDef[]) => void;
  onCancel: () => void;
}

export function CompoundCSVImportModal({
  initialRows,
  parseErrors,
  parseWarnings,
  usableWells,
  hasExistingData,
  onConfirm,
  onCancel,
}: CompoundCSVImportModalProps) {
  const [rows, setRows] = useState<FlatRow[]>(initialRows);

  const { compounds, solvents } = groupRowsToCompounds(rows);
  const needed = totalWellsNeeded(compounds, solvents);
  const pct = usableWells > 0 ? Math.round((needed / usableWells) * 100) : 0;
  const hasHardErrors = parseErrors.length > 0;

  function updateRow(id: string, patch: Partial<FlatRow>) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function removeRow(id: string) {
    setRows((prev) => prev.filter((r) => r.id !== id));
  }

  function handleConfirm() {
    const { compounds: c, solvents: s } = groupRowsToCompounds(rows);
    onConfirm(c, s);
  }

  return (
    <div className="ci-backdrop" onClick={onCancel}>
      <div className="ci-modal" onClick={(e) => e.stopPropagation()}>

        <div className="ci-header">
          <h3 className="ci-title">Import compounds from CSV</h3>
          <button type="button" className="ci-close" onClick={onCancel}>×</button>
        </div>

        {hasExistingData && (
          <div className="ci-warning-banner">
            ⚠ Confirming will replace your current compound and solvent list.
          </div>
        )}

        {parseErrors.length > 0 && (
          <div className="ci-error-block">
            {parseErrors.map((e, i) => (
              <div key={i} className="ci-error-line">✗ {e}</div>
            ))}
          </div>
        )}

        {parseWarnings.length > 0 && (
          <div className="ci-warning-block">
            {parseWarnings.map((w, i) => (
              <div key={i} className="ci-warning-line">⚠ {w}</div>
            ))}
          </div>
        )}

        <div className="ci-well-badge">
          <span className="ci-well-count">{needed}</span>
          <span className="ci-well-sep">/</span>
          <span className="ci-well-total">{usableWells}</span>
          <span className="ci-well-label">wells</span>
          {usableWells > 0 && (
            <div className="ci-well-bar-track">
              <div
                className="ci-well-bar-fill"
                style={{
                  width: `${Math.min(100, pct)}%`,
                  background:
                    pct > 100 ? "var(--icell-danger)" :
                    pct > 90  ? "#facc15" :
                    "var(--icell-success)",
                }}
              />
            </div>
          )}
        </div>

        <div className="ci-table-wrapper">
          <table className="ci-table">
            <thead>
              <tr>
                <th>Compound</th>
                <th>Conc (µM)</th>
                <th>Reps</th>
                <th>Role</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className={`ci-row ci-row-${row.role}`}>
                  <td>
                    <input
                      className="ci-name-input"
                      value={row.compound_name}
                      onChange={(e) => updateRow(row.id, { compound_name: e.target.value })}
                      onFocus={(e) => e.target.select()}
                    />
                  </td>
                  <td>
                    {row.role === "treatment" ? (
                      <SpinInput
                        min={0}
                        className={`ci-spin${row.concentration_uM === 0 ? " ci-spin--blank" : ""}`}
                        value={row.concentration_uM}
                        onChange={(v) => updateRow(row.id, { concentration_uM: v })}
                      />
                    ) : (
                      <span className="ci-conc-dash">—</span>
                    )}
                  </td>
                  <td>
                    <SpinInput
                      min={1}
                      max={48}
                      className="ci-spin"
                      value={row.replicate_number}
                      onChange={(v) => updateRow(row.id, { replicate_number: v })}
                    />
                  </td>
                  <td>
                    <span className={`ci-role-badge ci-role-${row.role}`}>
                      {row.role}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ci-remove-btn"
                      onClick={() => removeRow(row.id)}
                      title="Remove row"
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="ci-empty">
                    No rows — all entries removed.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="ci-footer">
          <button type="button" className="ci-cancel-btn" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="ci-confirm-btn"
            disabled={hasHardErrors}
            onClick={handleConfirm}
          >
            Confirm Import ({rows.length} rows)
          </button>
        </div>

      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/design/CompoundCSVImportModal.tsx
git commit -m "feat: add CompoundCSVImportModal component"
```

---

## Task 4: Wire upload into CompoundPanel

**Files:**
- Modify: `frontend/src/components/design/CompoundPanel.tsx`
- Modify: `frontend/src/styles/DesignMode.css`

- [ ] **Step 1: Add upload button style to DesignMode.css**

In `frontend/src/styles/DesignMode.css`, locate the `.design-add-btn` block (around line 413) and append these rules **after** the existing `.design-add-btn:hover` rule:

```css
/* Upload CSV button — secondary variant of design-add-btn */
.cp-upload-csv-btn {
  color: var(--icell-text-muted);
  border-color: rgba(255, 255, 255, 0.09);
  font-size: 12px;
  padding: 7px 14px;
  margin-top: 4px;
}

.cp-upload-csv-btn:hover {
  color: var(--icell-accent);
  border-color: rgba(129, 140, 248, 0.30);
  background: rgba(129, 140, 248, 0.06);
}
```

- [ ] **Step 2: Add imports to CompoundPanel.tsx**

The existing React import line already includes `useRef` and `useState` — no change needed there.

Add these two new import lines after the `import { totalWellsNeeded } from "./designUtils";` line:

```typescript
import { parseCSVText, type ParseResult } from "../../utils/parseCompoundCSV";
import { CompoundCSVImportModal } from "./CompoundCSVImportModal";
```

- [ ] **Step 3: Add state and handlers to CompoundPanel**

Inside the `CompoundPanel` function body, right after the line `const needed = totalWellsNeeded(compounds, solvents);`, add:

```typescript
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      setParseResult(parseCSVText(text));
      e.target.value = "";
    };
    reader.readAsText(file);
  }

  function handleImportConfirm(newCompounds: CompoundDef[], newSolvents: SolventDef[]) {
    onCompoundsChange(newCompounds);
    onSolventsChange(newSolvents);
    setParseResult(null);
  }
```

- [ ] **Step 4: Add the Upload CSV button and hidden file input**

In `CompoundPanel.tsx`, locate the "Add Compound" button:

```tsx
        <button
          type="button"
          className="design-add-btn"
          onClick={() => onCompoundsChange([...compounds, DEFAULT_COMPOUND()])}
        >
          Add Compound
        </button>
```

Replace it with:

```tsx
        <button
          type="button"
          className="design-add-btn"
          onClick={() => onCompoundsChange([...compounds, DEFAULT_COMPOUND()])}
        >
          Add Compound
        </button>
        <button
          type="button"
          className="design-add-btn cp-upload-csv-btn"
          onClick={handleUploadClick}
        >
          ↑ Upload CSV
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          style={{ display: "none" }}
          onChange={handleFileChange}
        />
```

- [ ] **Step 5: Render the modal**

At the very end of the `CompoundPanel` return, just before the closing `</div>` of `design-compound-panel`, add:

```tsx
        {parseResult !== null && (
          <CompoundCSVImportModal
            initialRows={parseResult.rows}
            parseErrors={parseResult.errors}
            parseWarnings={parseResult.warnings}
            usableWells={usableWells}
            hasExistingData={compounds.length > 0 || solvents.length > 0}
            onConfirm={handleImportConfirm}
            onCancel={() => setParseResult(null)}
          />
        )}
```

- [ ] **Step 6: Type-check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/design/CompoundPanel.tsx frontend/src/styles/DesignMode.css
git commit -m "feat: wire CSV import into CompoundPanel with upload button and modal"
```

---

## Task 5: Manual test

**Files:** none (verification only)

- [ ] **Step 1: Start the app**

```bash
docker compose up
```
Open `http://127.0.0.1:8000` in the browser.

- [ ] **Step 2: Navigate to Design Plate Layout**

Click "Design Plate Layout" in the workbench. Confirm the right panel (CompoundPanel) shows an "↑ Upload CSV" button below "Add Compound".

- [ ] **Step 3: Test happy path with the test fixture**

Upload `inputs/plaid_feeder/plaid_compound_feeder.csv`.

Expected:
- Modal opens.
- 43 rows shown (42 treatment + 1 DMSO solvent row).
- DMSO row has role badge "solvent", conc cell shows "—".
- Well counter shows correct total.
- No error or warning banners.
- "Confirm Import (43 rows)" button is enabled.

- [ ] **Step 4: Test row editing in the modal**

Edit one compound's concentration. Confirm the well counter updates live. Remove one row. Confirm row count in button label decreases.

- [ ] **Step 5: Confirm import**

Click "Confirm Import". Modal closes. CompoundPanel shows 42 `CompoundEntryEditor` cards + 1 `SolventEntryEditor` card. Confirm editing a card (name, concentration, replicates) works identically to manually-added compounds.

- [ ] **Step 6: Test replace warning**

Without clearing the panel, click "↑ Upload CSV" again and upload the same file. Confirm the amber "Confirming will replace your current compound and solvent list." banner appears.

- [ ] **Step 7: Test Cancel**

Open the modal and click Cancel (or backdrop). Confirm the panel is unchanged.

- [ ] **Step 8: Test faulty CSV**

Create a CSV with a missing column header (e.g. remove `role`) and upload it.
Expected: modal opens, red error block shows "Missing required column(s): role.", Confirm button is disabled.

- [ ] **Step 9: Final commit tag**

```bash
git tag feat/compound-csv-import
```

---

## Self-Review Notes

- `parseCSVText` lowercases headers before lookup, so `concentration_uM` (capital M in file) → `concentration_um` → matched correctly.
- `handleFileChange` resets `e.target.value = ""` so uploading the same file twice fires `onChange` both times.
- `CompoundCSVImportModal` holds its own `rows` state copy — the parent (`CompoundPanel`) only receives data on Confirm, so editing in the modal never affects the live panel until confirmed.
- `handleImportConfirm` receives `CompoundDef[]`/`SolventDef[]` — both already imported at the top of `CompoundPanel.tsx`, no new imports needed for the handler.
- `DesignPanel.tsx`, `types.ts`, and all backend files are untouched.
