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

  const validationMsgs: Array<{ level: "error" | "warning"; text: string }> = [];
  rows.forEach((row) => {
    if (row.role === "treatment" && row.concentration_uM === 0) {
      validationMsgs.push({
        level: "error",
        text: `${row.compound_name || "A compound"} has a blank concentration.`,
      });
    }
  });
  if (usableWells > 0 && needed > usableWells) {
    validationMsgs.push({
      level: "error",
      text: `Too many entries: ${needed} wells assigned, only ${usableWells} available.`,
    });
  } else if (usableWells > 0 && needed > usableWells * 0.9) {
    validationMsgs.push({
      level: "warning",
      text: `Tight fit: ${needed}/${usableWells} wells used (>90%).`,
    });
  }
  const hasValidationErrors = validationMsgs.some((m) => m.level === "error");

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

        {validationMsgs.length > 0 && (
          <div className="design-validation-strip">
            {validationMsgs.map((m, i) => (
              <div key={i} className={`design-validation-msg design-validation-${m.level}`}>
                {m.level === "error" ? "✗" : "⚠"} {m.text}
              </div>
            ))}
          </div>
        )}
        {!hasValidationErrors && rows.length > 0 && needed > 0 && (
          <div className="design-validation-strip">
            <div className="design-validation-msg design-validation-ok">✓ Configuration looks good</div>
          </div>
        )}

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
            disabled={hasHardErrors || (usableWells > 0 && needed > usableWells)}
            onClick={handleConfirm}
          >
            Confirm Import ({rows.length} rows)
          </button>
        </div>

      </div>
    </div>
  );
}
