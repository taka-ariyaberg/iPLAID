import type { BootstrapResponse, RunConfig } from "../../types";
import { ConfigDropdown } from "./ConfigDropdown";
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
          <div className="config-form-field">
            <span>Dispenser</span>
            <ConfigDropdown
              ariaLabel="Dispenser"
              value={config.dispenser}
              options={bootstrap.dispensers.map((d) => ({
                value: d.name,
                label: d.display_name,
              }))}
              onChange={(v) => onConfigChange("dispenser", v)}
            />
          </div>
        )}

        <div className="config-form-field">
          <span>Source plate type</span>
          <ConfigDropdown
            ariaLabel="Source plate type"
            value={config.sourceplate_type}
            options={(bootstrap.plate_types_by_dispenser?.[config.dispenser] ?? bootstrap.sourcePlateTypes).map(
              (plateType) => ({ value: plateType, label: plateType }),
            )}
            onChange={(v) => onConfigChange("sourceplate_type", v)}
          />
        </div>

        {onSourceLayoutFileChange && (
          <div className="config-form-field">
            <span>Source plate layout</span>
            <div className={`config-upload-zone ${sourceLayoutFile ? "is-loaded" : ""}`}>
              <label className="config-upload-zone-target" htmlFor="config-upload-source-layout">
                <div className="config-upload-zone-icon" aria-hidden="true">
                  {sourceLayoutFile ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  )}
                </div>
                <div className="config-upload-zone-body">
                  <span className="config-upload-zone-title">
                    {sourceLayoutFile ? sourceLayoutFile.name : "Upload layout CSV"}
                  </span>
                </div>
              </label>
              <input
                key={sourceLayoutFile?.name ?? "source-layout-empty"}
                id="config-upload-source-layout"
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => onSourceLayoutFileChange(e.target.files?.[0] ?? null)}
              />
              <div className="config-upload-zone-right">
                <div className={`config-upload-zone-badge ${sourceLayoutFile ? "is-loaded" : "is-optional"}`}>
                  {sourceLayoutFile ? "Loaded" : "Optional"}
                </div>
                {sourceLayoutFile && (
                  <button
                    type="button"
                    className="config-upload-zone-clear"
                    title="Remove file"
                    aria-label="Remove file"
                    onClick={() => onSourceLayoutFileChange(null)}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          </div>
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
