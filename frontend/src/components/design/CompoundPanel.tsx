/**
 * CompoundPanel — right panel of the Design mode.
 * Lets users add/edit/remove compounds with concentration rows and solvents
 * with replicate counts only.
 */

import { Fragment, useEffect, useRef, useState } from "react";
import type { CompoundDef, SolventDef } from "../../types";
import { getConcColor, DMSO_COLOR, getStableCompoundColor } from "../../utils/colorUtils";
import { SpinInput } from "./SpinInput";
import { totalWellsNeeded } from "./designUtils";
import { parseCSVText, type ParseResult } from "../../utils/parseCompoundCSV";
import { CompoundCSVImportModal } from "./CompoundCSVImportModal";

type ValidationEntry = { level: "error" | "warning"; text: string };

interface CompoundPanelProps {
  compounds: CompoundDef[];
  solvents: SolventDef[];
  validationMessages: ValidationEntry[];
  usableWells: number;
  onCompoundsChange: (compounds: CompoundDef[]) => void;
  onSolventsChange: (solvents: SolventDef[]) => void;
  onGenerate: () => void;
  isGenerating: boolean;
  canGenerate: boolean;
}

const DEFAULT_COMPOUND = (): CompoundDef => ({ name: "", conc_entries: [] });
const DEFAULT_SOLVENT = (): SolventDef => ({ name: "", replicates: 3 });

function normalizeName(name: string): string {
  return name.trim().toLowerCase();
}

function getDuplicateIndices(names: string[]): Set<number> {
  const duplicates = new Set<number>();
  const seen = new Map<string, number[]>();

  names.forEach((name, index) => {
    const key = normalizeName(name);
    if (!key) return;
    const indices = seen.get(key) ?? [];
    indices.push(index);
    seen.set(key, indices);
  });

  seen.forEach((indices) => {
    if (indices.length > 1) {
      indices.forEach((index) => duplicates.add(index));
    }
  });

  return duplicates;
}

function getOverlappingIndices(primary: string[], secondary: string[]): Set<number> {
  const secondaryKeys = new Set(secondary.map(normalizeName).filter(Boolean));
  const overlaps = new Set<number>();

  primary.forEach((name, index) => {
    const key = normalizeName(name);
    if (key && secondaryKeys.has(key)) {
      overlaps.add(index);
    }
  });

  return overlaps;
}

interface CompoundEntryEditorProps {
  color: string;
  entry: CompoundDef;
  onChange: (updated: CompoundDef) => void;
  onRemove: () => void;
}

