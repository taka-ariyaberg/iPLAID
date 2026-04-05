import { ChangeEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ConfirmRunModal } from "../components/workbench/ConfirmRunModal";
import { FileUploader } from "../components/workbench/FileUploader";
import { PlateViewerPanel } from "../components/workbench/PlateViewerPanel";
import { RunConfigPanel, numericFields } from "../components/workbench/RunConfigPanel";
import { WorkbenchHero } from "../components/workbench/WorkbenchHero";
import { apiClient } from "../services/apiClient";
import type { BootstrapResponse, LayoutPreview, RunConfig, TargetPlateDefinition } from "../types";
import "../styles/WorkbenchPage.css";

/** Quote a single CSV field: wrap in double-quotes if it contains a comma, quote, or newline. */
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

export function WorkbenchPage() {
  const navigate = useNavigate();
  const [bootstrap, setBootstrap] = useState<BootstrapResponse | null>(null);
  const [config, setConfig] = useState<RunConfig | null>(null);
  const [layoutFile, setLayoutFile] = useState<File | null>(null);
  const [metaFile, setMetaFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<LayoutPreview | null>(null);
  const [loadingBootstrap, setLoadingBootstrap] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Edit mode state
  const [isEditMode, setIsEditMode] = useState(false);
  const [workingPreview, setWorkingPreview] = useState<LayoutPreview | null>(null);
  const [showConfirmRun, setShowConfirmRun] = useState(false);
  const [revertKey, setRevertKey] = useState(0);
  const [showClearLayoutWarning, setShowClearLayoutWarning] = useState(false);
  const [layoutInputKey, setLayoutInputKey] = useState(0);

  // Viewer plate type — also drives config.target_plate_type
  const [viewerPlateTypeId, setViewerPlateTypeId] = useState<string>(config?.target_plate_type ?? "MWP 384");
  const [customRows, setCustomRows] = useState<number>(16);
  const [customCols, setCustomCols] = useState<number>(24);

  const viewerPlateDef: TargetPlateDefinition | undefined = bootstrap
    ? viewerPlateTypeId === "custom"
      ? { id: "custom", label: "Custom", rows: customRows, cols: customCols, wells: customRows * customCols }
      : bootstrap.targetPlateDefinitions.find((d) => d.id === viewerPlateTypeId)
    : undefined;

  const maxDataRows = preview ? Math.max(...preview.plates.map((p) => p.rowLabels.length)) : 0;
  const maxDataCols = preview ? Math.max(...preview.plates.map((p) => p.columnLabels.length)) : 0;
  const plateTooSmall =
    viewerPlateDef != null &&
    preview != null &&
    (viewerPlateDef.rows < maxDataRows || viewerPlateDef.cols < maxDataCols);

  useEffect(() => {
    async function loadBootstrap() {
      try {
        const payload = await apiClient.getBootstrap();
        setBootstrap(payload);
        setConfig(payload.configTemplate);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Failed to load app configuration.");
      } finally {
        setLoadingBootstrap(false);
      }
    }
    void loadBootstrap();
  }, []);

  function clearLayoutFile() {
    setLayoutFile(null);
    setPreview(null);
    setWorkingPreview(null);
    setIsEditMode(false);
    setLayoutInputKey((k) => k + 1);
    setConfig((c) => (c ? { ...c, layout_file: "" } : c));
  }

  function handleClearLayoutRequest() {
    if (isEditMode || workingPreview) {
      setShowClearLayoutWarning(true);
    } else {
      clearLayoutFile();
    }
  }

  function clearMetaFile() {
    setMetaFile(null);
    setConfig((c) => (c ? { ...c, meta_file: "" } : c));
  }

  async function handleLayoutChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setLayoutFile(file);
    setPreview(null);
    setWorkingPreview(null);
    setIsEditMode(false);
    if (!file) return;
    setErrorMessage(null);
    try {
      const nextPreview = await apiClient.previewLayout(file);
      setPreview(nextPreview);
      setConfig((c) => (c ? { ...c, layout_file: file.name } : c));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to preview the layout.");
    }
  }

  function handleMetaChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setMetaFile(file);
    setConfig((c) => (c && file ? { ...c, meta_file: file.name } : c));
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
      // Entering edit mode — initialise working copy if not already set
      if (!workingPreview) {
        setWorkingPreview(JSON.parse(JSON.stringify(preview)) as LayoutPreview);
      }
      setIsEditMode(true);
    } else {
      // Clicking Edit again while in mode = save & exit
      setIsEditMode(false);
    }
  }

  function handleEditChange(updated: LayoutPreview) {
    setWorkingPreview(updated);
  }

  function handleSaveEdits() {
    setIsEditMode(false);
  }

  function handleRevertAll() {
    setWorkingPreview(null);
    setRevertKey((k) => k + 1);
  }

  function handleProcess() {
    if (!layoutFile || !metaFile || !config || !preview) return;
    setShowConfirmRun(true);
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
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create pipeline run.");
      setProcessing(false);
    }
  }

  if (loadingBootstrap || !bootstrap || !config) {
    return <section className="page-state">Loading iPLAID…</section>;
  }

  const activePreview = workingPreview ?? preview;

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
        <FileUploader
          layoutFile={layoutFile}
          metaFile={metaFile}
          layoutInputKey={layoutInputKey}
          onLayoutChange={handleLayoutChange}
          onMetaChange={handleMetaChange}
          onClearLayout={handleClearLayoutRequest}
          onClearMeta={clearMetaFile}
        />

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
          onEditChange={handleEditChange}
          onSaveEdits={handleSaveEdits}
          onRevertAll={handleRevertAll}
        />

        <RunConfigPanel
          config={config}
          bootstrap={bootstrap}
          processing={processing}
          canProcess={Boolean(layoutFile && metaFile && preview)}
          onConfigChange={handleConfigChange}
          onProcess={handleProcess}
        />
      </div>

      {showConfirmRun && (
        <ConfirmRunModal
          hasEdits={Boolean(workingPreview)}
          isEditMode={isEditMode}
          onConfirm={handleConfirmRun}
          onClose={() => setShowConfirmRun(false)}
        />
      )}
    </div>
  );
}