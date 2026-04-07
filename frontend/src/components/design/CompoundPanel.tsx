/**
 * CompoundPanel — right panel of the Design mode.
 * Lets users add/edit/remove compounds and controls, each with:
 *   - named concentration values added one by one (µM)
 *   - replicate count
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { CompoundDef, ControlDef } from "../../types";
import { getStableCompoundColor, getConcColor, DMSO_COLOR } from "../../utils/colorUtils";
import { SpinInput } from "./SpinInput";
import { totalWellsNeeded } from "./designUtils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ValidationEntry = { level: "error" | "warning"; text: string };

interface CompoundPanelProps {
  compounds: CompoundDef[];
  controls: ControlDef[];
  validationMessages: ValidationEntry[];
  usableWells: number;
  onCompoundsChange: (compounds: CompoundDef[]) => void;
  onControlsChange: (controls: ControlDef[]) => void;
  onGenerate: () => void;
  isGenerating: boolean;
  canGenerate: boolean;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULT_COMPOUND = (): CompoundDef => ({ name: "", conc_entries: [] });
const DEFAULT_CONTROL  = (): ControlDef  => ({ name: "", conc_entries: [] });

// ---------------------------------------------------------------------------
// Entry editor (compound or control card)
// ---------------------------------------------------------------------------

interface EntryEditorProps {
  isControl: boolean;
  color: string;
  entry: CompoundDef | ControlDef;
  onChange: (updated: CompoundDef | ControlDef) => void;
  onRemove: () => void;
}

function EntryEditor({ isControl, color, entry, onChange, onRemove }: EntryEditorProps) {
  const entries = entry.conc_entries;
  // Pending conflict: existing index to merge into, replicates to add, and
  // optionally the source index + prevValue when editing an existing row.
  const [dupConflict, setDupConflict] = useState<{
    existingIdx: number;
    pendingReps: number;
    sourceIdx?: number;
    prevValue?: number;
  } | null>(null);
  // Incrementing this key remounts the SpinInput(s) so their draft resets.
  const [spinResetKey, setSpinResetKey] = useState(0);

  const addConc = () => {
    const existing = entries.findIndex((e) => e.value_um === 0);
    if (existing !== -1) {
      setDupConflict({ existingIdx: existing, pendingReps: 3 });
      return;
    }
    onChange({ ...entry, conc_entries: [...entries, { value_um: 0, replicates: 3 }] });
  };

  const mergeAsReplicates = () => {
    if (!dupConflict) return;
    const { existingIdx, pendingReps, sourceIdx } = dupConflict;
    setDupConflict(null);
    let next = [...entries];
    next[existingIdx] = { ...next[existingIdx], replicates: next[existingIdx].replicates + pendingReps };
    // If the conflict came from editing an existing row, remove that row.
    if (sourceIdx !== undefined) {
      next = next.filter((_, j) => j !== sourceIdx);
    }
    onChange({ ...entry, conc_entries: next });
  };

  const removeConc = (i: number) => {
    onChange({ ...entry, conc_entries: entries.filter((_, j) => j !== i) });
  };

  const updateConcValue = (i: number, value_um: number) => {
    const existing = entries.findIndex((e, j) => j !== i && e.value_um === value_um);
    if (existing !== -1) {
      setDupConflict({ existingIdx: existing, pendingReps: entries[i].replicates, sourceIdx: i, prevValue: entries[i].value_um });
      return;
    }
    const next = [...entries];
    next[i] = { ...next[i], value_um };
    onChange({ ...entry, conc_entries: next });
  };

  const updateConcReps = (i: number, replicates: number) => {
    const next = [...entries];
    next[i] = { ...next[i], replicates: Math.max(1, replicates) };
    onChange({ ...entry, conc_entries: next });
  };

  return (
    <article className="cp-entry">
      <div className="cp-entry-bar" style={{ background: color }} />
      <div className="cp-entry-body">
        {/* Header: name input + well tally + remove */}
        <div className="cp-entry-header">
          <input
            className="cp-entry-name"
            placeholder={isControl ? "Control name…" : "Compound name…"}
            value={entry.name}
            onChange={(e) => onChange({ ...entry, name: e.target.value })}
            onFocus={(e) => e.target.select()}
            onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
          />
          <span className="cp-entry-tally">
            {entries.reduce((s, e) => s + e.replicates, 0)}W
          </span>
          <button className="cp-entry-remove" onClick={onRemove} title="Remove">×</button>
        </div>

        {/* Concentration rows with colored swatches */}
        <div className="cp-conc-block">
          {entries.map((e, i) => (
            <div key={i} className="cp-conc-row">
              <span
                className="cp-conc-swatch"
                style={{ background: getConcColor(color, i, Math.max(entries.length, 1)) }}
              />
              <SpinInput
                key={`val-${i}-${spinResetKey}`}
                min={0}
                className="cp-conc-val"
                placeholder="0"
                value={e.value_um}
                onChange={(v) => updateConcValue(i, v)}
              />
              <span className="cp-conc-unit">µM</span>
              <SpinInput
                min={1}
                max={20}
                className="cp-conc-reps"
                placeholder="3"
                value={e.replicates}
                onChange={(v) => updateConcReps(i, v)}
                onCommit={(v) => updateConcReps(i, v)}
              />
              <span className="cp-conc-reps-lbl">reps</span>
              <button className="cp-conc-remove" onClick={() => removeConc(i)} title="Remove">×</button>
            </div>
          ))}
          <button className="cp-conc-add" onClick={addConc}>Add concentration</button>
        </div>

        {dupConflict !== null && (
          <div className="cp-dup-popup" role="alertdialog">
            <p className="cp-dup-msg">
              This concentration already exists for this {isControl ? "control" : "compound"}.
              Would you like to add it as additional replicates instead?
            </p>
            <div className="cp-dup-actions">
              <button className="cp-dup-btn cp-dup-cancel" onClick={() => {
                if (dupConflict.sourceIdx !== undefined && dupConflict.prevValue !== undefined) {
                  // Restore the row to its previous value so user can retype
                  const next = [...entries];
                  next[dupConflict.sourceIdx] = { ...next[dupConflict.sourceIdx], value_um: dupConflict.prevValue };
                  onChange({ ...entry, conc_entries: next });
                }
                setSpinResetKey((k) => k + 1);
                setDupConflict(null);
              }}>Edit</button>
              <button className="cp-dup-btn cp-dup-reps" onClick={mergeAsReplicates}>Add as replicates</button>
            </div>
          </div>
        )}
      </div>
    </article>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function CompoundPanel({
  compounds,
  controls,
  validationMessages,
  usableWells,
  onCompoundsChange,
  onControlsChange,
  onGenerate,
  isGenerating,
  canGenerate,
}: CompoundPanelProps) {
  const needed = totalWellsNeeded(compounds, controls);
  const pct = usableWells > 0 ? Math.round((needed / usableWells) * 100) : 0;
  const hasErrors = validationMessages.some((m) => m.level === "error");

  // Overflow popup: re-shows whenever overflow newly appears, auto-clears when fixed.
  const isOverflow = usableWells > 0 && needed > usableWells;
  const [popupDismissed, setPopupDismissed] = useState(false);
  const wasOverflowRef = useRef(isOverflow);
  useEffect(() => {
    if (isOverflow && !wasOverflowRef.current) setPopupDismissed(false);
    if (!isOverflow) setPopupDismissed(false);
    wasOverflowRef.current = isOverflow;
  }, [isOverflow]);

  // Overflow error is shown in the toast, not the inline strip.
  const stripMessages = validationMessages.filter((m) => !m.text.startsWith("Too many entries"));

  const updateCompound = useCallback(
    (i: number, u: CompoundDef | ControlDef) => {
      const updated = [...compounds];
      updated[i] = u as CompoundDef;
      onCompoundsChange(updated);
    },
    [compounds, onCompoundsChange],
  );

  const updateControl = useCallback(
    (i: number, u: CompoundDef | ControlDef) => {
      const updated = [...controls];
      updated[i] = u as ControlDef;
      onControlsChange(updated);
    },
    [controls, onControlsChange],
  );

  return (
    <div className="design-compound-panel">
      <div className="cp-scroll">
        {/* Well usage badge */}
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
                    pct > 90  ? "var(--icell-warning)" :
                                "var(--icell-accent)",
                }}
              />
            </div>
          )}
        </div>

        {/* Compounds */}
        <div className="design-section-header">
          <span className="design-section-title">Compounds</span>
        </div>
        {compounds.length === 0 && (
          <p className="cp-empty-hint">No compounds yet — click on Add to begin.</p>
        )}
        {compounds.map((c, i) => (
          <EntryEditor
            key={i}
            isControl={false}
            color={getStableCompoundColor(i)}
            entry={c}
            onChange={(u) => updateCompound(i, u)}
            onRemove={() => onCompoundsChange(compounds.filter((_, j) => j !== i))}
          />
        ))}
        <button
          className="design-add-btn"
          onClick={() => onCompoundsChange([...compounds, DEFAULT_COMPOUND()])}
        >
          Add Compound
        </button>

        {/* Controls */}
        <div className="design-section-header" style={{ marginTop: 16 }}>
          <span className="design-section-title">Controls</span>
        </div>
        {controls.length === 0 && (
          <p className="cp-empty-hint">No controls yet — click on Add to begin.</p>
        )}
        {controls.map((c, i) => (
          <EntryEditor
            key={i}
            isControl
            color={DMSO_COLOR}
            entry={c}
            onChange={(u) => updateControl(i, u)}
            onRemove={() => onControlsChange(controls.filter((_, j) => j !== i))}
          />
        ))}
        <button
          className="design-add-btn"
          onClick={() => onControlsChange([...controls, DEFAULT_CONTROL()])}
        >
          Add Control
        </button>

        {/* Validation strip (overflow shown in toast, not here) */}
        {stripMessages.length > 0 && (
          <div className="design-validation-strip">
            {stripMessages.map((m, i) => (
              <div key={i} className={`design-validation-msg design-validation-${m.level}`}>
                {m.level === "error" ? "✗" : "⚠"} {m.text}
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

      {/* Footer: generate button */}
      <div className="cp-footer">
        <button
          className="design-generate-btn"
          onClick={onGenerate}
          disabled={!canGenerate || isGenerating || hasErrors}
        >
          {isGenerating ? "Generating…" : "Generate Layout ▶"}
        </button>
      </div>

      {/* Overflow toast */}
      {isOverflow && !popupDismissed && (
        <div className="dpv-overflow-popup" role="alert">
          <span className="dpv-overflow-icon">✗</span>
          <p className="dpv-overflow-msg">
            Too many entries: <strong>{needed}</strong> wells assigned,
            only <strong>{usableWells}</strong> available.
          </p>
          <button
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