function CompoundEntryEditor({ color, entry, onChange, onRemove }: CompoundEntryEditorProps) {
  const entries = entry.conc_entries;
  const [dupConflict, setDupConflict] = useState<{
    existingIdx: number;
    pendingReps: number;
    sourceIdx?: number;
    prevValue?: number;
  } | null>(null);
  const [showBlankWarn, setShowBlankWarn] = useState(false);
  const [spinResetKey, setSpinResetKey] = useState(0);

  const addConc = () => {
    if (entries.some((item) => item.value_um === 0)) {
      setShowBlankWarn(true);
      return;
    }
    setShowBlankWarn(false);
    onChange({ ...entry, conc_entries: [...entries, { value_um: 0, replicates: 3 }] });
  };

  const mergeAsReplicates = () => {
    if (!dupConflict) return;
    const { existingIdx, pendingReps, sourceIdx } = dupConflict;
    setDupConflict(null);
    let next = [...entries];
    next[existingIdx] = { ...next[existingIdx], replicates: next[existingIdx].replicates + pendingReps };
    if (sourceIdx !== undefined) {
      next = next.filter((_, index) => index !== sourceIdx);
    }
    onChange({ ...entry, conc_entries: next });
  };

  const removeConc = (index: number) => {
    onChange({ ...entry, conc_entries: entries.filter((_, itemIndex) => itemIndex !== index) });
  };

  const updateConcValue = (index: number, value_um: number) => {
    setShowBlankWarn(false);
    const existing = entries.findIndex((item, itemIndex) => itemIndex !== index && item.value_um === value_um);
    if (existing !== -1) {
      setDupConflict({
        existingIdx: existing,
        pendingReps: entries[index].replicates,
        sourceIdx: index,
        prevValue: entries[index].value_um,
      });
      return;
    }
    setDupConflict((current) => (
      current?.sourceIdx === index ? null : current
    ));
    const next = [...entries];
    next[index] = { ...next[index], value_um };
    onChange({ ...entry, conc_entries: next });
  };

  const updateConcReps = (index: number, replicates: number) => {
    const next = [...entries];
    next[index] = { ...next[index], replicates: Math.max(1, replicates) };
    onChange({ ...entry, conc_entries: next });
  };

  return (
    <article className="cp-entry">
      <div className="cp-entry-bar" style={{ background: color }} />
      <div className="cp-entry-body">
        <div className="cp-entry-header">
          <input
            className="cp-entry-name"
            placeholder="Compound name…"
            value={entry.name}
            onChange={(e) => onChange({ ...entry, name: e.target.value })}
            onFocus={(e) => e.target.select()}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
            }}
          />
          <span className="cp-entry-tally">
            {entries.reduce((sum, item) => sum + item.replicates, 0)}W
          </span>
          <button type="button" className="cp-entry-remove" onClick={onRemove} title="Remove">
            ×
          </button>
        </div>

        <div className="cp-conc-block">
          {entries.map((item, index) => (
            <div key={index} className="cp-conc-row">
              <span
                className="cp-conc-swatch"
                style={{ background: getConcColor(color, index, Math.max(entries.length, 1)) }}
              />
              <SpinInput
                key={`val-${index}-${spinResetKey}`}
                min={0}
                className={`cp-conc-val${item.value_um === 0 ? " cp-conc-val--blank" : ""}`}
                placeholder="0"
                value={item.value_um}
                onChange={(value) => updateConcValue(index, value)}
              />
              <span className="cp-conc-unit">uM</span>
              <SpinInput
                min={1}
                max={20}
                className="cp-conc-reps"
                placeholder="3"
                value={item.replicates}
                onChange={(value) => updateConcReps(index, value)}
                onCommit={(value) => updateConcReps(index, value)}
              />
              <span className="cp-conc-reps-lbl">reps</span>
              <button
                type="button"
                className="cp-conc-remove"
                onClick={() => removeConc(index)}
                title="Remove"
              >
                ×
              </button>
            </div>
          ))}
          {showBlankWarn && (
            <p className="cp-blank-warn">Fill in the empty concentration before adding another.</p>
          )}
          <button type="button" className="cp-conc-add" onClick={addConc}>
            Add concentration
          </button>
        </div>

        {dupConflict !== null && (
          <div className="cp-dup-popup" role="alertdialog">
            <p className="cp-dup-msg">
              This concentration already exists for this compound. Would you like to add it as
              additional replicates instead?
            </p>
            <div className="cp-dup-actions">
              <button
                type="button"
                className="cp-dup-btn cp-dup-cancel"
                onClick={() => {
                  if (dupConflict.sourceIdx !== undefined && dupConflict.prevValue !== undefined) {
                    const next = [...entries];
                    next[dupConflict.sourceIdx] = {
                      ...next[dupConflict.sourceIdx],
                      value_um: dupConflict.prevValue,
                    };
                    onChange({ ...entry, conc_entries: next });
                  }
                  setSpinResetKey((value) => value + 1);
                  setDupConflict(null);
                }}
              >
                Edit
              </button>
              <button
                type="button"
                className="cp-dup-btn cp-dup-reps"
                onClick={mergeAsReplicates}
              >
                Add as replicates
              </button>
            </div>
          </div>
        )}
      </div>
    </article>
  );
}

interface SolventEntryEditorProps {
  entry: SolventDef;
  onChange: (updated: SolventDef) => void;
  onRemove: () => void;
}

