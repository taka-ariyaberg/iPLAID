/**
 * DesignPanel — self-contained PLAID_Core layout designer.
 *
 * Rendered in place of PlateViewerPanel when the user activates design mode.
 * Manages all its own state (designConfig, designJob, polling).
 * On success calls onComplete(layoutFile, preview) so WorkbenchPage can
 * treat the generated layout like a manually-uploaded CSV.
 */

import { useEffect, useRef, useState } from "react";
import { CompoundPanel } from "./CompoundPanel";
import { DesignPlateViewer } from "./DesignPlateViewer";
import { PlateConfigPanel } from "./PlateConfigPanel";
import { totalWellsNeeded } from "./designUtils";
import { apiClient } from "../../services/apiClient";
import type {
  BootstrapResponse,
  DesignConfig,
  DesignJob,
  LayoutPreview,
} from "../../types";
import "../../styles/DesignMode.css";
import "../../styles/DesignPanel.css";

// ---------------------------------------------------------------------------
// Helpers (self-contained — no coupling to WorkbenchPage)
// ---------------------------------------------------------------------------

function defaultDesignConfig(rows = 16, cols = 24): DesignConfig {
  return {
    plate_rows: rows,
    plate_cols: cols,
    empty_edge: 1,
    compounds: [],
    solvents: [],
    concentrations_on_different_rows: true,
    concentrations_on_different_columns: true,
    replicates_on_same_plate: true,
    replicates_on_different_plates: false,
    allow_empty_wells: true,
    balance_controls_inside_plate: true,
    interconnected_plates: true,
    control_slack: 0,
    force_spread_controls: false,
    force_spread_concentrations: false,
    horizontal_cell_lines: 1,
    vertical_cell_lines: 1,
    timeout_seconds: 30,
    num_threads: 4,
    random_seed: null,
  };
}

