/**
 * MetaCreatorModal — interactive builder for the `cmpd_info.csv` metadata file.
 *
 * Columns written:  cmpdname, highest_stock_mM, solvent
 * "Use as Meta File" creates a File object and passes it back via `onApply`.
 * "Download CSV" also writes it to disk for archiving.
 */

import React, { useMemo, useState } from "react";
import { SpinInput } from "../design/SpinInput";
import { getStableCompoundColor } from "../../utils/colorUtils";
import "./MetaCreatorModal.css";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CompoundRow {
  id: number;
  name: string;
  stock_mM: string;
  stockUnit: StockUnit;
  solvent: string;
}

type StockUnit = "M" | "mM" | "uM" | "nM";

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
  stock_mM: "",
  stockUnit: "mM",
  solvent: "DMSO",
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

function buildCSV(rows: CompoundRow[]): string {
  const header = "cmpdname,highest_stock_mM,solvent";
  const seen = new Set<string>();
  const dataLines: string[] = [];
  for (const r of rows) {
    const name = r.name.trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    const stockValue = r.stock_mM === "" ? 0 : Math.max(0, Number(r.stock_mM));
    const stock = String(stockValue * STOCK_UNIT_FACTORS[r.stockUnit]);
    dataLines.push(`${csvField(name)},${stock},${csvField(r.solvent || "DMSO")}`);
  }
  return [header, ...dataLines].join("\n");
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MetaCreatorModal({ initialRows, onClose, onApply }: MetaCreatorModalProps) {
  const seededRows = useMemo(() => {
    if (!initialRows || initialRows.length === 0) return [mkRow()];
    const nextSeed = initialRows.map((row) => ({ ...row, stockUnit: row.stockUnit ?? "mM" }));
    const maxId = nextSeed.reduce((max, row) => Math.max(max, row.id), 0);
    _nextId = Math.max(_nextId, maxId + 1);
    return nextSeed;
  }, [initialRows]);
  const [rows, setRows] = useState<CompoundRow[]>(seededRows);

  const addRow = () => setRows((r) => [...r, mkRow()]);

  const removeRow = (id: number) =>
    setRows((r) => (r.length > 1 ? r.filter((x) => x.id !== id) : r));

  const updateRow = (id: number, field: keyof CompoundRow, value: string) =>
    setRows((r) => r.map((x) => (x.id === id ? { ...x, [field]: value } : x)));

  const validCount = rows.filter(
    (r, i, arr) => {
      const name = r.name.trim();
      return name && arr.findIndex((x) => x.name.trim() === name) === i;
    }
  ).length;

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
            <p className="mcm-subtitle">
              Define compound names, stock concentrations, and solvents for the metadata CSV.
            </p>
          </div>
          <button className="mcm-close-btn" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* ── Column headers ── */}
        <div className="mcm-col-headers">
          <span className="mcm-dot-spacer" />
          <span className="mcm-col-lbl mcm-col-name">Compound name</span>
          <span className="mcm-col-lbl mcm-col-stock">Stock</span>
          <span className="mcm-col-lbl mcm-col-unit">Unit</span>
          <span className="mcm-col-lbl mcm-col-solvent">Solvent</span>
          <span className="mcm-remove-spacer" />
        </div>

        {/* ── Compound rows ── */}
        <div className="mcm-rows">
          {rows.map((row, i) => (
            <div key={row.id} className="mcm-row">
              <span
                className="mcm-row-dot"
                style={{ background: getStableCompoundColor(i) }}
              />
              <input
                className="mcm-input mcm-input-name"
                placeholder="e.g. Etoposide"
                value={row.name}
                onChange={(e) => updateRow(row.id, "name", e.target.value)}
                onFocus={(e) => e.target.select()}
              />
              <SpinInput
                min={0}
                step={1}
                className="mcm-stock-spin"
                placeholder="10"
                value={row.stock_mM === "" ? 0 : Number(row.stock_mM) || 0}
                onChange={(value) => updateRow(row.id, "stock_mM", String(Math.max(0, value)))}
                onCommit={(value) => updateRow(row.id, "stock_mM", String(Math.max(0, value)))}
              />
              <select
                className="mcm-input mcm-input-unit"
                value={row.stockUnit}
                onChange={(e) => updateRow(row.id, "stockUnit", e.target.value as StockUnit)}
              >
                <option value="M">M</option>
                <option value="mM">mM</option>
                <option value="uM">uM</option>
                <option value="nM">nM</option>
              </select>
              <input
                className="mcm-input mcm-input-solvent"
                placeholder="DMSO"
                value={row.solvent}
                onChange={(e) => updateRow(row.id, "solvent", e.target.value)}
                onFocus={(e) => e.target.select()}
              />
              <button
                className="mcm-remove-btn"
                onClick={() => removeRow(row.id)}
                title="Remove row"
                disabled={rows.length === 1}
              >
                ×
              </button>
            </div>
          ))}
        </div>

        <button className="mcm-add-row-btn" onClick={addRow}>
          Add Compound
        </button>

        {/* ── Footer ── */}
        <div className="mcm-footer">
          <span className="mcm-compound-count">
            {validCount} compound{validCount !== 1 ? "s" : ""}
          </span>
          <div className="mcm-footer-actions">
            <button className="mcm-btn mcm-btn-ghost" onClick={handleDownload}>
              Download CSV
            </button>
            <button
              className="mcm-btn mcm-btn-primary"
              disabled={validCount === 0}
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
