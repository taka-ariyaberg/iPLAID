/**
 * DesignPanel — PLAID_Core layout designer.
 *
 * Rendered in place of PlateViewerPanel when the user activates design mode.
 * On success calls onComplete(layoutFile, preview) so WorkbenchPage can
 * treat the generated layout like a manually-uploaded CSV.
 */

import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";
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
import { DMSO_COLOR, getConcColor, getStableCompoundColor } from "../../utils/colorUtils";
import {
  buildExportFilename,
  downloadPlateCsv,
  downloadPlatePng,
  downloadPlateSvg,
  type PlateExportSpec,
} from "../../utils/plateExport";
import "../../styles/DesignMode.css";
import "../../styles/DesignPanel.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

function normalizeWellName(well: string): string {
  return well.replace(/^([A-Za-z]+)0*(\d+)$/, "$1$2");
}

function buildDesignExportSpec(preview: LayoutPreview, config: DesignConfig): PlateExportSpec {
  const compoundOrder = new Map<string, number>();
  config.compounds.forEach((compound, index) => {
    compoundOrder.set(compound.name.trim().toLowerCase(), index);
  });

  const plates = preview.plates.map((plate) => {
    const wellMap = new Map(
      plate.wells.map((well) => [normalizeWellName(well.well), well]),
    );
    const allWells: PlateExportSpec["plates"][number]["allWells"] = [];

    plate.rowLabels.forEach((rowLabel) => {
      plate.columnLabels.forEach((column) => {
        const wellName = `${rowLabel}${column}`;
        const well = wellMap.get(wellName);
        allWells.push({
          well: wellName,
          compound: well?.compound ?? null,
          concentration: well?.concentration ?? null,
          isFilled: Boolean(well),
        });
      });
    });

    return {
      plateId: plate.plateId,
      rowLabels: plate.rowLabels,
      columnLabels: plate.columnLabels,
      allWells,
    };
  });

  const totalEmptyCount = plates.reduce(
    (sum, plate) => sum + plate.allWells.filter((well) => !well.isFilled).length,
    0,
  );

  const groups = new Map<string, {
    count: number;
    isControl: boolean;
    concentrations: Map<string, { numeric: number | null; count: number }>;
  }>();

  preview.plates.forEach((plate) => {
    plate.wells.forEach((well) => {
      const concentrationKey = well.concentration === null ? "No concentration" : String(well.concentration);
      const group = groups.get(well.compound) ?? {
        count: 0,
        isControl: Boolean(well.isControl),
        concentrations: new Map<string, { numeric: number | null; count: number }>(),
      };
      group.count += 1;
      group.isControl = group.isControl || Boolean(well.isControl);

      const concentration = group.concentrations.get(concentrationKey) ?? {
        numeric: well.concentration,
        count: 0,
      };
      concentration.count += 1;
      group.concentrations.set(concentrationKey, concentration);
      groups.set(well.compound, group);
    });
  });

  const legendGroups = Array.from(groups.entries())
    .sort(([leftName], [rightName]) => {
      const leftIndex = compoundOrder.get(leftName.trim().toLowerCase());
      const rightIndex = compoundOrder.get(rightName.trim().toLowerCase());
      if (leftIndex != null && rightIndex != null && leftIndex !== rightIndex) {
        return leftIndex - rightIndex;
      }
      if (leftIndex != null) return -1;
      if (rightIndex != null) return 1;
      return leftName.localeCompare(rightName);
    })
    .map(([compound, group]) => ({
      compound,
      count: group.count,
      isControl: group.isControl,
      concentrations: Array.from(group.concentrations.entries())
        .sort((left, right) => {
          const leftValue = left[1].numeric ?? -1;
          const rightValue = right[1].numeric ?? -1;
          return leftValue - rightValue;
        })
        .map(([label, concentration]) => ({
          label,
          numeric: concentration.numeric,
          count: concentration.count,
        })),
    }));

  const compoundColorLookup = new Map<string, string>();
  let fallbackColorIndex = config.compounds.length;
  legendGroups.forEach((group) => {
    if (group.isControl) {
      compoundColorLookup.set(group.compound, DMSO_COLOR);
      return;
    }

    const configuredIndex = compoundOrder.get(group.compound.trim().toLowerCase());
    const colorIndex = configuredIndex ?? fallbackColorIndex++;
    compoundColorLookup.set(group.compound, getStableCompoundColor(colorIndex));
  });

  const wellColorLookup = new Map<string, Map<string, string>>();
  legendGroups.forEach((group) => {
    const baseColor = compoundColorLookup.get(group.compound) ?? DMSO_COLOR;
    const concentrationColors = new Map<string, string>();
    group.concentrations.forEach((concentration, index) => {
      concentrationColors.set(
        concentration.label,
        group.isControl
          ? DMSO_COLOR
          : getConcColor(baseColor, index, group.concentrations.length),
      );
    });
    wellColorLookup.set(group.compound, concentrationColors);
  });

  return {
    title: "PLAID_Core design layout",
    plates,
    wellColorLookup,
    compoundColorLookup,
    legendGroups: legendGroups.map(({ isControl: _isControl, ...group }) => group),
    totalEmptyCount,
    concentrationUnit: "µM",
    totalWellCount: preview.wellCount,
    plateCount: preview.plateCount,
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface DesignPanelProps {
  bootstrap: BootstrapResponse;
  designConfig: DesignConfig;
  onDesignConfigChange: Dispatch<SetStateAction<DesignConfig>>;
  designJob: DesignJob | null;
  onDesignJobChange: Dispatch<SetStateAction<DesignJob | null>>;
  isGenerating: boolean;
  onIsGeneratingChange: Dispatch<SetStateAction<boolean>>;
  onComplete: (layoutFile: File, preview: LayoutPreview) => void;
  onCancel: () => void;
  onError: (msg: string) => void;
}

export function DesignPanel({
  bootstrap,
  designConfig,
  onDesignConfigChange,
  designJob,
  onDesignJobChange,
  isGenerating,
  onIsGeneratingChange,
  onComplete,
  onCancel,
  onError,
}: DesignPanelProps) {
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
        onIsGeneratingChange(false);
        onDesignJobChange((current) =>
          current?.jobId === activeJob.jobId ? null : current,
        );
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
    onIsGeneratingChange(true);
    onDesignJobChange(null);
    try {
      const job = await apiClient.solveDesign(designConfig);
      if (!isMountedRef.current || cancelAfterStartRef.current) {
        void apiClient.cancelDesignJob(job.jobId).catch(() => undefined);
        return;
      }
      onDesignJobChange(job);
      pollRef.current = setInterval(async () => {
        try {
          const updated = await apiClient.getDesignJob(job.jobId);
          if (!isMountedRef.current) return;
          onDesignJobChange(updated);
          if (updated.status === "completed" || updated.status === "failed") {
            clearInterval(pollRef.current!);
            pollRef.current = null;
            onIsGeneratingChange(false);
            if (updated.status === "failed") {
              onError(updated.error?.message ?? "Solver failed.");
            }
          }
        } catch {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          if (isMountedRef.current) {
            onIsGeneratingChange(false);
          }
        }
      }, 2000);
    } catch (err) {
      if (isMountedRef.current) {
        onError(err instanceof Error ? err.message : "Failed to start solver.");
        onIsGeneratingChange(false);
      }
    }
  }

  function handleCancel() {
    cancelAfterStartRef.current = true;
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    onIsGeneratingChange(false);
    const activeJob = designJobRef.current;
    if (activeJob && (activeJob.status === "queued" || activeJob.status === "running")) {
      void apiClient.cancelDesignJob(activeJob.jobId).catch(() => undefined);
      onDesignJobChange(null);
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
  const exportSpec = solvedPreview ? buildDesignExportSpec(solvedPreview, designConfig) : null;

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
            onChange={onDesignConfigChange}
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

          {solvedPreview && exportSpec && (
            <div className="plate-export-actions dp-export-actions" data-export-ignore="true">
              <p className="section-kicker">Export</p>
              <div className="plate-export-btns">
                <button
                  type="button"
                  className="plate-export-btn"
                  onClick={() => downloadPlateCsv(solvedPreview, buildExportFilename("PLAID_Core design layout", "csv"))}
                  title="Download layout as CSV"
                >
                  <span className="plate-export-icon">⬇</span> CSV
                </button>
                <button
                  type="button"
                  className="plate-export-btn"
                  onClick={() => downloadPlateSvg(exportSpec, buildExportFilename("PLAID_Core design layout", "svg"))}
                  title="Download plate figure as SVG"
                >
                  <span className="plate-export-icon">⬇</span> SVG
                </button>
                <button
                  type="button"
                  className="plate-export-btn"
                  onClick={() => downloadPlatePng(exportSpec, buildExportFilename("PLAID_Core design layout", "png"))}
                  title="Download plate figure as PNG"
                >
                  <span className="plate-export-icon">⬇</span> PNG
                </button>
              </div>
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
            onCompoundsChange={(c) => onDesignConfigChange((dc) => ({ ...dc, compounds: c }))}
            onSolventsChange={(solvents) => onDesignConfigChange((dc) => ({ ...dc, solvents }))}
            onGenerate={handleGenerate}
            isGenerating={isGenerating}
            canGenerate={canGenerate}
          />
        </div>
      </div>
    </section>
  );
}
