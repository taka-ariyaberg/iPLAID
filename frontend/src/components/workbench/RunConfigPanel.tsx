import type { BootstrapResponse, RunConfig } from "../../types";
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
};

export function RunConfigPanel({
  config,
  bootstrap,
  processing,
  canProcess,
  onConfigChange,
  onProcess,
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
          <input value={config.user_name} onChange={(e) => onConfigChange("user_name", e.target.value)} />
        </label>

        <label>
          <span>Protocol name</span>
          <input value={config.protocol_name} onChange={(e) => onConfigChange("protocol_name", e.target.value)} />
        </label>

        <label>
          <span>Source plate</span>
          <select value={config.sourceplate_type} onChange={(e) => onConfigChange("sourceplate_type", e.target.value)}>
            {bootstrap.sourcePlateTypes.map((pt) => (
              <option key={pt} value={pt}>{pt}</option>
            ))}
          </select>
        </label>

        <label>
          <span>Working volume (µL)</span>
          <input type="number" min="0" step="0.1" value={config.working_volume_ul} onChange={(e) => onConfigChange("working_volume_ul", e.target.value)} />
        </label>

        <label>
          <span>Max DMSO (%)</span>
          <input type="number" min="0" step="0.01" value={config.max_dmso_pct} onChange={(e) => onConfigChange("max_dmso_pct", e.target.value)} />
        </label>

        <label>
          <span>Prep overage (%)</span>
          <input type="number" min="0" step="0.01" value={config.source_prep_overage_pct} onChange={(e) => onConfigChange("source_prep_overage_pct", e.target.value)} />
        </label>

        <label>
          <span>Minimum pipette volume (µL)</span>
          <input type="number" min="0" step="0.1" value={config.min_pipette_volume_uL} onChange={(e) => onConfigChange("min_pipette_volume_uL", e.target.value)} />
        </label>

        <label>
          <span>Dilution solvent</span>
          <input value={config.dilution_solvent} onChange={(e) => onConfigChange("dilution_solvent", e.target.value)} />
        </label>

        <label>
          <span>Source well fill (%)</span>
          <input type="number" min="0" step="0.01" value={config.source_well_fill_pct} onChange={(e) => onConfigChange("source_well_fill_pct", e.target.value)} />
        </label>

        <label>
          <span>Standard prep volume (µL)</span>
          <input type="number" min="0" step="1" value={config.standard_prep_volume_uL} onChange={(e) => onConfigChange("standard_prep_volume_uL", e.target.value)} />
        </label>
      </div>

      <button
        className="primary-action workbench-process-button"
        disabled={!canProcess || processing}
        onClick={onProcess}
      >
        {processing ? "Submitting…" : "Run iPLAID"}
      </button>
    </section>
  );
}

export { numericFields };
