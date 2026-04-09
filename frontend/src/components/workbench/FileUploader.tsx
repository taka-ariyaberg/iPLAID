import { ChangeEvent } from "react";
import "./FileUploader.css";

type FileUploaderProps = {
  layoutFile: File | null;
  metaFile: File | null;
  layoutInputKey: number;
  metaInputKey: number;
  layoutSource: "upload" | "design" | null;
  metaSource: "upload" | "created" | null;
  onLayoutChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onMetaChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onClearLayout: () => void;
  onClearMeta: () => void;
  /** Whether the PLAID_Core design panel is currently open */
  designActive: boolean;
  onDesignToggle: () => void;
  /** Whether the meta-creator modal is open */
  metaCreatorActive: boolean;
  onMetaCreatorOpen: () => void;
};

export function FileUploader({
  layoutFile,
  metaFile,
  layoutInputKey,
  metaInputKey,
  layoutSource,
  metaSource,
  onLayoutChange,
  onMetaChange,
  onClearLayout,
  onClearMeta,
  designActive,
  onDesignToggle,
  metaCreatorActive,
  onMetaCreatorOpen,
}: FileUploaderProps) {
  const designLoaded = !designActive && layoutSource === "design" && Boolean(layoutFile);
  const metaLoaded   = !metaCreatorActive && metaSource === "created" && Boolean(metaFile);
  const layoutUploaded = layoutSource === "upload" && Boolean(layoutFile);
  const metaUploaded   = metaSource === "upload" && Boolean(metaFile);
  return (
    <section className="panel-surface uploader-panel">
      <div className="panel-header-row">
        <div>
          <p className="section-kicker">Inputs</p>
          <h3>Run files</h3>
        </div>
      </div>

      <div className="upload-grid">

        {/* ── Left column: Layout CSV + Design with PLAID ── */}
        <div className="upload-col">
          <div className={`upload-zone ${layoutUploaded ? "is-loaded" : ""}`}>
            <label className="upload-zone-target" htmlFor="upload-layout">
              <div className="upload-zone-icon" aria-hidden="true">
                {layoutUploaded ? (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                )}
              </div>
              <div className="upload-zone-body">
                <span className="upload-zone-title">{layoutUploaded ? layoutFile!.name : "Upload Layout CSV"}</span>
                <span className="upload-zone-hint">{layoutUploaded ? "Click to replace" : "Target-plate layout CSV"}</span>
              </div>
            </label>
            <input key={layoutInputKey} id="upload-layout" type="file" accept=".csv" onChange={onLayoutChange} />
            <div className="upload-zone-right">
              <div className={`upload-zone-badge ${layoutUploaded ? "is-loaded" : "is-waiting"}`}>
                {layoutUploaded ? "Loaded" : "Required"}
              </div>
              {layoutUploaded && (
                <button type="button" className="upload-zone-clear" title="Remove file" onClick={onClearLayout}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* Design with PLAID */}
          <div className="upload-col-divider"><span>or</span></div>
          <div className={`uploader-action-shell uploader-action-shell--design${designActive ? " is-active" : designLoaded ? " is-loaded" : ""}`}>
            <button
              type="button"
              className="uploader-action-btn"
              onClick={onDesignToggle}
            >
              <div className="uploader-action-icon-box">
                {designActive ? (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="19" y1="12" x2="5" y2="12" />
                    <polyline points="12 19 5 12 12 5" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
                  </svg>
                )}
              </div>
              <div className="uploader-action-body">
                <span className="uploader-action-title">
                  {designActive ? "Close Designer" : "Design with PLAID"}
                </span>
                <span className="uploader-action-hint">
                  {designActive ? "Return to manual file upload" : designLoaded ? "Layout designed — click to redesign" : "Auto-generate a target-plate layout"}
                </span>
              </div>
            </button>
            <div className="uploader-action-tools">
              <div className={`uploader-action-badge${designActive ? " is-active-design" : designLoaded ? " is-loaded-action" : ""}`}>
                {designActive ? "Active" : designLoaded ? "Loaded" : "Optional"}
              </div>
              {designLoaded && (
                <button
                  type="button"
                  className="upload-zone-clear"
                  title="Remove designed layout"
                  aria-label="Remove designed layout"
                  onClick={onClearLayout}
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

        {/* ── Right column: Meta CSV + Create Metadata ── */}
        <div className="upload-col">
          <div className={`upload-zone ${metaUploaded ? "is-loaded" : ""}`}>
            <label className="upload-zone-target" htmlFor="upload-meta">
              <div className="upload-zone-icon" aria-hidden="true">
                {metaUploaded ? (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                )}
              </div>
              <div className="upload-zone-body">
                <span className="upload-zone-title">{metaUploaded ? metaFile!.name : "Upload Metadata CSV"}</span>
                <span className="upload-zone-hint">{metaUploaded ? "Click to replace" : "Compound names, stock concs. & solvents"}</span>
              </div>
            </label>
            <input key={metaInputKey} id="upload-meta" type="file" accept=".csv" onChange={onMetaChange} />
            <div className="upload-zone-right">
              <div className={`upload-zone-badge ${metaUploaded ? "is-loaded" : "is-waiting"}`}>
                {metaUploaded ? "Loaded" : "Required"}
              </div>
              {metaUploaded && (
                <button type="button" className="upload-zone-clear" title="Remove file" onClick={onClearMeta}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* Create Metadata */}
          <div className="upload-col-divider"><span>or</span></div>
          <div className={`uploader-action-shell uploader-action-shell--meta${metaCreatorActive ? " is-active" : metaLoaded ? " is-loaded" : ""}`}>
            <button
              type="button"
              className="uploader-action-btn"
              onClick={onMetaCreatorOpen}
            >
              <div className="uploader-action-icon-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="12" y1="11" x2="12" y2="17" />
                  <line x1="9" y1="14" x2="15" y2="14" />
                </svg>
              </div>
              <div className="uploader-action-body">
                <span className="uploader-action-title">Create Metadata</span>
                <span className="uploader-action-hint">
                  {metaLoaded ? "Metadata created — click to edit" : "Build a metadata CSV for compounds, stocks and solvents"}
                </span>
              </div>
            </button>
            <div className="uploader-action-tools">
              <div className={`uploader-action-badge${metaCreatorActive ? " is-active-meta" : metaLoaded ? " is-loaded-action" : ""}`}>
                {metaCreatorActive ? "Active" : metaLoaded ? "Loaded" : "Optional"}
              </div>
              {metaLoaded && (
                <button
                  type="button"
                  className="upload-zone-clear"
                  title="Remove created metadata"
                  aria-label="Remove created metadata"
                  onClick={onClearMeta}
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

      </div>
    </section>
  );
}
