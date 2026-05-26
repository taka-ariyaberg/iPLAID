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
  SolventFamily,
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
  confirmLabel?: string;
  cancelLabel?: string;
};

function ConflictWarning({ message, onConfirm, onCancel, confirmLabel, cancelLabel }: ConflictWarningProps) {
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
          <button className="conflict-btn conflict-btn-cancel" onClick={onCancel}>{cancelLabel ?? "Keep existing"}</button>
          <button className="conflict-btn conflict-btn-confirm" onClick={onConfirm}>{confirmLabel ?? "Replace anyway"}</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Invalid-file warning (single-button, informational)
// ---------------------------------------------------------------------------

type InvalidFileWarningProps = {
  title: string;
  detail: string;
  onDismiss: () => void;
};

function InvalidFileWarning({ title, detail, onDismiss }: InvalidFileWarningProps) {
  return (
    <div className="conflict-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onDismiss(); }}>
      <div className="conflict-panel invalid-file-panel" role="alertdialog">
        <div className="conflict-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </div>
        <h3 className="invalid-file-title">{title}</h3>
        <p className="invalid-file-detail">{detail}</p>
        <div className="conflict-actions invalid-file-actions">
          <button type="button" className="conflict-btn conflict-btn-cancel" onClick={onDismiss}>OK</button>
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
  // Validation-error modal for the optional Source plate layout CSV upload.
  // Held separately from the page-level errorMessage banner so the user gets
  // a hard-to-miss popup when the format is wrong (banner can be missed).
  const [sourceLayoutWarning, setSourceLayoutWarning] = useState<string | null>(null);
  // Per-solvent carrier caps. `solventFamilies` and `selectedSolventKey` are
  // local view-state only — never written into config. Only the derived
  // solvent_caps_pct map (built in rebuildSolventCaps / handleSolventCapChange)
  // travels in config.
  const [solventFamilies, setSolventFamilies] = useState<SolventFamily[]>([]);
  const [selectedSolventKey, setSelectedSolventKey] = useState<string>("");
  const [capNotice, setCapNotice] = useState<string | null>(null);
  const [showClearMetaWarning, setShowClearMetaWarning] = useState(false);

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
  const pendingNewMetaRef = useRef<{ file: File; source: "upload" | "created"; rows?: MetaCompoundRow[] } | null>(null);
  const pendingNewSourceLayoutRef = useRef<File | null>(null);

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

  // Rebuilds the per-solvent cap map from the solvent families in the staged
  // meta/source file. On swap OR delete the whole map is dropped and rebuilt
  // from the new families at their default caps (with a non-error notice). The
  // selected solvent is local view-state only and never written into config.
  async function rebuildSolventCaps(file: File | null, opts?: { silent?: boolean }) {
    // Only notify when caps the user could have customized are actually being
    // discarded. Read the PERSISTED config (survives navigation away/back),
    // not the ephemeral solventFamilies state which resets on remount —
    // otherwise deleting a meta after a round-trip to the run page is silent.
    // `silent` suppresses the post-hoc notice when the caller already showed a
    // pre-action confirmation (the meta-delete Proceed/Cancel dialog).
    const hadPriorCaps =
      !!config?.solvent_caps_pct && Object.keys(config.solvent_caps_pct).length > 0;
    if (!file) {
      setSolventFamilies([]);
      setSelectedSolventKey("");
      setConfig((c) => (c ? { ...c, solvent_caps_pct: null } : c));
      if (hadPriorCaps && !opts?.silent) setCapNotice("Solvent caps were cleared because the solvent file was removed.");
      return;
    }
    try {
      const families = await apiClient.fetchSolventFamilies(file);
      setSolventFamilies(families);
      setSelectedSolventKey(families[0]?.solventKey ?? "");
      const caps: Record<string, number> = {};
      families.forEach((f) => { caps[f.solventKey] = f.defaultCapPct; });
      setConfig((c) => (c ? { ...c, solvent_caps_pct: caps } : c));
      if (hadPriorCaps) setCapNotice("Solvent caps were reset to defaults because the solvent file changed.");
    } catch {
      setSolventFamilies([]);
      setSelectedSolventKey("");
      setConfig((c) => (c ? { ...c, solvent_caps_pct: null } : c));
      setCapNotice("Could not read solvent families from this file; falling back to the single Max-solvent-% cap.");
    }
  }

  function handleSolventCapChange(solventKey: string, pct: number) {
    setConfig((c) => {
      if (!c) return c;
      const next = { ...(c.solvent_caps_pct ?? {}) };
      next[solventKey] = pct;
      return { ...c, solvent_caps_pct: next };
    });
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

  // Self-correcting: if config.target_plate_type isn't in the active dispenser's
  // catalog (e.g. left over from a saved state, or from a browser serving a stale
  // bundle on a previous run), snap to that dispenser's default. Same for
  // sourceplate_type. Prevents an iDOT plate label from leaking into an Echo run
  // (which would put "MWP 384" in the Echo CSV and the machine would reject it).
  useEffect(() => {
    if (!bootstrap || !config) return;
    const targetList =
      bootstrap.target_plate_definitions_by_dispenser?.[config.dispenser] ?? bootstrap.targetPlateDefinitions;
    const sourceList = bootstrap.plate_types_by_dispenser?.[config.dispenser];
    const meta = bootstrap.dispensers?.find((d) => d.name === config.dispenser);
    const targetValid = targetList.some((d) => d.id === config.target_plate_type);
    const sourceValid = sourceList ? sourceList.includes(config.sourceplate_type) : true;
    if (!targetValid && meta?.default_target_plate_type) {
      setConfig((c) => (c ? { ...c, target_plate_type: meta.default_target_plate_type } : c));
      setViewerPlateTypeId(meta.default_target_plate_type);
    }
    if (!sourceValid && meta?.default_sourceplate_type) {
      setConfig((c) => (c ? { ...c, sourceplate_type: meta.default_sourceplate_type } : c));
    }
  }, [bootstrap, config, setConfig, setViewerPlateTypeId]);

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
    // silent: the destructive cap clear is announced up-front by
    // handleClearMetaRequest's confirmation dialog, not a post-hoc notice.
    void rebuildSolventCaps(null, { silent: true });
  }

  function handleClearMetaRequest() {
    const hasCaps =
      !!config?.solvent_caps_pct && Object.keys(config.solvent_caps_pct).length > 0;
    if (hasCaps) setShowClearMetaWarning(true);
    else clearMetaFile();
  }

  function dismissConflictWarning() {
    pendingLayoutFileRef.current = null;
    pendingMetaFileRef.current = null;
    pendingNewMetaRef.current = null;
    pendingNewSourceLayoutRef.current = null;
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
    void rebuildSolventCaps(file);
  }

  function applyMetaFromUpload(file: File) {
    if (sourceLayoutFile) {
      pendingNewMetaRef.current = { file, source: "upload" };
      setConflictWarning({
        message:
          "A source plate layout is staged, which already provides metadata. Replace it with this metadata file?",
        onConfirm: () => {
          const pending = pendingNewMetaRef.current;
          pendingNewMetaRef.current = null;
          setConflictWarning(null);
          if (!pending) return;
          setSourceLayoutFile(null);
          setConfig((c) => (c ? { ...c, source_layout_file: null } : c));
          applyMetaFile(pending.file);
        },
      });
      return;
    }
    applyMetaFile(file);
  }

  function applyMetaFromCreator(file: File, rows: MetaCompoundRow[]) {
    if (sourceLayoutFile) {
      pendingNewMetaRef.current = { file, source: "created", rows };
      setConflictWarning({
        message:
          "A source plate layout is staged, which already provides metadata. Replace it with the metadata you just created?",
        onConfirm: () => {
          const pending = pendingNewMetaRef.current;
          pendingNewMetaRef.current = null;
          setConflictWarning(null);
          if (!pending || pending.source !== "created" || !pending.rows) return;
          setSourceLayoutFile(null);
          setConfig((c) => (c ? { ...c, source_layout_file: null } : c));
          handleMetaFile(pending.file, pending.rows);
          void rebuildSolventCaps(pending.file);
        },
      });
      return;
    }
    handleMetaFile(file, rows);
    void rebuildSolventCaps(file);
  }

  async function applySourceLayoutUpload(file: File | null) {
    if (file && metaFile) {
      pendingNewSourceLayoutRef.current = file;
      setConflictWarning({
        message:
          "A metadata file is staged. A source plate layout supersedes metadata. Replace metadata with this source plate layout?",
        onConfirm: () => {
          const pending = pendingNewSourceLayoutRef.current;
          pendingNewSourceLayoutRef.current = null;
          setConflictWarning(null);
          if (!pending) return;
          clearMetaFile();
          void handleSourceLayoutChange(pending);
        },
      });
      return;
    }
    await handleSourceLayoutChange(file);
  }

  async function handleSourceLayoutChange(file: File | null) {
    if (file === null) {
      setSourceLayoutFile(null);
      setConfig((c) => (c ? { ...c, source_layout_file: null } : c));
      void rebuildSolventCaps(null);
      return;
    }
    try {
      await apiClient.previewSourceLayout(file);
      setSourceLayoutFile(file);
      setConfig((c) => (c ? { ...c, source_layout_file: file.name } : c));
      void rebuildSolventCaps(file);
    } catch (err) {
      // Validation failed — pop a modal warning instead of silently rejecting.
      // Leave previous state cleared so the upload zone does NOT go green.
      setSourceLayoutFile(null);
      setConfig((c) => (c ? { ...c, source_layout_file: null } : c));
      void rebuildSolventCaps(null);
      setSourceLayoutWarning(
        err instanceof Error ? err.message : "Failed to validate source plate layout."
      );
    }
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
          if (nextFile) applyMetaFromUpload(nextFile);
        },
      });
      return;
    }
    applyMetaFromUpload(file);
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
    if (field === "dispenser" || field === "sourceplate_type") {
      if (sourceLayoutFile) void rebuildSolventCaps(null);
      setSourceLayoutFile(null);
    }
    if (field === "dispenser" && bootstrap) {
      const meta = bootstrap.dispensers?.find((d) => d.name === value);
      if (meta?.default_target_plate_type) setViewerPlateTypeId(meta.default_target_plate_type);
    }
    setConfig((c) => {
      if (!c) return c;
      // Switching dispenser resets sourceplate_type AND target_plate_type to
      // the new dispenser's defaults. iDOT target plate names are geometric
      // ("MWP 384"); Echo target plate names are vendor SKUs (e.g.
      // "Revvity_384PS_6007660"). Letting an iDOT label leak into an Echo
      // run would put an unrecognised string in the Echo CSV's Destination
      // Plate Type column, which the Echo machine would reject.
      if (field === "dispenser" && bootstrap) {
        const meta = bootstrap.dispensers?.find((d) => d.name === value);
        return {
          ...c,
          dispenser: value as RunConfig["dispenser"],
          sourceplate_type: meta?.default_sourceplate_type ?? c.sourceplate_type,
          target_plate_type: meta?.default_target_plate_type ?? c.target_plate_type,
          source_layout_file: null,
        };
      }
      if (field === "sourceplate_type") {
        return {
          ...c,
          sourceplate_type: value,
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
    if (!config) return;
    if (!metaFile && !sourceLayoutFile) return;
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

  const targetDefsForDispenser =
    bootstrap.target_plate_definitions_by_dispenser?.[config.dispenser] ?? bootstrap.targetPlateDefinitions;
  const viewerPlateDef: TargetPlateDefinition | undefined =
    viewerPlateTypeId === "custom"
      ? { id: "custom", label: "Custom", rows: customRows, cols: customCols, wells: customRows * customCols }
      : targetDefsForDispenser.find((d) => d.id === viewerPlateTypeId);

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
      <WorkbenchHero
        layoutFile={layoutFile}
        metaFile={metaFile}
        sourceLayoutFile={sourceLayoutFile}
        config={config}
        layoutWellCount={null}
        metaCompoundCount={null}
        running={
          processing
            ? { kind: "pipeline" }
            : designIsGenerating
              ? {
                  kind: "design",
                  label:
                    designJob?.phase === "preflight"
                      ? "Checking inputs…"
                      : designJob?.phase === "solving"
                        ? "Solving with PLAID_Core…"
                        : "Starting solver…",
                }
              : null
        }
      />

      {errorMessage && <section className="status-banner is-error">{errorMessage}</section>}

      {capNotice && (
        <div className="confirm-overlay" role="alertdialog" aria-label="Solvent caps notice">
          <div className="confirm-dialog">
            <p className="confirm-dialog-msg">{capNotice}</p>
            <div className="confirm-dialog-btns">
              <button type="button" className="confirm-btn is-cancel" onClick={() => setCapNotice(null)}>
                Got it
              </button>
            </div>
          </div>
        </div>
      )}

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

      {showClearMetaWarning && (
        <ConflictWarning
          message="Removing this metadata file will clear the solvent caps you set for this run."
          cancelLabel="Cancel"
          confirmLabel="Remove & clear caps"
          onCancel={() => setShowClearMetaWarning(false)}
          onConfirm={() => { setShowClearMetaWarning(false); clearMetaFile(); }}
        />
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
          onClearMeta={handleClearMetaRequest}
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
            targetPlateDefs={targetDefsForDispenser}
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
            canProcess={Boolean(layoutFile && (metaFile || sourceLayoutFile) && preview)}
            onConfigChange={handleConfigChange}
            onProcess={() => { if (layoutFile && (metaFile || sourceLayoutFile) && config && preview) setShowConfirmRun(true); }}
            sourceLayoutFile={sourceLayoutFile}
            onSourceLayoutFileChange={(f) => void applySourceLayoutUpload(f)}
            solventFamilies={solventFamilies}
            selectedSolventKey={selectedSolventKey}
            onSelectedSolventChange={setSelectedSolventKey}
            onSolventCapChange={handleSolventCapChange}
          />
        )}
      </div>

      {showConfirmRun && (
        <ConfirmRunModal
          hasEdits={Boolean(workingPreview)}
          isEditMode={isEditMode}
          sourceLayoutFileName={sourceLayoutFile?.name ?? config?.source_layout_file ?? null}
          sourcePlateType={config?.sourceplate_type}
          solventFamilies={solventFamilies}
          solventCaps={config?.solvent_caps_pct}
          onConfirm={handleConfirmRun}
          onClose={() => setShowConfirmRun(false)}
        />
      )}

      {metaCreatorOpen && (
        <MetaCreatorModal
          initialRows={metaCreatorRows}
          projectDetails={downloadProjectDetails}
          onClose={() => setMetaCreatorOpen(false)}
          onApply={applyMetaFromCreator}
        />
      )}

      {conflictWarning && (
        <ConflictWarning
          message={conflictWarning.message}
          onConfirm={conflictWarning.onConfirm}
          onCancel={dismissConflictWarning}
        />
      )}

      {sourceLayoutWarning && (
        <InvalidFileWarning
          title="Invalid source plate layout CSV"
          detail={`iPLAID can't accept this file as a Source plate layout — the format is wrong.\n\n${sourceLayoutWarning}`}
          onDismiss={() => setSourceLayoutWarning(null)}
        />
      )}
    </div>
  );
}
