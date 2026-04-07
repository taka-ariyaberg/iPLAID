import { ChangeEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ConfirmRunModal } from "../components/workbench/ConfirmRunModal";
import { FileUploader } from "../components/workbench/FileUploader";
import { MetaCreatorModal } from "../components/workbench/MetaCreatorModal";
import { PlateViewerPanel } from "../components/workbench/PlateViewerPanel";
import { RunConfigPanel, numericFields } from "../components/workbench/RunConfigPanel";
import { WorkbenchHero } from "../components/workbench/WorkbenchHero";
import { DesignPanel } from "../components/design/DesignPanel";
import { apiClient } from "../services/apiClient";
import type {
  BootstrapResponse,
  LayoutPreview,
  RunConfig,
  TargetPlateDefinition,
} from "../types";
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
        [csvQuote(plate.plateId), csvQuote(well.well), csvQuote(well.compound), csvQuote(well.concentration)].join(",")
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
  const [bootstrap, setBootstrap] = useState<BootstrapResponse | null>(null);
  const [config, setConfig] = useState<RunConfig | null>(null);
  const [loadingBootstrap, setLoadingBootstrap] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // ----- upload mode -----
  const [layoutFile, setLayoutFile] = useState<File | null>(null);
  const [metaFile, setMetaFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<LayoutPreview | null>(null);
  const [processing, setProcessing] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [workingPreview, setWorkingPreview] = useState<LayoutPreview | null>(null);
  const [showConfirmRun, setShowConfirmRun] = useState(false);
  const [revertKey, setRevertKey] = useState(0);
  const [showClearLayoutWarning, setShowClearLayoutWarning] = useState(false);
  const [layoutInputKey, setLayoutInputKey] = useState(0);
  const [viewerPlateTypeId, setViewerPlateTypeId] = useState<string>("MWP 384");
  const [customRows, setCustomRows] = useState<number>(16);
  const [customCols, setCustomCols] = useState<number>(24);

  // ----- file source tracking -----
  // Tracks how the current layout/meta files were set so we can warn on conflict.
  const [layoutSource, setLayoutSource] = useState<"upload" | "design" | null>(null);
  const [metaSource, setMetaSource] = useState<"upload" | "created" | null>(null);

  // ----- conflict warning state -----
  const [conflictWarning, setConflictWarning] = useState<{ message: string; onConfirm: () => void } | null>(null);
  // pending file input event held while waiting for user confirmation
  const pendingLayoutEventRef = useRef<ChangeEvent<HTMLInputElement> | null>(null);
  const pendingMetaEventRef   = useRef<ChangeEvent<HTMLInputElement> | null>(null);

  // ----- design mode -----
  const [designActive, setDesignActive] = useState(false);

  // ----- meta creator -----
  const [metaCreatorOpen, setMetaCreatorOpen] = useState(false);

  function handleMetaFile(file: File) {
    setMetaFile(file);
    setMetaSource("created");
    setConfig((c) => (c ? { ...c, meta_file: file.name } : c));
    setMetaCreatorOpen(false);
  }

  // Bootstrap
  useEffect(() => {
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
  }, []);

  // ---------------------------------------------------------------------------
  // Upload mode handlers
  // ---------------------------------------------------------------------------

  function clearLayoutFile() {
    setLayoutFile(null);
    setLayoutSource(null);
    setPreview(null);
    setWorkingPreview(null);
    setIsEditMode(false);
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
    setConfig((c) => (c ? { ...c, meta_file: "" } : c));
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
    if (!file) return;
    if (layoutSource === "design" && layoutFile) {
      pendingLayoutEventRef.current = event;
      setConflictWarning({
        message: "You have a PLAID-designed layout loaded. Uploading a CSV will replace it.",
        onConfirm: () => {
          const e = pendingLayoutEventRef.current;
          pendingLayoutEventRef.current = null;
          setConflictWarning(null);
          if (e?.target.files?.[0]) void applyLayoutFile(e.target.files[0]);
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
    if (!file) return;
    if (metaSource === "created" && metaFile) {
      pendingMetaEventRef.current = event;
      setConflictWarning({
        message: "You have a created meta file loaded. Uploading a CSV will replace it.",
        onConfirm: () => {
          const e = pendingMetaEventRef.current;
          pendingMetaEventRef.current = null;
          setConflictWarning(null);
          if (e?.target.files?.[0]) applyMetaFile(e.target.files[0]);
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
      const job = await apiClient.createRun({ layoutFile: activeLayoutFile, metaFile, config });
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
          <DesignPanel
            bootstrap={bootstrap}
            onComplete={handleDesignComplete}
            onCancel={() => setDesignActive(false)}
            onError={setErrorMessage}
          />
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

        {/* Run config — only when design panel is not active */}
        {!designActive && (
          <RunConfigPanel
            config={config}
            bootstrap={bootstrap}
            processing={processing}
            canProcess={Boolean(layoutFile && metaFile && preview)}
            onConfigChange={handleConfigChange}
            onProcess={() => { if (layoutFile && metaFile && config && preview) setShowConfirmRun(true); }}
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
          onClose={() => setMetaCreatorOpen(false)}
          onApply={handleMetaFile}
        />
      )}

      {conflictWarning && (
        <ConflictWarning
          message={conflictWarning.message}
          onConfirm={conflictWarning.onConfirm}
          onCancel={() => setConflictWarning(null)}
        />
      )}
    </div>
  );
}

