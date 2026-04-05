import { ChangeEvent } from "react";
import "./FileUploader.css";

type FileUploaderProps = {
  layoutFile: File | null;
  metaFile: File | null;
  layoutInputKey: number;
  onLayoutChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onMetaChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onClearLayout: () => void;
  onClearMeta: () => void;
};

export function FileUploader({
  layoutFile,
  metaFile,
  layoutInputKey,
  onLayoutChange,
  onMetaChange,
  onClearLayout,
  onClearMeta,
}: FileUploaderProps) {
  return (
    <section className="panel-surface uploader-panel">
      <div className="panel-header-row">
        <div>
          <p className="section-kicker">Inputs</p>
          <h3>Run files</h3>
        </div>
      </div>

      <div className="upload-grid">
        {/* Layout CSV */}
        <div className={`upload-zone ${layoutFile ? "is-loaded" : ""}`}>
          <label className="upload-zone-target" htmlFor="upload-layout">
            <div className="upload-zone-icon" aria-hidden="true">
              {layoutFile ? (
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
              <span className="upload-zone-title">{layoutFile ? layoutFile.name : "Layout CSV"}</span>
              <span className="upload-zone-hint">{layoutFile ? "Click to replace" : "Target-plate well assignments"}</span>
            </div>
          </label>
          <input key={layoutInputKey} id="upload-layout" type="file" accept=".csv" onChange={onLayoutChange} />
          <div className="upload-zone-right">
            <div className={`upload-zone-badge ${layoutFile ? "is-loaded" : "is-waiting"}`}>
              {layoutFile ? "Loaded" : "Required"}
            </div>
            {layoutFile && (
              <button type="button" className="upload-zone-clear" title="Remove file" onClick={onClearLayout}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* Metadata CSV */}
        <div className={`upload-zone ${metaFile ? "is-loaded" : ""}`}>
          <label className="upload-zone-target" htmlFor="upload-meta">
            <div className="upload-zone-icon" aria-hidden="true">
              {metaFile ? (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <line x1="3" y1="9" x2="21" y2="9" />
                  <line x1="9" y1="21" x2="9" y2="9" />
                </svg>
              )}
            </div>
            <div className="upload-zone-body">
              <span className="upload-zone-title">{metaFile ? metaFile.name : "Metadata CSV"}</span>
              <span className="upload-zone-hint">{metaFile ? "Click to replace" : "Compound names & concentrations"}</span>
            </div>
          </label>
          <input id="upload-meta" type="file" accept=".csv" onChange={onMetaChange} />
          <div className="upload-zone-right">
            <div className={`upload-zone-badge ${metaFile ? "is-loaded" : "is-waiting"}`}>
              {metaFile ? "Loaded" : "Required"}
            </div>
            {metaFile && (
              <button type="button" className="upload-zone-clear" title="Remove file" onClick={onClearMeta}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
