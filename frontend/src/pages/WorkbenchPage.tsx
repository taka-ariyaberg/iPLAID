import { ChangeEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ConfirmRunModal } from "../components/workbench/ConfirmRunModal";
import { FileUploader } from "../components/workbench/FileUploader";
import { MetaCreatorModal } from "../components/workbench/MetaCreatorModal";
import type { CompoundRow as MetaCompoundRow } from "../components/workbench/MetaCreatorModal";
import { PlateViewerPanel } from "../components/workbench/PlateViewerPanel";
import { RunConfigPanel, numericFields } from "../components/workbench/RunConfigPanel";
import { WorkbenchHero } from "../components/workbench/WorkbenchHero";
import { DesignPanel } from "../components/design/DesignPanel";
import { defaultDesignConfig } from "../components/design/designUtils";
import { apiClient } from "../services/apiClient";
import type {
  LayoutPreview,
  RunConfig,
  TargetPlateDefinition,
} from "../types";
import { canonicalWellId } from "../utils/wellUtils";
import { useWorkbenchField } from "../workbenchState";
import "../styles/WorkbenchPage.css";

// ---------------------------------------------------------------------------
// Conflict warning
// ---------------------------------------------------------------------------

type ConflictWarningProps = {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
};

function ConflictWarning({ message, onConfirm, onCancel }: ConflictWarningProps) {
  return (
    <div className="conflict-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="conflict-panel" role="alertdialog">
        <div className="conflict-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </div>
        <p className="conflict-message">{message}</p>
        <div className="conflict-actions">
          <button className="conflict-btn conflict-btn-cancel" onClick={onCancel}>Keep existing</button>
          <button className="conflict-btn conflict-btn-confirm" onClick={onConfirm}>Replace anyway</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function csvQuote(value: string | number | null): string {
  const s = value === null ? "" : String(value);
  if (s.includes(",") || s.includes('"') || s.includes("\n") || s.includes("\r")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function previewToCSVFile(preview: LayoutPreview): File {
  const rows = ["plateID,well,cmpdname,CONCuM"];
  preview.plates.forEach((plate) => {
    plate.wells.forEach((well) => {
      rows.push(
        [
          csvQuote(plate.plateId),
          csvQuote(canonicalWellId(well.well)),
          csvQuote(well.compound),
          csvQuote(well.concentration),
        ].join(",")
      );
    });
  });
  return new File([rows.join("\n")], "edited_layout.csv", { type: "text/csv" });
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function WorkbenchPage() {
  const navigate = useNavigate();

  // ----- shared -----
  const [bootstrap, setBootstrap] = useWorkbenchField("bootstrap");
  const [config, setConfig] = useWorkbenchField("config");
  const [loadingBootstrap, setLoadingBootstrap] = useWorkbenchField("loadingBootstrap");
  const [errorMessage, setErrorMessage] = useWorkbenchField("errorMessage");
  // Optional pre-prepared source-plate layout (Liquid Name -> Source Well CSV).
  // Lives in component state — not persisted across navigation, intentionally.
  const [sourceLayoutFile, setSourceLayoutFile] = useState<File | null>(null);

  // ----- upload mode -----
  const [layoutFile, setLayoutFile] = useWorkbenchField("layoutFile");
  const [metaFile, setMetaFile] = useWorkbenchField("metaFile");
  const [preview, setPreview] = useWorkbenchField("preview");
  const [processing, setProcessing] = useWorkbenchField("processing");
  const [isEditMode, setIsEditMode] = useWorkbenchField("isEditMode");
  const [workingPreview, setWorkingPreview] = useWorkbenchField("workingPreview");
  const [showConfirmRun, setShowConfirmRun] = useWorkbenchField("showConfirmRun");
  const [revertKey, setRevertKey] = useWorkbenchField("revertKey");
  const [showClearLayoutWarning, setShowClearLayoutWarning] = useWorkbenchField("showClearLayoutWarning");
  const [layoutInputKey, setLayoutInputKey] = useWorkbenchField("layoutInputKey");
  const [metaInputKey, setMetaInputKey] = useWorkbenchField("metaInputKey");
  const [viewerPlateTypeId, setViewerPlateTypeId] = useWorkbenchField("viewerPlateTypeId");
  const [customRows, setCustomRows] = useWorkbenchField("customRows");
  const [customCols, setCustomCols] = useWorkbenchField("customCols");

  // ----- file source tracking -----
  // Tracks how the current layout/meta files were set so we can warn on conflict.
  const [layoutSource, setLayoutSource] = useWorkbenchField("layoutSource");
  const [metaSource, setMetaSource] = useWorkbenchField("metaSource");

  // ----- conflict warning state -----
  const [conflictWarning, setConflictWarning] = useState<{ message: string; onConfirm: () => void } | null>(null);
  // pending files held while waiting for user confirmation
  const pendingLayoutFileRef = useRef<File | null>(null);
  const pendingMetaFileRef   = useRef<File | null>(null);

  // ----- design mode -----
  const [designActive, setDesignActive] = useWorkbenchField("designActive");
  const [designConfig, setDesignConfig] = useWorkbenchField("designConfig");
  const [designJob, setDesignJob] = useWorkbenchField("designJob");
  const [designIsGenerating, setDesignIsGenerating] = useWorkbenchField("designIsGenerating");

  // ----- meta creator -----
  const [metaCreatorOpen, setMetaCreatorOpen] = useWorkbenchField("metaCreatorOpen");
  const [metaCreatorRows, setMetaCreatorRows] = useWorkbenchField("metaCreatorRows");

  function handleMetaFile(file: File, rows: MetaCompoundRow[]) {
    setMetaFile(file);
    setMetaSource("created");
    setMetaCreatorRows(rows.map((row) => ({ ...row })));
    setConfig((c) => (c ? { ...c, meta_file: file.name } : c));
    setMetaCreatorOpen(false);
  }

  // Bootstrap
  useEffect(() => {
    if (bootstrap || !loadingBootstrap) return;

    async function load() {
      try {
        const payload = await apiClient.getBootstrap();
        setBootstrap(payload);
        setConfig(payload.configTemplate);
      } catch (err) {
        setErrorMessage(err instanceof Error ? err.message : "Failed to load app configuration.");
      } finally {
        setLoadingBootstrap(false);
      }
    }

    void load();
  }, [bootstrap, loadingBootstrap]);

  useEffect(() => {
    if (!bootstrap || designConfig) return;
    const p384 = bootstrap.targetPlateDefinitions.find((plate) => plate.wells === 384);
    setDesignConfig(defaultDesignConfig(p384?.rows ?? 16, p384?.cols ?? 24));
  }, [bootstrap, designConfig]);

  // ---------------------------------------------------------------------------
  // Upload mode handlers
  // ---------------------------------------------------------------------------

  function clearLayoutFile() {
    setLayoutFile(null);
    setLayoutSource(null);
    setPreview(null);
    setWorkingPreview(null);
    setIsEditMode(false);
    pendingLayoutFileRef.current = null;
    setLayoutInputKey((k) => k + 1);
    setConfig((c) => (c ? { ...c, layout_file: "" } : c));
  }

  function handleClearLayoutRequest() {
    if (isEditMode || workingPreview) setShowClearLayoutWarning(true);
    else clearLayoutFile();
  }

  function clearMetaFile() {
    setMetaFile(null);
    setMetaSource(null);
    setMetaCreatorRows([]);
    pendingMetaFileRef.current = null;
    setMetaInputKey((k) => k + 1);
    setConfig((c) => (c ? { ...c, meta_file: "" } : c));
  }

  function dismissConflictWarning() {
    pendingLayoutFileRef.current = null;
    pendingMetaFileRef.current = null;
    setConflictWarning(null);
  }

  async function applyLayoutFile(file: File) {
    setLayoutFile(file);
    setLayoutSource("upload");
    setPreview(null);
    setWorkingPreview(null);
    setIsEditMode(false);
    setErrorMessage(null);
    try {
      const nextPreview = await apiClient.previewLayout(file);
      setPreview(nextPreview);
      setConfig((c) => (c ? { ...c, layout_file: file.name } : c));
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to preview the layout.");
    }
  }

  async function handleLayoutChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!file) return;
    if (layoutSource === "design" && layoutFile) {
      pendingLayoutFileRef.current = file;
      setConflictWarning({
        message: "You have a PLAID-designed layout loaded. Uploading a CSV will replace it.",
        onConfirm: () => {
          const nextFile = pendingLayoutFileRef.current;
          pendingLayoutFileRef.current = null;
          setConflictWarning(null);
          if (nextFile) void applyLayoutFile(nextFile);
        },
      });
      return;
    }
    void applyLayoutFile(file);
  }

  function applyMetaFile(file: File) {
    setMetaFile(file);
    setMetaSource("upload");
    setConfig((c) => (c ? { ...c, meta_file: file.name } : c));
  }

  function handleMetaChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!file) return;
    if (metaSource === "created" && metaFile) {
      pendingMetaFileRef.current = file;
      setConflictWarning({
        message: "You have a created meta file loaded. Uploading a CSV will replace it.",
        onConfirm: () => {
          const nextFile = pendingMetaFileRef.current;
          pendingMetaFileRef.current = null;
          setConflictWarning(null);
          if (nextFile) applyMetaFile(nextFile);
        },
      });
      return;
    }
    applyMetaFile(file);
  }

  function handleDesignToggle() {
    if (!designActive && layoutSource === "upload" && layoutFile) {
      setConflictWarning({
        message: "You have an uploaded layout CSV loaded. Opening the designer will replace it when you generate a new layout.",
        onConfirm: () => { setConflictWarning(null); setDesignActive(true); },
      });
      return;
    }
    setDesignActive((v) => !v);
  }

  function handleMetaCreatorOpen() {
    if (metaSource === "upload" && metaFile) {
      setConflictWarning({
        message: "You have an uploaded meta CSV loaded. Using the meta creator will replace it.",
        onConfirm: () => { setConflictWarning(null); setMetaCreatorOpen(true); },
      });
      return;
    }
    setMetaCreatorOpen(true);
  }

  function handleViewerPlateTypeChange(id: string) {
    setViewerPlateTypeId(id);
    if (id !== "custom") {
      setConfig((c) => (c ? { ...c, target_plate_type: id } : c));
    }
  }

  function handleConfigChange(field: keyof RunConfig, value: string) {
    setConfig((c) => {
      if (!c) return c;
      // Switching dispenser resets sourceplate_type to the new dispenser's
      // default (otherwise an iDOT plate label leaks into an Echo run) and
      // clears any uploaded source-layout file (different source plates use
      // different wells / liquid sets). Target plate is geometry-only
      // (96/384/etc.) and stays whatever the user picked.
      if (field === "dispenser" && bootstrap) {
        const meta = bootstrap.dispensers?.find((d) => d.name === value);
        return {
          ...c,
          dispenser: value as RunConfig["dispenser"],
          sourceplate_type: meta?.default_sourceplate_type ?? c.sourceplate_type,
          source_layout_file: null,
        };
      }
      return { ...c, [field]: numericFields.includes(field) ? Number(value) : value };
    });
  }

  function handleEditModeToggle() {
    if (!preview) return;
    if (!isEditMode) {
      if (!workingPreview) setWorkingPreview(JSON.parse(JSON.stringify(preview)) as LayoutPreview);
      setIsEditMode(true);
    } else {
      setIsEditMode(false);
    }
  }

  async function handleConfirmRun() {
    if (!metaFile || !config) return;
    setShowConfirmRun(false);
    setProcessing(true);
    setErrorMessage(null);
    const activeLayoutFile = workingPreview ? previewToCSVFile(workingPreview) : layoutFile!;
    try {
      const job = await apiClient.createRun({
        layoutFile: activeLayoutFile,
        metaFile,
        config,
        sourceLayoutFile,
      });
      setProcessing(false);
      navigate(`/runs/${job.jobId}`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to create pipeline run.");
      setProcessing(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Design mode handlers
  // ---------------------------------------------------------------------------

  function handleDesignComplete(lf: File, nextPreview: LayoutPreview) {
    setLayoutFile(lf);
    setLayoutSource("design");
    setPreview(nextPreview);
    setWorkingPreview(null);
    setIsEditMode(false);
    setConfig((c) => (c ? { ...c, layout_file: lf.name } : c));
    setDesignActive(false);
  }

  // ---------------------------------------------------------------------------
  // Derived view state
  // ---------------------------------------------------------------------------

  if (loadingBootstrap || !bootstrap || !config) {
    return <section className="page-state">Loading iPLAID…</section>;
  }

  const activePreview = workingPreview ?? preview;
  const downloadProjectDetails: string[] = [config.user_name, config.protocol_name];

  const viewerPlateDef: TargetPlateDefinition | undefined =
    viewerPlateTypeId === "custom"
      ? { id: "custom", label: "Custom", rows: customRows, cols: customCols, wells: customRows * customCols }
      : bootstrap.targetPlateDefinitions.find((d) => d.id === viewerPlateTypeId);

  const maxDataRows = preview ? Math.max(...preview.plates.map((p) => p.rowLabels.length)) : 0;
  const maxDataCols = preview ? Math.max(...preview.plates.map((p) => p.columnLabels.length)) : 0;
  const plateTooSmall =
    viewerPlateDef != null &&
    preview != null &&
    (viewerPlateDef.rows < maxDataRows || viewerPlateDef.cols < maxDataCols);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="workbench-layout">
      <WorkbenchHero isReady={Boolean(layoutFile && metaFile)} />

      {errorMessage && <section className="status-banner is-error">{errorMessage}</section>}

      {showClearLayoutWarning && (
        <div className="confirm-overlay">
          <div className="confirm-dialog">
            <p className="confirm-dialog-msg">
              ⚠ You have unsaved edits. Removing the layout file will discard all changes permanently.
            </p>
            <div className="confirm-dialog-btns">
              <button type="button" className="confirm-btn is-cancel" onClick={() => setShowClearLayoutWarning(false)}>
                Keep editing
              </button>
              <button type="button" className="confirm-btn is-danger" onClick={() => { setShowClearLayoutWarning(false); clearLayoutFile(); }}>
                Discard &amp; remove
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="workbench-columns">
        {/* Input panel — always visible */}
        <FileUploader
          layoutFile={layoutFile}
          metaFile={metaFile}
          layoutInputKey={layoutInputKey}
          metaInputKey={metaInputKey}
          layoutSource={layoutSource}
          metaSource={metaSource}
          onLayoutChange={handleLayoutChange}
          onMetaChange={handleMetaChange}
          onClearLayout={handleClearLayoutRequest}
          onClearMeta={clearMetaFile}
          designActive={designActive}
          onDesignToggle={handleDesignToggle}
          metaCreatorActive={metaCreatorOpen}
          onMetaCreatorOpen={handleMetaCreatorOpen}
        />

        {/* Centre area: design panel OR plate viewer */}
        {designActive ? (
          designConfig ? (
            <DesignPanel
              bootstrap={bootstrap}
              designConfig={designConfig}
              onDesignConfigChange={(nextValue) => {
                setDesignConfig((currentValue) => {
                  const activeConfig = currentValue ?? designConfig;
                  return typeof nextValue === "function"
                    ? nextValue(activeConfig)
                    : nextValue;
                });
              }}
              designJob={designJob}
              onDesignJobChange={setDesignJob}
              isGenerating={designIsGenerating}
              onIsGeneratingChange={setDesignIsGenerating}
              projectDetails={downloadProjectDetails}
              onComplete={handleDesignComplete}
              onCancel={() => setDesignActive(false)}
              onError={setErrorMessage}
            />
          ) : (
            <section className="page-state">Preparing designer…</section>
          )
        ) : (
          <PlateViewerPanel
            preview={activePreview}
            originalPreview={preview}
            bootstrap={bootstrap}
            viewerPlateTypeId={viewerPlateTypeId}
            onViewerPlateTypeChange={handleViewerPlateTypeChange}
            customRows={customRows}
            onCustomRowsChange={setCustomRows}
            customCols={customCols}
            onCustomColsChange={setCustomCols}
            plateDef={viewerPlateDef}
            exportProjectDetails={downloadProjectDetails}
            plateTooSmall={plateTooSmall}
            maxDataRows={maxDataRows}
            maxDataCols={maxDataCols}
            isEditMode={isEditMode}
            revertKey={revertKey}
            onEditModeToggle={handleEditModeToggle}
            onEditChange={setWorkingPreview}
            onSaveEdits={() => setIsEditMode(false)}
            onRevertAll={() => { setWorkingPreview(null); setRevertKey((k) => k + 1); }}
          />
        )}

        {/* Run config — only when design panel is not active and config/bootstrap are loaded */}
        {!designActive && config && bootstrap && (
          <RunConfigPanel
            config={config}
            bootstrap={bootstrap}
            processing={processing}
            canProcess={Boolean(layoutFile && metaFile && preview)}
            onConfigChange={handleConfigChange}
            onProcess={() => { if (layoutFile && metaFile && config && preview) setShowConfirmRun(true); }}
            sourceLayoutFile={sourceLayoutFile}
            onSourceLayoutFileChange={(f) => {
              setSourceLayoutFile(f);
              setConfig((c) => (c ? { ...c, source_layout_file: f?.name ?? null } : c));
            }}
          />
        )}
      </div>

      {showConfirmRun && (
        <ConfirmRunModal
          hasEdits={Boolean(workingPreview)}
          isEditMode={isEditMode}
          onConfirm={handleConfirmRun}
          onClose={() => setShowConfirmRun(false)}
        />
      )}

      {metaCreatorOpen && (
        <MetaCreatorModal
          initialRows={metaCreatorRows}
          projectDetails={downloadProjectDetails}
          onClose={() => setMetaCreatorOpen(false)}
          onApply={handleMetaFile}
        />
      )}

      {conflictWarning && (
        <ConflictWarning
          message={conflictWarning.message}
          onConfirm={conflictWarning.onConfirm}
          onCancel={dismissConflictWarning}
        />
      )}
    </div>
  );
}
