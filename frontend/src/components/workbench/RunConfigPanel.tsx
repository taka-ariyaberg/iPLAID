import type { BootstrapResponse, RunConfig } from "../../types";
import { SpinInput } from "./SpinInput";
import "./RunConfigPanel.css";

const numericFields: Array<keyof RunConfig> = [
  "working_volume_ul",
  "max_dmso_pct",
  "source_prep_overage_pct",
  "min_pipette_volume_uL",
  "source_well_fill_pct",
  "standard_prep_volume_uL",
];

type RunConfigPanelProps = {
  config: RunConfig;
  bootstrap: BootstrapResponse;
  processing: boolean;
  canProcess: boolean;
  onConfigChange: (field: keyof RunConfig, value: string) => void;
  onProcess: () => void;
  sourceLayoutFile?: File | null;
  onSourceLayoutFileChange?: (file: File | null) => void;
};

type NumericFieldProps = {
  label: string;
  field: typeof numericFields[number];
  value: number;
  min: number;
  step: number;
  onConfigChange: (field: keyof RunConfig, value: string) => void;
};

function NumericField({ label, field, value, min, step, onConfigChange }: NumericFieldProps) {
  return (
    <label>
      <span>{label}</span>
      <SpinInput
        value={value}
        min={min}
        step={step}
        className="design-num-input"
        onChange={(nextValue) => onConfigChange(field, String(nextValue))}
        onCommit={(nextValue) => onConfigChange(field, String(nextValue))}
      />
    </label>
  );
}

export function RunConfigPanel({
  config,
  bootstrap,
  processing,
  canProcess,
  onConfigChange,
  onProcess,
  sourceLayoutFile,
  onSourceLayoutFileChange,
}: RunConfigPanelProps) {
  return (
    <section className="workbench-config panel-surface">
      <div className="panel-header-row">
        <div>
          <p className="section-kicker">Configuration</p>
          <h3>Run settings</h3>
        </div>
      </div>

      <div className="config-form">
        <label>
          <span>User name</span>
          <input
            value={config.user_name}
            onChange={(e) => onConfigChange("user_name", e.target.value)}
          />
        </label>

        <label>
          <span>Protocol name</span>
          <input
            value={config.protocol_name}
            onChange={(e) => onConfigChange("protocol_name", e.target.value)}
          />
        </label>

        {bootstrap.dispensers && bootstrap.dispensers.length > 0 && (
          <label>
            <span>Dispenser</span>
            <select
              value={config.dispenser}
              onChange={(e) => onConfigChange("dispenser", e.target.value)}
            >
              {bootstrap.dispensers.map((d) => (
                <option key={d.name} value={d.name}>
                  {d.display_name}
                </option>
              ))}
            </select>
          </label>
        )}

        <label>
          <span>Source plate</span>
          <select
            value={config.sourceplate_type}
            onChange={(e) => onConfigChange("sourceplate_type", e.target.value)}
          >
            {(bootstrap.plate_types_by_dispenser?.[config.dispenser] ?? bootstrap.sourcePlateTypes).map(
              (plateType) => (
                <option key={plateType} value={plateType}>
                  {plateType}
                </option>
              ),
            )}
          </select>
        </label>

        {onSourceLayoutFileChange && (
          <label>
            <span>Source plate layout (optional)</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => onSourceLayoutFileChange(e.target.files?.[0] ?? null)}
            />
            {sourceLayoutFile && (
              <small style={{ display: "block", marginTop: 4, opacity: 0.7 }}>
                Using {sourceLayoutFile.name}.{" "}
                <button
                  type="button"
                  onClick={() => onSourceLayoutFileChange(null)}
                  style={{ background: "none", border: "none", padding: 0, color: "inherit", cursor: "pointer", textDecoration: "underline" }}
                >
                  Clear
                </button>
              </small>
            )}
          </label>
        )}

        <label>
          <span>Dilution solvent</span>
          <input
            value={config.dilution_solvent}
            onChange={(e) => onConfigChange("dilution_solvent", e.target.value)}
          />
        </label>

        <NumericField
          label="Working volume (uL)"
          field="working_volume_ul"
          value={config.working_volume_ul}
          min={0}
          step={0.1}
          onConfigChange={onConfigChange}
        />

        <NumericField
          label="Max solvent (%)"
          field="max_dmso_pct"
          value={config.max_dmso_pct}
          min={0}
          step={0.01}
          onConfigChange={onConfigChange}
        />

        <NumericField
          label="Prep overage (%)"
          field="source_prep_overage_pct"
          value={config.source_prep_overage_pct}
          min={0}
          step={0.01}
          onConfigChange={onConfigChange}
        />

        <NumericField
          label="Minimum pipette volume (uL)"
          field="min_pipette_volume_uL"
          value={config.min_pipette_volume_uL}
          min={0}
          step={0.1}
          onConfigChange={onConfigChange}
        />

        <NumericField
          label="Source well fill (%)"
          field="source_well_fill_pct"
          value={config.source_well_fill_pct}
          min={0}
          step={0.01}
          onConfigChange={onConfigChange}
        />

        <NumericField
          label="Standard prep volume (uL)"
          field="standard_prep_volume_uL"
          value={config.standard_prep_volume_uL}
          min={0}
          step={1}
          onConfigChange={onConfigChange}
        />
      </div>

      <button
        className="primary-action workbench-process-button"
        disabled={!canProcess || processing}
        onClick={onProcess}
      >
        {processing ? "Submitting..." : "Run iPLAID"}
      </button>
    </section>
  );
}

export { numericFields };
