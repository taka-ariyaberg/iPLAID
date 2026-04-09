/**
 * MetaCreatorModal — interactive builder for the `cmpd_info.csv` metadata file.
 *
 * Columns written:  cmpdname, highest_stock_mM, solvent
 * "Use as Meta File" creates a File object and passes it back via `onApply`.
 * "Download CSV" also writes it to disk for archiving.
 */

import { Fragment, useMemo, useState } from "react";
import { SpinInput } from "../design/SpinInput";
import { getStableCompoundColor } from "../../utils/colorUtils";
import "./MetaCreatorModal.css";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type RowClass = "compound" | "solvent";

export interface CompoundRow {
  id: number;
  name: string;
  stock_mM: string;
  stockUnit: StockUnit;
  solvent: string;
  rowClass?: RowClass;
}

type StockUnit = "M" | "mM" | "uM" | "nM";
type ValidationResult = { ok: boolean; message: string };

interface MetaCreatorModalProps {
  initialRows?: CompoundRow[];
  onClose: () => void;
  onApply: (file: File, rows: CompoundRow[]) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let _nextId = 1;
const mkRow = (): CompoundRow => ({
  id: _nextId++,
  name: "",
  stock_mM: "10",
  stockUnit: "mM",
  solvent: "DMSO",
  rowClass: "compound",
});

const mkSolventRow = (name = ""): CompoundRow => ({
  id: _nextId++,
  name,
  stock_mM: "0",
  stockUnit: "mM",
  solvent: name,
  rowClass: "solvent",
});

const STOCK_UNIT_FACTORS: Record<StockUnit, number> = {
  M: 1000,
  mM: 1,
  uM: 0.001,
  nM: 0.000001,
};

/** Wrap a CSV field in quotes if it contains a comma, quote, or newline. */
function csvField(v: string): string {
  return /[,"\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}

function normalizeName(value: string): string {
  return value.trim().toLowerCase();
}

function getRowClass(row: CompoundRow): RowClass {
  if (row.rowClass) return row.rowClass;
  const name = row.name.trim().toUpperCase();
  const stockValue = Number(row.stock_mM);
  if ((name === "DMSO" || name === row.solvent.trim().toUpperCase()) && stockValue === 0) {
    return "solvent";
  }
  return "compound";
}

function getExportStockMm(row: CompoundRow): number {
  const stockValue = Number(row.stock_mM);
  if (!Number.isFinite(stockValue)) {
    return 0;
  }
  return Math.max(0, stockValue) * STOCK_UNIT_FACTORS[row.stockUnit];
}

function validateRow(row: CompoundRow, rows: CompoundRow[]): ValidationResult {
  const name = row.name.trim();
  if (!name) {
    return { ok: false, message: "Name required." };
  }

  const normalizedName = normalizeName(name);
  const matchingRows = rows.filter(
    (candidate) => normalizeName(candidate.name) === normalizedName
  );
  if (matchingRows.length > 1) {
    const firstId = matchingRows[0]?.id;
    return {
      ok: firstId === row.id,
      message: "Duplicate name.",
    };
  }

  if (!row.solvent.trim()) {
    return { ok: false, message: "Solvent required." };
  }

  const rowClass = getRowClass(row);
  const stockValue = Number(row.stock_mM);
  const hasNumericStock = row.stock_mM !== "" && Number.isFinite(stockValue);

  if (!hasNumericStock) {
    return { ok: false, message: "Stock required." };
  }

  if (rowClass === "solvent") {
    return { ok: true, message: "" };
  }

  if (stockValue <= 0) {
    return { ok: false, message: "Compounds must be > 0." };
  }

  return { ok: true, message: "" };
}

function buildCSV(rows: CompoundRow[]): string {
  const header = "cmpdname,highest_stock_mM,solvent";
  const seen = new Set<string>();
  const dataLines: string[] = [];
  for (const r of rows) {
    const name = r.name.trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    const stock = String(getExportStockMm(r));
    dataLines.push(`${csvField(name)},${stock},${csvField(r.solvent || "DMSO")}`);
  }
  return [header, ...dataLines].join("\n");
}

function MetaEntryEditor({
  row,
  index,
  isSolventControl,
  onUpdate,
  onStockUpdate,
  onRemove,
  validationMessage,
}: {
  row: CompoundRow;
  index: number;
  isSolventControl: boolean;
  onUpdate: (field: keyof CompoundRow, value: string) => void;
  onStockUpdate: (value: number) => void;
  onRemove: () => void;
  validationMessage?: string;
}) {
  return (
    <Fragment>
      <div className={`mcm-row${isSolventControl ? " mcm-row-solvent" : ""}${validationMessage ? " is-invalid" : ""}`}>
        <span
          className="mcm-row-dot"
          style={{ background: getStableCompoundColor(index) }}
        />
        <input
          className="mcm-input mcm-input-name"
          placeholder={isSolventControl ? "e.g. DMSO" : "e.g. Etoposide"}
          value={row.name}
          onChange={(e) => {
            const nextValue = e.target.value;
            onUpdate("name", nextValue);
            if (isSolventControl) {
              onUpdate("solvent", nextValue);
            }
          }}
          onFocus={(e) => e.target.select()}
        />
        <SpinInput
          min={isSolventControl ? 0 : 1}
          step={1}
          className="mcm-stock-spin"
          placeholder={isSolventControl ? "0" : "10"}
          value={row.stock_mM === "" ? (isSolventControl ? 0 : 10) : Number(row.stock_mM) || 0}
          onChange={onStockUpdate}
          onCommit={onStockUpdate}
        />
        <select
          className="mcm-input mcm-input-unit"
          value={row.stockUnit}
          onChange={(e) => onUpdate("stockUnit", e.target.value as StockUnit)}
        >
          <option value="M">M</option>
          <option value="mM">mM</option>
          <option value="uM">uM</option>
          <option value="nM">nM</option>
        </select>
        {!isSolventControl ? (
          <input
            className="mcm-input mcm-input-solvent"
            placeholder="DMSO"
            value={row.solvent}
            onChange={(e) => onUpdate("solvent", e.target.value)}
            onFocus={(e) => e.target.select()}
          />
        ) : null}
        <button
          className="mcm-remove-btn"
          onClick={onRemove}
          title="Remove row"
        >
          ×
        </button>
      </div>
      {validationMessage && <p className="mcm-row-message">{validationMessage}</p>}
    </Fragment>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MetaCreatorModal({ initialRows, onClose, onApply }: MetaCreatorModalProps) {
  const seededRows = useMemo(() => {
    if (!initialRows || initialRows.length === 0) return [mkRow(), mkSolventRow()];
    const nextSeed: CompoundRow[] = initialRows.map((row) => ({
      ...row,
      stockUnit: row.stockUnit ?? "mM",
      rowClass: getRowClass(row),
    }));
    if (!nextSeed.some((row) => getRowClass(row) === "solvent")) {
      nextSeed.push(mkSolventRow());
    }
    const maxId = nextSeed.reduce((max, row) => Math.max(max, row.id), 0);
    _nextId = Math.max(_nextId, maxId + 1);
    return nextSeed;
  }, [initialRows]);
  const [rows, setRows] = useState<CompoundRow[]>(seededRows);
  const [stockWarnings, setStockWarnings] = useState<Record<number, string>>({});

  const removeRow = (id: number) => {
    setRows((r) => (r.length > 1 ? r.filter((x) => x.id !== id) : r));
    setStockWarnings((current) => {
      const next = { ...current };
      delete next[id];
      return next;
    });
  };

  const updateRow = (id: number, field: keyof CompoundRow, value: string) =>
    setRows((r) => r.map((x) => (x.id === id ? { ...x, [field]: value } : x)));

  function updateStock(id: number, isSolventControl: boolean, value: number) {
    if (isSolventControl) {
      setStockWarnings((current) => {
        const next = { ...current };
        delete next[id];
        return next;
      });
      updateRow(id, "stock_mM", String(Math.max(0, value)));
      return;
    }

    if (value <= 0) {
      setStockWarnings((current) => ({
        ...current,
        [id]: "Compounds cannot use 0.",
      }));
    } else {
      setStockWarnings((current) => {
        const next = { ...current };
        delete next[id];
        return next;
      });
    }

    updateRow(id, "stock_mM", String(Math.max(1, value)));
  }

  const rowStates = rows.map((row) => ({ row, validation: validateRow(row, rows) }));
  const compoundRows = rowStates.filter(({ row }) => getRowClass(row) === "compound");
  const solventRows = rowStates.filter(({ row }) => getRowClass(row) === "solvent");
  const hasInvalidCompoundRows = compoundRows.some(({ validation }) => !validation.ok);
  const hasInvalidSolventRows = solventRows.some(({ validation }) => !validation.ok);
  const solventNames = new Set(
    solventRows
      .map(({ row }) => normalizeName(row.name))
      .filter(Boolean)
  );
  const missingSolventRows = Array.from(
    new Set(
      compoundRows
        .map(({ row }) => row.solvent.trim())
        .filter(Boolean)
        .filter((solvent) => !solventNames.has(normalizeName(solvent)))
    )
  );
  const validCount = rowStates.filter(({ validation }) => validation.ok).length;
  const invalidCount = rowStates.length - validCount;
  const canSubmit = validCount > 0 && invalidCount === 0 && missingSolventRows.length === 0;

  function addCompoundRow() {
    if (hasInvalidCompoundRows) return;
    setRows((r) => [...r, mkRow()]);
  }

  function addSolventRow() {
    if (hasInvalidSolventRows) return;
    const nextSuggestedSolvent = missingSolventRows[0] ?? "";
    setRows((r) => [...r, mkSolventRow(nextSuggestedSolvent)]);
  }

  function handleApply() {
    const csv = buildCSV(rows);
    const blob = new Blob([csv], { type: "text/csv" });
    const file = new File([blob], "cmpd_info.csv", { type: "text/csv" });
    onApply(file, rows);
  }

  function handleDownload() {
    const csv = buildCSV(rows);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "cmpd_info.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div
      className="mcm-overlay"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="mcm-modal" role="dialog" aria-modal="true">
        {/* ── Header ── */}
        <div className="mcm-header">
          <div>
            <p className="mcm-kicker">Inputs</p>
            <h2 className="mcm-title">Build compound info file</h2>
          </div>
          <button className="mcm-close-btn" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="mcm-rows">
          <section className="mcm-group">
            <div className="mcm-group-header">
              <p className="mcm-group-title">Compounds</p>
            </div>
            <div className="mcm-col-headers">
              <span className="mcm-dot-spacer" />
              <span className="mcm-col-lbl mcm-col-name">Compound name</span>
              <span className="mcm-col-lbl mcm-col-stock">Stock</span>
              <span className="mcm-col-lbl mcm-col-unit">Unit</span>
              <span className="mcm-col-lbl mcm-col-solvent">Solvent</span>
              <span className="mcm-remove-spacer" />
            </div>
          {compoundRows.length === 0 && <p className="mcm-empty-hint">No compounds yet.</p>}
            {compoundRows.map(({ row, validation }, i) => (
              <MetaEntryEditor
                key={row.id}
                row={row}
                index={i}
                isSolventControl={false}
                validationMessage={stockWarnings[row.id] ?? (validation.ok ? undefined : validation.message)}
                onUpdate={(field, value) => updateRow(row.id, field, value)}
                onStockUpdate={(value) => updateStock(row.id, false, value)}
                onRemove={() => removeRow(row.id)}
              />
            ))}
            <button
              className="mcm-group-add mcm-group-add-wide"
              onClick={addCompoundRow}
              disabled={hasInvalidCompoundRows}
            >
              Add compound
            </button>
          </section>

          <section className="mcm-group">
            <div className="mcm-group-header">
              <p className="mcm-group-title">Solvent / controls</p>
            </div>
            <div className="mcm-col-headers mcm-col-headers-solvent">
              <span className="mcm-dot-spacer" />
              <span className="mcm-col-lbl mcm-col-name">Name</span>
              <span className="mcm-col-lbl mcm-col-stock">Stock</span>
              <span className="mcm-col-lbl mcm-col-unit">Unit</span>
              <span className="mcm-remove-spacer" />
            </div>
            {solventRows.length === 0 && <p className="mcm-empty-hint">No solvent/control rows yet.</p>}
            {solventRows.map(({ row, validation }, i) => (
              <MetaEntryEditor
                key={row.id}
                row={row}
                index={compoundRows.length + i}
                isSolventControl={true}
                validationMessage={stockWarnings[row.id] ?? (validation.ok ? undefined : validation.message)}
                onUpdate={(field, value) => updateRow(row.id, field, value)}
                onStockUpdate={(value) => updateStock(row.id, true, value)}
                onRemove={() => removeRow(row.id)}
              />
            ))}
            <button
              className="mcm-group-add mcm-group-add-wide"
              onClick={addSolventRow}
              disabled={hasInvalidSolventRows}
            >
              Add solvent/control
            </button>
          </section>
        </div>

        {/* ── Footer ── */}
        <div className="mcm-footer">
          <span className="mcm-compound-count">
            {validCount} valid row{validCount !== 1 ? "s" : ""}
          </span>
          <div className="mcm-footer-actions">
            <button className="mcm-btn mcm-btn-ghost" onClick={handleDownload}>
              Download CSV
            </button>
            <button
              className="mcm-btn mcm-btn-primary"
              disabled={!canSubmit}
              onClick={handleApply}
            >
              Use as Meta File
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