function SolventEntryEditor({ entry, onChange, onRemove }: SolventEntryEditorProps) {
  return (
    <article className="cp-entry">
      <div className="cp-entry-bar" style={{ background: DMSO_COLOR }} />
      <div className="cp-entry-body">
        <div className="cp-entry-header">
          <input
            className="cp-entry-name"
            placeholder="Solvent name…"
            value={entry.name}
            onChange={(e) => onChange({ ...entry, name: e.target.value })}
            onFocus={(e) => e.target.select()}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
            }}
          />
          <span className="cp-entry-tally">{entry.replicates}W</span>
          <button type="button" className="cp-entry-remove" onClick={onRemove} title="Remove">
            ×
          </button>
        </div>

        <div className="cp-conc-block">
          <div className="cp-conc-row cp-solvent-row">
            <span className="cp-conc-swatch" style={{ background: DMSO_COLOR }} />
            <span className="cp-solvent-label">Replicates</span>
            <SpinInput
              min={1}
              max={48}
              className="cp-conc-reps"
              placeholder="3"
              value={entry.replicates}
              onChange={(value) => onChange({ ...entry, replicates: Math.max(1, value) })}
              onCommit={(value) => onChange({ ...entry, replicates: Math.max(1, value) })}
            />
            <span className="cp-conc-reps-lbl">reps</span>
          </div>
        </div>
      </div>
    </article>
  );
}

