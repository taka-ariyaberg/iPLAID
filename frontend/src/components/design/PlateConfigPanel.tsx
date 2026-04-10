/**
 * PlateConfigPanel — left panel of Design mode.
 * Exposes all PlateConfig / solver parameters, grouped into collapsible sections.
 */

import React, { useCallback } from "react";
import type { DesignConfig } from "../../types";
import { SpinInput } from "./SpinInput";

interface PlateConfigPanelProps {
  config: DesignConfig;
  onChange: (updated: DesignConfig) => void;
  /** Plate type options from bootstrap (uses rows/cols, not as source plate) */
  targetPlateOptions: Array<{ id: string; label: string; rows: number; cols: number }>;
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function Toggle({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="design-toggle-row" title={hint}>
      <span className="design-toggle-label">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={value}
        className={`design-toggle-btn${value ? " design-toggle-on" : ""}`}
        onClick={() => onChange(!value)}
      >
        <span className="design-toggle-thumb" />
      </button>
    </label>
  );
}

function NumberField({
  label,
  hint,
  value,
  min,
  max,
  onChange,
  readOnly = false,
}: {
  label: string;
  hint?: string;
  value: number;
  min?: number;
  max?: number;
  onChange: (v: number) => void;
  readOnly?: boolean;
}) {
  return (
    <label className="design-num-row" title={hint}>
      <span className="design-num-label">{label}</span>
      <SpinInput
        className="design-num-input"
        value={value}
        min={min}
        max={max}
        onChange={onChange}
        onCommit={onChange}
        readOnly={readOnly}
      />
    </label>
  );
}

function Section({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  return (
    <details className="design-config-section" open={defaultOpen}>
      <summary className="design-config-section-title">{title}</summary>
      <div className="design-config-section-body">{children}</div>
    </details>
  );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export function PlateConfigPanel({ config, onChange, targetPlateOptions }: PlateConfigPanelProps) {
  const patch = useCallback(
    (updates: Partial<DesignConfig>) => onChange({ ...config, ...updates }),
    [config, onChange]
  );

  // Derive which preset (if any) matches the current rows × cols
  const matchedPreset = targetPlateOptions.find(
    (p) => p.rows === config.plate_rows && p.cols === config.plate_cols
  );
  const presetValue = matchedPreset ? `${matchedPreset.rows}x${matchedPreset.cols}` : "custom";
  const isCustom = presetValue === "custom";

  return (
    <div className="design-config-panel">
      {/* ----- Plate geometry (always open) ----- */}
      <Section title="Plate geometry" defaultOpen>
        <label className="design-num-row">
          <span className="design-num-label">Preset</span>
          <select
            className="design-select"
            value={presetValue}
            onChange={(e) => {
              if (e.target.value === "custom") return; // let user edit rows/cols directly
              const opt = targetPlateOptions.find(
                (p) => `${p.rows}x${p.cols}` === e.target.value
              );
              if (opt) patch({ plate_rows: opt.rows, plate_cols: opt.cols });
            }}
          >
            <option value="custom">Custom</option>
            {targetPlateOptions.map((p) => (
              <option key={p.id} value={`${p.rows}x${p.cols}`}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <NumberField
          label="Rows"
          hint="Number of plate rows — editing this switches to Custom"
          value={config.plate_rows}
          min={4}
          max={48}
          onChange={(v) => patch({ plate_rows: v })}
        />
        <NumberField
          label="Columns"
          hint="Number of plate columns — editing this switches to Custom"
          value={config.plate_cols}
          min={4}
          max={48}
          onChange={(v) => patch({ plate_cols: v })}
        />
        {isCustom && (
          <div className="design-config-custom-hint">
            Custom: {config.plate_rows}×{config.plate_cols} ({config.plate_rows * config.plate_cols} wells)
          </div>
        )}
        <NumberField
          label="Empty edge"
          hint="Set manually to select a symmetric border, or draw a region on the plate — both keep each other in sync"
          value={config.empty_edge}
          min={0}
          max={Math.floor(Math.min(config.plate_rows, config.plate_cols) / 2) - 1}
          onChange={(v) => patch({ empty_edge: v })}
        />
      </Section>

      {/* ----- Replicate placement ----- */}
      <Section title="Replicate placement">
        <Toggle
          label="Replicates on same plate"
          hint="Keep all replicates of each compound on the same plate"
          value={config.replicates_on_same_plate}
          onChange={(v) => patch({ replicates_on_same_plate: v, replicates_on_different_plates: !v })}
        />
        <Toggle
          label="Replicates on different plates"
          hint="Spread replicates of each compound across multiple plates"
          value={config.replicates_on_different_plates}
          onChange={(v) => patch({ replicates_on_different_plates: v, replicates_on_same_plate: !v })}
        />
        <Toggle
          label="Allow empty wells"
          hint="Solver may leave some wells unfilled when no compound fits"
          value={config.allow_empty_wells}
          onChange={(v) => patch({ allow_empty_wells: v })}
        />
      </Section>

      {/* ----- Concentration layout ----- */}
      <Section title="Concentration layout">
        <Toggle
          label="Different rows"
          hint="Place different concentrations of the same compound in different rows"
          value={config.concentrations_on_different_rows}
          onChange={(v) => patch({ concentrations_on_different_rows: v })}
        />
        <Toggle
          label="Different columns"
          hint="Place different concentrations of the same compound in different columns"
          value={config.concentrations_on_different_columns}
          onChange={(v) => patch({ concentrations_on_different_columns: v })}
        />
        <Toggle
          label="Force spread concentrations"
          hint="Apply proven bounds to force concentration spreading (advanced)"
          value={config.force_spread_concentrations}
          onChange={(v) => patch({ force_spread_concentrations: v })}
        />
      </Section>

      {/* ----- Solvent layout ----- */}
      <Section title="Solvent layout">
        <Toggle
          label="Balance solvents per plate"
          hint="Distribute solvent-only wells evenly within each plate"
          value={config.balance_controls_inside_plate}
          onChange={(v) => patch({ balance_controls_inside_plate: v })}
        />
        <Toggle
          label="Force spread solvents"
          hint="Apply proven bounds to force solvent spreading (advanced)"
          value={config.force_spread_controls}
          onChange={(v) => patch({ force_spread_controls: v })}
        />
        <NumberField
          label="Solvent slack"
          hint="Higher values allow more flexibility in solvent distribution (0 = strict)"
          value={config.control_slack}
          min={0}
          max={20}
          onChange={(v) => patch({ control_slack: v })}
        />
      </Section>

      {/* ----- Multi-plate ----- */}
      <Section title="Multi-plate">
        <Toggle
          label="Interconnected plates"
          hint="Consider all plates together for globally optimal distribution"
          value={config.interconnected_plates}
          onChange={(v) => patch({ interconnected_plates: v })}
        />
      </Section>

      {/* ----- Cell lines ----- */}
      <Section title="Cell lines">
        <NumberField
          label="Horizontal cell lines"
          hint="Number of cell line subdivisions along plate rows"
          value={config.horizontal_cell_lines}
          min={1}
          max={config.plate_rows}
          onChange={(v) => patch({ horizontal_cell_lines: v })}
        />
        <NumberField
          label="Vertical cell lines"
          hint="Number of cell line subdivisions along plate columns"
          value={config.vertical_cell_lines}
          min={1}
          max={config.plate_cols}
          onChange={(v) => patch({ vertical_cell_lines: v })}
        />
      </Section>

      {/* ----- Solver ----- */}
      <Section title="Solver">
        <NumberField
          label="Timeout (s)"
          hint="Maximum solver runtime in seconds"
          value={config.timeout_seconds}
          min={1}
          max={120}
          onChange={(v) => patch({ timeout_seconds: v })}
        />
        <NumberField
          label="Threads"
          hint="Parallel solver threads (Gecode)"
          value={config.num_threads}
          min={1}
          max={8}
          onChange={(v) => patch({ num_threads: v })}
        />
        <label className="design-num-row">
          <span className="design-num-label">Random seed</span>
          <SpinInput
            className="design-num-input"
            value={config.random_seed ?? 0}
            min={0}
            placeholder="auto"
            onChange={(v) => patch({ random_seed: v === 0 ? null : v })}
            onCommit={(v) => patch({ random_seed: v === 0 ? null : v })}
          />
        </label>
      </Section>
    </div>
  );
}