function buildValidationMessages(dc: DesignConfig) {
  const msgs: Array<{ level: "error" | "warning"; text: string }> = [];
  if (dc.compounds.length === 0 && dc.solvents.length === 0) {
    msgs.push({ level: "error", text: "Add at least one compound or solvent." });
  }
  const usable = Math.max(0, (dc.plate_rows - 2 * dc.empty_edge) * (dc.plate_cols - 2 * dc.empty_edge));
  const needed = totalWellsNeeded(dc.compounds, dc.solvents);
  if (needed > usable) {
    msgs.push({
      level: "error",
      text: `Too many entries: ${needed} wells assigned, only ${usable} available.`,
    });
  } else if (needed > usable * 0.9) {
    msgs.push({
      level: "warning",
      text: `Tight fit: ${needed}/${usable} wells used (>90%).`,
    });
  }
  if (dc.replicates_on_same_plate && dc.replicates_on_different_plates) {
    msgs.push({ level: "error", text: "Cannot use both same-plate and different-plate replicate strategies." });
  }
  if (!dc.replicates_on_same_plate && !dc.replicates_on_different_plates) {
    msgs.push({ level: "error", text: "Select a replicate placement strategy." });
  }
  dc.compounds.forEach((c, i) => {
    if (!c.name.trim()) msgs.push({ level: "error", text: `Compound ${i + 1} has no name.` });
    if (c.conc_entries.some((e) => e.value_um === 0))
      msgs.push({ level: "error", text: `__blank_conc__:${c.name || `#${i + 1}`}` });
  });
  const cmpNames = dc.compounds.map((c) => c.name.trim().toLowerCase()).filter(Boolean);
  if (new Set(cmpNames).size < cmpNames.length)
    msgs.push({ level: "error", text: "__dup_compound__" });
  dc.solvents.forEach((solvent, i) => {
    if (!solvent.name.trim()) msgs.push({ level: "error", text: `Solvent ${i + 1} has no name.` });
  });
  const solventNames = dc.solvents.map((solvent) => solvent.name.trim().toLowerCase()).filter(Boolean);
  if (new Set(solventNames).size < solventNames.length) {
    msgs.push({ level: "error", text: "__dup_solvent__" });
  }
  if (cmpNames.some((name) => solventNames.includes(name))) {
    msgs.push({ level: "error", text: "__compound_solvent_overlap__" });
  }
  return msgs;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface DesignPanelProps {
  bootstrap: BootstrapResponse;
  onComplete: (layoutFile: File, preview: LayoutPreview) => void;
  onCancel: () => void;
  onError: (msg: string) => void;
}

export function DesignPanel({ bootstrap, onComplete, onCancel, onError }: DesignPanelProps) {
  // Initialise to 384-well if available, otherwise 16×24
  const [designConfig, setDesignConfig] = useState<DesignConfig>(() => {
    const p384 = bootstrap.targetPlateDefinitions.find((p) => p.wells === 384);
    return defaultDesignConfig(p384?.rows ?? 16, p384?.cols ?? 24);
  });

  const [designJob, setDesignJob] = useState<DesignJob | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const pollRef      = useRef<ReturnType<typeof setInterval> | null>(null);
  const designJobRef = useRef<DesignJob | null>(null);
  const isMountedRef = useRef(true);
  const cancelAfterStartRef = useRef(false);
  designJobRef.current = designJob;

  useEffect(() => {
    isMountedRef.current = true;
    cancelAfterStartRef.current = false;

    return () => {
      isMountedRef.current = false;
      cancelAfterStartRef.current = true;
      if (pollRef.current) clearInterval(pollRef.current);
      const activeJob = designJobRef.current;
      if (activeJob && (activeJob.status === "queued" || activeJob.status === "running")) {
        void apiClient.cancelDesignJob(activeJob.jobId).catch(() => undefined);
      }
    };
  }, []);

  const validationMessages = buildValidationMessages(designConfig);
  const canGenerate = validationMessages.every((m) => m.level !== "error");
  const usableWells = Math.max(
    0,
    (designConfig.plate_rows - 2 * designConfig.empty_edge) *
      (designConfig.plate_cols - 2 * designConfig.empty_edge)
  );

  async function handleGenerate() {
    if (!canGenerate) return;
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    cancelAfterStartRef.current = false;
    setIsGenerating(true);
    setDesignJob(null);
    try {
      const job = await apiClient.solveDesign(designConfig);
      if (!isMountedRef.current || cancelAfterStartRef.current) {
        void apiClient.cancelDesignJob(job.jobId).catch(() => undefined);
        return;
      }
      setDesignJob(job);
      pollRef.current = setInterval(async () => {
        try {
          const updated = await apiClient.getDesignJob(job.jobId);
          if (!isMountedRef.current) return;
          setDesignJob(updated);
          if (updated.status === "completed" || updated.status === "failed") {
            clearInterval(pollRef.current!);
            pollRef.current = null;
            setIsGenerating(false);
            if (updated.status === "failed") {
              onError(updated.error?.message ?? "Solver failed.");
            }
          }
        } catch {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          if (isMountedRef.current) {
            setIsGenerating(false);
          }
        }
      }, 2000);
    } catch (err) {
      if (isMountedRef.current) {
        onError(err instanceof Error ? err.message : "Failed to start solver.");
        setIsGenerating(false);
      }
    }
  }

  function handleCancel() {
    cancelAfterStartRef.current = true;
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    setIsGenerating(false);
    const activeJob = designJobRef.current;
    if (activeJob && (activeJob.status === "queued" || activeJob.status === "running")) {
      void apiClient.cancelDesignJob(activeJob.jobId).catch(() => undefined);
    }
    onCancel();
  }

  async function handleUseLayout() {
    if (!designJob || designJob.status !== "completed" || !designJob.layoutPreview) return;
    const layoutUrl = apiClient.designArtifactUrl(designJob.jobId, "designed_layout.csv");
    try {
      const lr = await fetch(layoutUrl);
      const layoutBlob = await lr.blob();
      const lf = new File([layoutBlob], "designed_layout.csv", { type: "text/csv" });
      onComplete(lf, designJob.layoutPreview);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to load generated layout file.");
    }
  }

  const solvedPreview =
    designJob?.status === "completed" ? (designJob.layoutPreview ?? undefined) : undefined;
  const designPhase = designJob?.phase ?? "queued";
  const runningLabel = designPhase === "preflight" ? "Checking inputs…" : "Solving…";

  return (
    <section className="panel-surface dp-panel">
      {/* ── Header ── */}
      <div className="dp-header">
        <div>
          <h3 className="dp-title">Design Plate Layout</h3>
        </div>
        <button type="button" className="dp-cancel-btn" onClick={handleCancel} title="Cancel design">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* ── Three-column body ── */}
      <div className="dp-body">
        {/* Left: plate geometry + solver settings */}
        <div className="dp-col-config">
          <PlateConfigPanel
            config={designConfig}
            onChange={setDesignConfig}
            targetPlateOptions={bootstrap.targetPlateDefinitions}
          />
        </div>

        {/* Centre: plate visualiser + solver status */}
        <div className="dp-col-viewer">
          <DesignPlateViewer
            rows={designConfig.plate_rows}
            cols={designConfig.plate_cols}
            emptyEdge={designConfig.empty_edge}
            compounds={designConfig.compounds}
            solvents={designConfig.solvents}
            solvedPreview={solvedPreview}
            wellsNeeded={totalWellsNeeded(designConfig.compounds, designConfig.solvents)}
            isGenerating={isGenerating}
            phase={designPhase}
          />

          {designJob && (
            <div className="dp-solver-status">
              {designJob.status === "queued" && (
                <span className="dp-pill dp-pill-queued">Queued…</span>
              )}
              {designJob.status === "running" && (
                <span className="dp-pill dp-pill-running">
                  <span className="dp-spinner" />
                  {runningLabel}
                </span>
              )}
              {designJob.status === "completed" && (
                <>
                  <span className="dp-pill dp-pill-done">
                    ✓&nbsp;{designJob.numPlates} plate{designJob.numPlates !== 1 ? "s" : ""}&nbsp;·&nbsp;{designJob.numWells} wells
                  </span>
                  <button className="dp-use-btn" onClick={handleUseLayout}>
                    Use this Layout →
                  </button>
                </>
              )}
              {designJob.status === "failed" && (
                <span className="dp-pill dp-pill-failed">
                  ✗&nbsp;{designJob.error?.message ?? "Solver failed"}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Right: compounds + solvents + generate */}
        <div className="dp-col-compounds">
          <CompoundPanel
            compounds={designConfig.compounds}
            solvents={designConfig.solvents}
            validationMessages={validationMessages}
            usableWells={usableWells}
            onCompoundsChange={(c) => setDesignConfig((dc) => ({ ...dc, compounds: c }))}
            onSolventsChange={(solvents) => setDesignConfig((dc) => ({ ...dc, solvents }))}
            onGenerate={handleGenerate}
            isGenerating={isGenerating}
            canGenerate={canGenerate}
          />
        </div>
      </div>
    </section>
  );
}