export function CompoundPanel({
  compounds,
  solvents,
  validationMessages,
  usableWells,
  onCompoundsChange,
  onSolventsChange,
  onGenerate,
  isGenerating,
  canGenerate,
}: CompoundPanelProps) {
  const needed = totalWellsNeeded(compounds, solvents);
  const pct = usableWells > 0 ? Math.round((needed / usableWells) * 100) : 0;

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [csvLoaded, setCsvLoaded] = useState(false);

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setParseResult(parseCSVText(ev.target?.result as string));
      e.target.value = "";
    };
    reader.readAsText(file);
  }

  function handleImportConfirm(newCompounds: CompoundDef[], newSolvents: SolventDef[]) {
    onCompoundsChange(newCompounds);
    onSolventsChange(newSolvents);
    setParseResult(null);
    setCsvLoaded(true);
  }

  function handleDeleteCSV() {
    onCompoundsChange([]);
    onSolventsChange([]);
    setCsvLoaded(false);
  }
  const hasErrors = validationMessages.some((message) => message.level === "error");

  const duplicateCompoundIndices = getDuplicateIndices(compounds.map((compound) => compound.name));
  const duplicateSolventIndices = getDuplicateIndices(solvents.map((solvent) => solvent.name));
  const overlappingCompoundIndices = getOverlappingIndices(
    compounds.map((compound) => compound.name),
    solvents.map((solvent) => solvent.name),
  );
  const overlappingSolventIndices = getOverlappingIndices(
    solvents.map((solvent) => solvent.name),
    compounds.map((compound) => compound.name),
  );

  const isOverflow = usableWells > 0 && needed > usableWells;
  const [popupDismissed, setPopupDismissed] = useState(false);
  const wasOverflowRef = useRef(isOverflow);
  useEffect(() => {
    if (isOverflow && !wasOverflowRef.current) setPopupDismissed(false);
    if (!isOverflow) setPopupDismissed(false);
    wasOverflowRef.current = isOverflow;
  }, [isOverflow]);

  const stripMessages = validationMessages.filter(
    (message) =>
      !message.text.startsWith("Too many entries") &&
      !message.text.startsWith("__blank_conc__") &&
      !message.text.startsWith("__dup_compound__") &&
      !message.text.startsWith("__dup_solvent__") &&
      !message.text.startsWith("__compound_solvent_overlap__"),
  );

  const compoundWarnings = (index: number): string[] => {
    const warnings: string[] = [];
    if (duplicateCompoundIndices.has(index)) warnings.push("This compound name is already used.");
    if (overlappingCompoundIndices.has(index)) warnings.push("This name is already used by a solvent.");
    return warnings;
  };

  const solventWarnings = (index: number): string[] => {
    const warnings: string[] = [];
    if (duplicateSolventIndices.has(index)) warnings.push("This solvent name is already used.");
    if (overlappingSolventIndices.has(index)) warnings.push("This name is already used by a compound.");
    return warnings;
  };

  return (
    <div className="design-compound-panel">
      <div className="cp-scroll">
        <div className="design-well-badge">
          <span className="design-well-count">{needed}</span>
          <span className="design-well-sep">/</span>
          <span className="design-well-total">{usableWells}</span>
          <span className="design-well-label">wells</span>
          {usableWells > 0 && (
            <div className="design-well-bar-track">
              <div
                className="design-well-bar-fill"
                style={{
                  width: `${Math.min(100, pct)}%`,
                  background:
                    pct > 100 ? "var(--icell-danger)" :
                    pct > 90 ? "#facc15" :
                    "var(--icell-success)",
                }}
              />
            </div>
          )}
        </div>

        <div className="design-section-header">
          <span className="design-section-title">Compounds</span>
        </div>
        {compounds.length === 0 && (
          <p className="cp-empty-hint">No compounds yet — click on Add to begin.</p>
        )}
        {compounds.map((compound, index) => (
          <Fragment key={index}>
            <CompoundEntryEditor
              color={getStableCompoundColor(index)}
              entry={compound}
              onChange={(updated) => {
                const next = [...compounds];
                next[index] = updated;
                onCompoundsChange(next);
              }}
              onRemove={() => onCompoundsChange(compounds.filter((_, itemIndex) => itemIndex !== index))}
            />
            {compoundWarnings(index).length > 0 && (
              <p className="cp-dup-name-warn">{compoundWarnings(index).join(" ")}</p>
            )}
          </Fragment>
        ))}
        <button
          type="button"
          className="design-add-btn"
          onClick={() => onCompoundsChange([...compounds, DEFAULT_COMPOUND()])}
        >
          Add Compound
        </button>
        {csvLoaded ? (
          <button
            type="button"
            className="design-add-btn cp-delete-csv-btn"
            onClick={handleDeleteCSV}
          >
            ✕ Delete CSV
          </button>
        ) : (
          <button
            type="button"
            className="design-add-btn cp-upload-csv-btn"
            onClick={handleUploadClick}
          >
            ↑ Upload CSV
          </button>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          style={{ display: "none" }}
          onChange={handleFileChange}
        />

        <div className="design-section-header" style={{ marginTop: 16 }}>
          <span className="design-section-title">Solvents</span>
        </div>
        {solvents.length === 0 && (
          <p className="cp-empty-hint">No solvents yet — click on Add to begin.</p>
        )}
        {solvents.map((solvent, index) => (
          <Fragment key={index}>
            <SolventEntryEditor
              entry={solvent}
              onChange={(updated) => {
                const next = [...solvents];
                next[index] = updated;
                onSolventsChange(next);
              }}
              onRemove={() => onSolventsChange(solvents.filter((_, itemIndex) => itemIndex !== index))}
            />
            {solventWarnings(index).length > 0 && (
              <p className="cp-dup-name-warn">{solventWarnings(index).join(" ")}</p>
            )}
          </Fragment>
        ))}
        <button
          type="button"
          className="design-add-btn"
          onClick={() => onSolventsChange([...solvents, DEFAULT_SOLVENT()])}
        >
          Add Solvent
        </button>

        {stripMessages.length > 0 && (
          <div className="design-validation-strip">
            {stripMessages.map((message, index) => (
              <div key={index} className={`design-validation-msg design-validation-${message.level}`}>
                {message.level === "error" ? "✗" : "⚠"} {message.text}
              </div>
            ))}
          </div>
        )}
        {!hasErrors && needed > 0 && (
          <div className="design-validation-strip">
            <div className="design-validation-msg design-validation-ok">✓ Configuration looks good</div>
          </div>
        )}
      </div>

      <div className="cp-footer">
        <button
          type="button"
          className="design-generate-btn"
          onClick={onGenerate}
          disabled={!canGenerate || isGenerating || hasErrors}
        >
          {isGenerating ? "Generating…" : "Generate Layout ▶"}
        </button>
      </div>

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

      {isOverflow && !popupDismissed && (
        <div className="dpv-overflow-popup" role="alert">
          <span className="dpv-overflow-icon">✗</span>
          <p className="dpv-overflow-msg">
            Too many entries: <strong>{needed}</strong> wells assigned, only <strong>{usableWells}</strong>{" "}
            available.
          </p>
          <button
            type="button"
            className="dpv-overflow-dismiss"
            aria-label="Dismiss"
            onClick={() => setPopupDismissed(true)}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
