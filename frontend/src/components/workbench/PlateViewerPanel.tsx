import { PlateGrid } from "../PlateGrid";
import type { LayoutPreview, TargetPlateDefinition } from "../../types";
import "./PlateViewerPanel.css";

type PlateViewerPanelProps = {
  preview: LayoutPreview | null;
  originalPreview: LayoutPreview | null;
  targetPlateDefs: TargetPlateDefinition[];
  viewerPlateTypeId: string;
  onViewerPlateTypeChange: (id: string) => void;
  customRows: number;
  onCustomRowsChange: (n: number) => void;
  customCols: number;
  onCustomColsChange: (n: number) => void;
  plateDef: TargetPlateDefinition | undefined;
  exportProjectDetails?: string | string[];
  plateTooSmall: boolean;
  maxDataRows: number;
  maxDataCols: number;
  isEditMode: boolean;
  revertKey: number;
  onEditModeToggle: () => void;
  onEditChange: (updated: LayoutPreview) => void;
  onSaveEdits: () => void;
  onRevertAll: () => void;
};

export function PlateViewerPanel({
  preview,
  originalPreview,
  targetPlateDefs,
  viewerPlateTypeId,
  onViewerPlateTypeChange,
  customRows,
  onCustomRowsChange,
  customCols,
  onCustomColsChange,
  plateDef,
  exportProjectDetails,
  plateTooSmall,
  maxDataRows,
  maxDataCols,
  isEditMode,
  revertKey,
  onEditModeToggle,
  onEditChange,
  onSaveEdits,
  onRevertAll,
}: PlateViewerPanelProps) {
  if (!preview) {
    return <section className="page-state">Upload a layout CSV to visualize the plate map.</section>;
  }

  return (
    <PlateGrid
      preview={preview}
      originalPreview={originalPreview ?? undefined}
      title="Plate viewer"
      plateDef={plateDef}
      exportProjectDetails={exportProjectDetails}
      exportScope="workbench"
      isEditMode={isEditMode}
      revertKey={revertKey}
      onEditChange={onEditChange}
      onSaveEdits={onSaveEdits}
      onRevertAll={onRevertAll}
      showDefaultTooltip
    >
      <div className="plate-type-selector">
        <label className="plate-type-selector-label" htmlFor="viewer-plate-type">Target plate type</label>
        <select
          id="viewer-plate-type"
          className="plate-type-selector-select"
          value={viewerPlateTypeId}
          onChange={(e) => onViewerPlateTypeChange(e.target.value)}
        >
          {targetPlateDefs.map((def) => (
            <option key={def.id} value={def.id}>{def.label}</option>
          ))}
          <option value="custom">Custom…</option>
        </select>
        {viewerPlateTypeId === "custom" && (
          <div className="plate-type-custom">
            <label>
              Rows
              <input
                type="number" min={1} max={64} value={customRows}
                onChange={(e) => onCustomRowsChange(Math.max(1, parseInt(e.target.value, 10) || 1))}
              />
            </label>
            <label>
              Columns
              <input
                type="number" min={1} max={96} value={customCols}
                onChange={(e) => onCustomColsChange(Math.max(1, parseInt(e.target.value, 10) || 1))}
              />
            </label>
          </div>
        )}
        <button
          type="button"
          className={`edit-mode-btn${isEditMode ? " is-active" : ""}`}
          onClick={onEditModeToggle}
          title={isEditMode ? "Exit edit mode" : "Enter edit mode to modify well assignments"}
        >
          {isEditMode ? "Editing…" : "Edit layout"}
        </button>
      </div>
      {plateTooSmall && (
        <div className="plate-type-warning">
          <span className="plate-type-warning-icon">⚠</span>
          Selected plate ({plateDef!.rows}&thinsp;×&thinsp;{plateDef!.cols}) is smaller than the
          layout data ({maxDataRows}&thinsp;rows&thinsp;×&thinsp;{maxDataCols}&thinsp;cols) — wells outside
          this grid will not be displayed.
        </div>
      )}
    </PlateGrid>
  );
}
