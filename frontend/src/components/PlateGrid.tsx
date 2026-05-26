import { Fragment, ReactNode, useEffect, useMemo, useRef, useState } from "react";

import type { LayoutPreview, TargetPlateDefinition } from "../types";
import "../styles/PlateViewer.css";
import { DMSO_COLOR, EMPTY_COLOR, getConcColor, getCompoundColor } from "../utils/colorUtils";
import { buildPlateExportFilename } from "../utils/downloadFilenames";
import { downloadPlatePng, downloadPlateSvg, downloadPlateCsv } from "../utils/plateExport";
import { canonicalWellId, formatWellId, normalizeWellKey } from "../utils/wellUtils";

function buildRowLabels(count: number): string[] {
  return Array.from({ length: count }, (_, index) => {
    let value = index + 1;
    let label = "";
    while (value > 0) {
      const remainder = (value - 1) % 26;
      label = String.fromCharCode(65 + remainder) + label;
      value = Math.floor((value - 1) / 26);
    }
    return label;
  });
}

function getPlateFrame(
  plateDef: TargetPlateDefinition | undefined,
  plate: LayoutPreview["plates"][number],
) {
  if (plateDef) {
    return {
      rowLabels: buildRowLabels(plateDef.rows),
      columnLabels: Array.from({ length: plateDef.cols }, (_, index) => index + 1),
    };
  }
  return {
    rowLabels: plate.rowLabels,
    columnLabels: plate.columnLabels,
  };
}

function abbreviateCompound(compound: string): string {
  if (compound.toUpperCase() === "DMSO") {
    return "DM";
  }
  return compound
    .split(/\s+/)
    .map((part) => part.slice(0, 1).toUpperCase())
    .join("")
    .slice(0, 2);
}

type PlateGridProps = {
  preview: LayoutPreview;
  title: string;
  plateDef?: TargetPlateDefinition;
  concentrationUnit?: string;
  exportProjectDetails?: string | string[];
  exportScope?: "target" | "source" | "workbench";
  children?: ReactNode;
  isEditMode?: boolean;
  originalPreview?: LayoutPreview;
  revertKey?: number;
  onEditChange?: (updated: LayoutPreview) => void;
  onSaveEdits?: () => void;
  onRevertAll?: () => void;
  /** Optional custom tooltip rendered in a floating panel when a well is hovered.
   *  Receives the well id as `"plateId:wellName"`. Return null to use no tooltip. */
  wellTooltipContent?: (wellId: string) => ReactNode | null;
  /** When true (and no wellTooltipContent is supplied), shows a built-in floating
   *  tooltip panel with well id, compound and concentration for any hovered well. */
  showDefaultTooltip?: boolean;
  /** Optional extra content rendered inside each concentration block in the info panel.
   *  Called with (compound, concLabel) — return null to render nothing for that entry. */
  concBlockExtras?: (compound: string, concLabel: string) => ReactNode | null;
  /** Optional set of composite well ids (`${plateId}:${wellId}`) that should be
   *  rendered with a diagonal-line "skipped" overlay (e.g. excluded-compound wells). */
  excludedWells?: Set<string>;
};

type WellRecord = {
  plateId: string;
  well: string;
  compound: string | null;
  concentration: number | null;
  isControl: boolean;
  isFilled: boolean;
};

function formatConcentration(concentration: number | null, unit = "µM"): string {
  if (concentration === null) {
    return "No concentration";
  }
  return `${concentration} ${unit}`;
}

function formatWellCount(count: number): string {
  return `(${count} well${count === 1 ? "" : "s"})`;
}

// ── Custom combobox: free-type input + toggle dropdown of suggestions ─────────

type ComboboxOption = { label: string; value: string };

type EditComboboxProps = {
  value: string;
  onChange: (v: string) => void;
  options: ComboboxOption[];
  placeholder: string;
  onClear?: () => void;
};

function EditCombobox({ value, onChange, options, placeholder, onClear }: EditComboboxProps) {
  const [isOpen, setIsOpen] = useState(false);
  const openedByToggleRef = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, []);

  // Toggle button shows ALL options so user can overwrite typed text by picking from full list.
  // Filtering only applies when dropdown is opened programmatically (not currently used).
  const displayOptions = (isOpen && openedByToggleRef.current)
    ? options
    : value
    ? options.filter((o) => o.label.toLowerCase().includes(value.toLowerCase()))
    : options;

  return (
    <div className="edit-combobox" ref={containerRef}>
      <div className="edit-combobox-row">
        <input
          className="edit-assign-input edit-combobox-input"
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsOpen(false)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); setIsOpen(false); }
            if (e.key === "Escape") setIsOpen(false);
          }}
        />
        {value && onClear && (
          <button
            type="button"
            className="edit-combobox-clear"
            onClick={() => { onClear(); setIsOpen(false); }}
            tabIndex={-1}
          >
            ×
          </button>
        )}
        <button
          type="button"
          className={`edit-combobox-toggle${isOpen ? " is-open" : ""}`}
          onClick={() => { openedByToggleRef.current = true; setIsOpen((v) => !v); }}
          tabIndex={-1}
        >
          ▾
        </button>
      </div>
      {isOpen && displayOptions.length > 0 && (
        <ul className="edit-combobox-list" role="listbox">
          {displayOptions.map((opt) => (
            <li key={opt.value} role="option" aria-selected={opt.value === value}>
              <button
                type="button"
                className={`edit-combobox-option${opt.value === value ? " is-selected" : ""}`}
                onClick={() => { onChange(opt.value); setIsOpen(false); }}
              >
                {opt.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function PlateGrid({
  preview,
  title,
  plateDef,
  concentrationUnit = "µM",
  exportProjectDetails,
  exportScope = "workbench",
  children,
  isEditMode = false,
  originalPreview,
  revertKey,
  onEditChange,
  onSaveEdits,
  onRevertAll,
  wellTooltipContent,
  showDefaultTooltip = false,
  concBlockExtras,
  excludedWells,
}: PlateGridProps) {
  const [selectedWellIds, setSelectedWellIds] = useState<string[]>([]);
  // key = `${compound}::${concLabel}` of the hovered concentration subgroup in the info panel
  const [hoveredConcKey, setHoveredConcKey] = useState<string | null>(null);
  const [hoveredSingleWellId, setHoveredSingleWellId] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);
  // well IDs that are "spotlit" — all others get dimmed overlay
  const [highlightedWellIds, setHighlightedWellIds] = useState<Set<string>>(new Set());
  // Edit mode state
  const [undoStack, setUndoStack] = useState<LayoutPreview[]>([]);
  const [redoStack, setRedoStack] = useState<LayoutPreview[]>([]);
  const [anchorWellId, setAnchorWellId] = useState<string | null>(null);
  const [editCompound, setEditCompound] = useState<string>("");
  const [editConc, setEditConc] = useState<string>("");
  const [showOriginalLocal, setShowOriginalLocal] = useState(false);
  const [shiftWarning, setShiftWarning] = useState<string | null>(null);
  // Overwrite conflict: filled wells among selected at assign time
  const [assignConflict, setAssignConflict] = useState<{ filledIds: string[] } | null>(null);
  // Copy/paste clipboard: relative offsets from the copy-time anchor
  type ClipboardEntry = {
    plateId: string;
    rowOffset: number;
    colOffset: number;
    compound: string;
    concentration: number | null;
    isControl: boolean;
  };
  const [clipboard, setClipboard] = useState<ClipboardEntry[] | null>(null);
  // Paste conflict: filled wells that would be overwritten
  const [pasteConflict, setPasteConflict] = useState<{
    newPlates: LayoutPreview["plates"];
    newWellCount: number;
    conflictCount: number;
    conflictWells: string[];
    skipPlates: LayoutPreview["plates"];
    skipWellCount: number;
  } | null>(null);
  // Drag-select refs (not state — we don't want re-renders on every cell enter)
  const isPointerDownRef = useRef(false);
  const dragAnchorIdRef = useRef<string | null>(null);
  const dragShiftRef = useRef(false);
  const dragDeselectRef = useRef(false);
  const dragBaseSelectionRef = useRef<string[]>([]);
  // Stable compound→index map so that adding new compounds never shifts existing colors.
  const compoundColorIndexRef = useRef<Map<string, number>>(new Map());
  const resolvedExportProjectDetails = exportProjectDetails ?? title;

  if (!preview.plates.length) {
    return null;
  }

  // In compare mode (edit mode only) temporarily show the original layout
  const displayPreview =
    isEditMode && showOriginalLocal && originalPreview ? originalPreview : preview;

  const renderedPlates = useMemo(() => {
    return displayPreview.plates.map((plate) => {
      const frame = getPlateFrame(plateDef, plate);
      // Store lookup keys in compact form so uploads with "B2" and "B02" map to
      // the same logical cell while the UI consistently renders padded well IDs.
      const wellMap = new Map(
        plate.wells.map((well) => [normalizeWellKey(well.well), well]),
      );

      const allWells: WellRecord[] = [];
      const wellLookup = new Map<string, WellRecord>();
      frame.rowLabels.forEach((rowLabel) => {
        frame.columnLabels.forEach((column) => {
          const wellName = formatWellId(rowLabel, column);
          const well = wellMap.get(normalizeWellKey(wellName));
          const record = {
            plateId: plate.plateId,
            well: wellName,
            compound: well?.compound ?? null,
            concentration: well?.concentration ?? null,
            isControl: Boolean(well?.isControl),
            isFilled: Boolean(well),
          };
          allWells.push(record);
          wellLookup.set(wellName, record);
        });
      });

      return {
        ...plate,
        rowLabels: frame.rowLabels,
        columnLabels: frame.columnLabels,
        allWells,
        wellLookup,
      };
    });
  }, [displayPreview, plateDef]);

  const selectionLookup = useMemo(() => {
    const lookup = new Map<string, WellRecord>();
    renderedPlates.forEach((plate) => {
      plate.allWells.forEach((well) => {
        lookup.set(`${plate.plateId}:${well.well}`, well);
      });
    });
    return lookup;
  }, [renderedPlates]);

  const legendGroups = useMemo(() => {
    const groups = new Map<string, {
      count: number;
      isControl: boolean;
      concentrations: Map<string, { numeric: number | null; count: number }>;
    }>();

    displayPreview.plates.forEach((plate) => {
      plate.wells.forEach((well) => {
        const compound = well.compound;
        const concentrationKey = well.concentration === null ? "No concentration" : String(well.concentration);
        const group = groups.get(compound) ?? {
          count: 0,
          isControl: Boolean(well.isControl),
          concentrations: new Map(),
        };
        group.count += 1;
        group.isControl = group.isControl || Boolean(well.isControl);
        const currentConcentration = group.concentrations.get(concentrationKey) ?? {
          numeric: well.concentration,
          count: 0,
        };
        currentConcentration.count += 1;
        group.concentrations.set(concentrationKey, currentConcentration);
        groups.set(compound, group);
      });
    });

    return Array.from(groups.entries())
      .sort((left, right) => left[0].localeCompare(right[0]))
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
  }, [displayPreview]);

  // Base (full-opacity) colour per compound — used for bars and headers.
  // Compound colors are stable: each compound gets a golden-angle hue based on its
  // sequential discovery index, so adding new compounds never shifts existing colors.
  const compoundColorLookup = useMemo(() => {
    const lookup = new Map<string, string>();
    const realGroups = legendGroups.filter((g) => !g.isControl);
    // Assign a stable index to each new compound — existing ones keep theirs forever.
    let nextIdx = compoundColorIndexRef.current.size;
    realGroups.forEach((group) => {
      if (!compoundColorIndexRef.current.has(group.compound)) {
        compoundColorIndexRef.current.set(group.compound, nextIdx++);
      }
    });
    legendGroups.forEach((group) => {
      if (group.isControl) {
        lookup.set(group.compound, DMSO_COLOR);
        return;
      }
      const idx = compoundColorIndexRef.current.get(group.compound) ?? 0;
      // Golden angle (137.508°) gives maximally-separated hues regardless of total count.
      const hue = (30 + idx * 137.508) % 360;
      lookup.set(group.compound, `hsl(${hue.toFixed(1)}, 88%, 62%)`);
    });
    return lookup;
  }, [legendGroups]);

  // Per-well fill colour: compound hue at varying opacity based on concentration rank.
  const wellColorLookup = useMemo(() => {
    const lookup = new Map<string, Map<string, string>>();
    legendGroups.forEach((group) => {
      const concMap = new Map<string, string>();
      const isControl = group.isControl;
      const baseColor = compoundColorLookup.get(group.compound)!;
      group.concentrations.forEach((conc, i) => {
        concMap.set(
          conc.label,
          isControl ? DMSO_COLOR : getConcColor(baseColor, i, group.concentrations.length),
        );
      });
      lookup.set(group.compound, concMap);
    });
    return lookup;
  }, [legendGroups, compoundColorLookup]);

  const selectedWells = useMemo(
    () =>
      selectedWellIds
        .map((wellId) => selectionLookup.get(wellId))
        .filter((well): well is WellRecord => Boolean(well)),
    [selectedWellIds, selectionLookup],
  );

  const totalEmptyCount = useMemo(
    () => renderedPlates.reduce((sum, plate) => sum + plate.allWells.filter((w) => !w.isFilled).length, 0),
    [renderedPlates],
  );

  // Selected wells grouped by compound, for pill display in the info panel.
  const selectedWellsByCompound = useMemo(() => {
    const lookup = new Map<string, WellRecord[]>();
    selectedWells.forEach((well) => {
      if (!well.isFilled || !well.compound) return;
      const list = lookup.get(well.compound) ?? [];
      list.push(well);
      lookup.set(well.compound, list);
    });
    return lookup;
  }, [selectedWells]);

  const selectedEmptyWells = useMemo(
    () => selectedWells.filter((w) => !w.isFilled),
    [selectedWells],
  );

  // Glow all matching wells on hover — no selection filter needed.
  const hoveredWellIds = useMemo<Set<string>>(() => {
    if (!hoveredConcKey) return new Set();
    const ids = new Set<string>();
    if (hoveredConcKey === "__empty__") {
      renderedPlates.forEach((plate) => {
        plate.allWells.forEach((well) => {
          if (!well.isFilled) ids.add(`${well.plateId}:${well.well}`);
        });
      });
    } else {
      const [compound, concLabel] = hoveredConcKey.split("::");
      renderedPlates.forEach((plate) => {
        plate.allWells.forEach((well) => {
          if (well.compound === compound && well.isFilled) {
            // "__all__" = compound-level hover: glow every well for this compound
            if (concLabel === "__all__") {
              ids.add(`${well.plateId}:${well.well}`);
            } else {
              const wLabel = well.concentration === null ? "No concentration" : String(well.concentration);
              if (wLabel === concLabel) ids.add(`${well.plateId}:${well.well}`);
            }
          }
        });
      });
    }
    return ids;
  }, [hoveredConcKey, renderedPlates]);

  useEffect(() => {
    // Don't reset while in edit mode — preview changes come from our own edits.
    // Also skip resetting interaction state when only plateDef changes (async bootstrap
    // load on ResultsPage would otherwise wipe an active highlight/selection).
    if (isEditMode) return;
    setSelectedWellIds([]);
    setHighlightedWellIds(new Set());
    setHoveredConcKey(null);
    setUndoStack([]);
    setRedoStack([]);
    setAnchorWellId(null);
    setShiftWarning(null);
    setShowOriginalLocal(false);
    setEditCompound("");
    setEditConc("");
    setAssignConflict(null);
    // Reset stable color assignments so a freshly loaded file starts from index 0.
    compoundColorIndexRef.current = new Map();
  }, [isEditMode, preview]); // plateDef omitted intentionally: it's a sizing hint loaded

  // "Revert all" in edit mode — clear selection even though isEditMode is true.
  useEffect(() => {
    if (revertKey === undefined) return;
    setSelectedWellIds([]);
    setAnchorWellId(null);
    setShiftWarning(null);
    setEditCompound("");
    setEditConc("");
    setAssignConflict(null);
    setPasteConflict(null);
    setClipboard(null);
    setUndoStack([]);
    setRedoStack([]);
  }, [revertKey]);

  // Release drag-select on global mouse-up
  useEffect(() => {
    function onPointerUp() {
      isPointerDownRef.current = false;
      dragAnchorIdRef.current = null;
    }
    document.addEventListener("pointerup", onPointerUp);
    return () => document.removeEventListener("pointerup", onPointerUp);
  }, []);

  // Keyboard shortcuts — only active in edit mode
  useEffect(() => {
    if (!isEditMode) return;

    function onKeyDown(e: KeyboardEvent) {
      // Don't steal keys when user is typing in an input or textarea
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const mod = e.metaKey || e.ctrlKey;
      if (mod && !e.shiftKey && e.key.toLowerCase() === "a") {
        e.preventDefault();
        const ids: string[] = [];
        renderedPlates.forEach((plate) => {
          plate.allWells.forEach((w) => { if (w.isFilled) ids.push(`${w.plateId}:${w.well}`); });
        });
        setSelectedWellIds(ids);
        return;
      }
      if (mod && e.shiftKey && e.key.toLowerCase() === "a") {
        e.preventDefault();
        const ids: string[] = [];
        renderedPlates.forEach((plate) => {
          plate.allWells.forEach((w) => ids.push(`${w.plateId}:${w.well}`));
        });
        setSelectedWellIds(ids);
        return;
      }
      if (mod && e.key.toLowerCase() === "c") {
        e.preventDefault();
        copySelected();
        return;
      }
      if (mod && e.key.toLowerCase() === "v") {
        e.preventDefault();
        pasteClipboard();
        return;
      }
      if (mod && e.key.toLowerCase() === "d") {
        e.preventDefault();
        setSelectedWellIds([]);
        setAnchorWellId(null);
        return;
      }
      if ((e.key === "Delete" || e.key === "Backspace") && !e.metaKey && !e.ctrlKey) {
        if (selectedWellIds.length === 0) return;
        clearSelectedWells();
        return;
      }
      if (mod && !e.shiftKey && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (!undoStack.length) return;
        const prev = undoStack[undoStack.length - 1];
        setRedoStack((r) => [preview, ...r]);
        setUndoStack((s) => s.slice(0, -1));
        onEditChange?.(prev);
        setSelectedWellIds([]);
        setAnchorWellId(null);
        return;
      }
      if (mod && e.shiftKey && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (!redoStack.length) return;
        const next = redoStack[0];
        setUndoStack((s) => [...s, preview]);
        setRedoStack((r) => r.slice(1));
        onEditChange?.(next);
        setSelectedWellIds([]);
        setAnchorWellId(null);
        return;
      }
      if (!mod && e.key === "ArrowLeft") { e.preventDefault(); shiftLayoutBy(0, -1); return; }
      if (!mod && e.key === "ArrowRight") { e.preventDefault(); shiftLayoutBy(0, 1); return; }
      if (!mod && e.key === "ArrowUp") { e.preventDefault(); shiftLayoutBy(-1, 0); return; }
      if (!mod && e.key === "ArrowDown") { e.preventDefault(); shiftLayoutBy(1, 0); return; }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditMode, selectedWellIds, undoStack, redoStack, preview, renderedPlates, clipboard, anchorWellId]);

  function applyEdit(newPreview: LayoutPreview) {
    setUndoStack((s) => [...s, preview]);
    setRedoStack([]);
    onEditChange?.(newPreview);
    setSelectedWellIds([]);
    setAnchorWellId(null);
    setAssignConflict(null);
    setShiftWarning(null);
  }

  function undoEdit() {
    if (!undoStack.length) return;
    const prev = undoStack[undoStack.length - 1];
    setRedoStack((r) => [preview, ...r]);
    setUndoStack((s) => s.slice(0, -1));
    onEditChange?.(prev);
    setSelectedWellIds([]);
    setAnchorWellId(null);
  }

  function redoEdit() {
    if (!redoStack.length) return;
    const next = redoStack[0];
    setUndoStack((s) => [...s, preview]);
    setRedoStack((r) => r.slice(1));
    onEditChange?.(next);
    setSelectedWellIds([]);
    setAnchorWellId(null);
  }

  function clearSelectedWells() {
    if (!selectedWellIds.length) return;
    const selectedSet = new Set(selectedWellIds);
    const newPlates = preview.plates.map((plate) => ({
      ...plate,
      wells: plate.wells.filter((w) => {
        return !selectedSet.has(`${plate.plateId}:${canonicalWellId(w.well)}`);
      }),
    }));
    const newWellCount = newPlates.reduce((sum, p) => sum + p.wells.length, 0);
    applyEdit({ ...preview, plates: newPlates, wellCount: newWellCount });
  }

  function assignCompoundToSelected() {
    if (!selectedWellIds.length || !editCompound || !editConc) return;
    // Check for already-filled wells among selection
    const filledIds = selectedWellIds.filter((id) => {
      const w = selectionLookup.get(id);
      return w?.isFilled;
    });
    if (filledIds.length > 0) {
      setAssignConflict({ filledIds });
      return;
    }
    doAssign(false);
  }

  function doAssign(skipFilled: boolean) {
    if (!editCompound || !editConc) return;
    const selectedSet = new Set(selectedWellIds);
    const concNumeric = editConc.trim().toLowerCase() === "no concentration" ? null : parseFloat(editConc);
    const concLabel = editConc.trim().toLowerCase() === "no concentration" ? null : (isNaN(concNumeric!) ? null : concNumeric);
    const newPlates = preview.plates.map((plate) => {
      const wellsMap = new Map(
        plate.wells.map((w) => [normalizeWellKey(w.well), w]),
      );
      selectedSet.forEach((sid) => {
        const colonIdx = sid.indexOf(":");
        const sidPlate = sid.slice(0, colonIdx);
        const sidWell = canonicalWellId(sid.slice(colonIdx + 1));
        if (sidPlate !== plate.plateId) return;
        const existingRecord = selectionLookup.get(sid);
        if (skipFilled && existingRecord?.isFilled) return;
        const parsed = sidWell.match(/^([A-Za-z]+)(\d+)$/);
        wellsMap.set(normalizeWellKey(sidWell), {
          well: sidWell,
          rowLabel: parsed ? parsed[1].toUpperCase() : "",
          column: parsed ? parseInt(parsed[2], 10) : 0,
          compound: editCompound,
          concentration: concLabel ?? null,
          isControl: editCompound.toUpperCase() === "DMSO" || concLabel === 0,
        });
      });
      return { ...plate, wells: Array.from(wellsMap.values()) };
    });
    const newWellCount = newPlates.reduce((sum, p) => sum + p.wells.length, 0);
    applyEdit({ ...preview, plates: newPlates, wellCount: newWellCount });
  }

  function copySelected() {
    const filledSelected = selectedWellIds
      .map((id) => selectionLookup.get(id))
      .filter((w): w is WellRecord => w !== undefined && w.isFilled);
    if (filledSelected.length === 0) return;

    // Excel-like: offsets are relative to the bounding-box top-left (minRow, minCol),
    // so pasting places the copied pattern's top-left at the destination cell.
    let minRowIdx = Infinity, minColIdx = Infinity;
    const wellPositions: { w: WellRecord; rowIdx: number; colIdx: number }[] = [];
    for (const w of filledSelected) {
      const rf = renderedPlates.find((rp) => rp.plateId === w.plateId);
      if (!rf) continue;
      const norm = normalizeWellKey(w.well);
      const parsed = norm.match(/^([A-Za-z]+)(\d+)$/);
      if (!parsed) continue;
      const rowIdx = rf.rowLabels.indexOf(parsed[1].toUpperCase());
      const colIdx = rf.columnLabels.indexOf(parseInt(parsed[2], 10));
      minRowIdx = Math.min(minRowIdx, rowIdx);
      minColIdx = Math.min(minColIdx, colIdx);
      wellPositions.push({ w, rowIdx, colIdx });
    }
    if (wellPositions.length === 0) return;

    const entries = wellPositions.map(({ w, rowIdx, colIdx }) => ({
      plateId: w.plateId,
      rowOffset: rowIdx - minRowIdx,
      colOffset: colIdx - minColIdx,
      compound: w.compound ?? "",
      concentration: w.concentration,
      isControl: w.isControl,
    }));
    setClipboard(entries);
  }

  function buildFloodFillPlates(targetIds: string[], skipConflicts: boolean): { plates: LayoutPreview["plates"]; wellCount: number } | null {
    if (!clipboard || clipboard.length !== 1) return null;
    const src = clipboard[0];
    // Group target well ids by plate
    const byPlate = new Map<string, { rowLabel: string; col: number; wellName: string }[]>();
    for (const id of targetIds) {
      const colonIdx = id.indexOf(":");
      const plateId = id.slice(0, colonIdx);
      const wellName = canonicalWellId(id.slice(colonIdx + 1));
      const parsed = normalizeWellKey(wellName).match(/^([A-Za-z]+)(\d+)$/);
      if (!parsed) continue;
      if (!byPlate.has(plateId)) byPlate.set(plateId, []);
      byPlate.get(plateId)!.push({ rowLabel: parsed[1].toUpperCase(), col: parseInt(parsed[2], 10), wellName });
    }
    const newPlates = preview.plates.map((plate) => {
      const targets = byPlate.get(plate.plateId);
      if (!targets) return plate;
      const wellsMap = new Map(plate.wells.map((w) => [normalizeWellKey(w.well), w]));
      for (const { rowLabel, col, wellName } of targets) {
        const wellKey = normalizeWellKey(wellName);
        if (skipConflicts && wellsMap.has(wellKey)) continue;
        wellsMap.set(wellKey, {
          well: wellName,
          rowLabel,
          column: col,
          compound: src.compound,
          concentration: src.concentration,
          isControl: src.isControl,
        });
      }
      return { ...plate, wells: Array.from(wellsMap.values()) };
    });
    return { plates: newPlates, wellCount: newPlates.reduce((s, p) => s + p.wells.length, 0) };
  }

  function buildPastePlates(skipConflicts: boolean): { plates: LayoutPreview["plates"]; wellCount: number } | null {
    if (!clipboard || !anchorWellId) return null;
    const [anchorPlateId, anchorWellName] = [anchorWellId.slice(0, anchorWellId.indexOf(":")), anchorWellId.slice(anchorWellId.indexOf(":") + 1)];
    const anchorRf = renderedPlates.find((rp) => rp.plateId === anchorPlateId);
    if (!anchorRf) return null;
    const anchorNorm = normalizeWellKey(anchorWellName);
    const anchorParsed = anchorNorm.match(/^([A-Za-z]+)(\d+)$/);
    if (!anchorParsed) return null;
    const anchorRowIdx = anchorRf.rowLabels.indexOf(anchorParsed[1].toUpperCase());
    const anchorColIdx = anchorRf.columnLabels.indexOf(parseInt(anchorParsed[2], 10));

    // Check bounds first
    for (const entry of clipboard) {
      const rf = renderedPlates.find((rp) => rp.plateId === (entry.plateId === anchorPlateId ? anchorPlateId : entry.plateId)) ?? anchorRf;
      const tr = anchorRowIdx + entry.rowOffset;
      const tc = anchorColIdx + entry.colOffset;
      if (tr < 0 || tr >= rf.rowLabels.length || tc < 0 || tc >= rf.columnLabels.length) {
        setShiftWarning(`⚠ Paste blocked — ${clipboard.length > 1 ? "some wells" : "the well"} would fall outside the plate bounds.`);
        return null;
      }
    }
    setShiftWarning(null);

    const newPlates = preview.plates.map((plate) => {
      // Only paste into anchor's plate
      if (plate.plateId !== anchorPlateId) return plate;
      const rf = anchorRf;
      const wellsMap = new Map(plate.wells.map((w) => [normalizeWellKey(w.well), w]));
      for (const entry of clipboard) {
        const tr = anchorRowIdx + entry.rowOffset;
        const tc = anchorColIdx + entry.colOffset;
        const targetWell = formatWellId(rf.rowLabels[tr], rf.columnLabels[tc]);
        const targetWellKey = normalizeWellKey(targetWell);
        if (skipConflicts && wellsMap.has(targetWellKey)) continue;
        const parsed = targetWell.match(/^([A-Za-z]+)(\d+)$/);
        wellsMap.set(targetWellKey, {
          well: targetWell,
          rowLabel: parsed ? parsed[1].toUpperCase() : "",
          column: parsed ? parseInt(parsed[2], 10) : 0,
          compound: entry.compound,
          concentration: entry.concentration,
          isControl: entry.isControl,
        });
      }
      return { ...plate, wells: Array.from(wellsMap.values()) };
    });
    return { plates: newPlates, wellCount: newPlates.reduce((s, p) => s + p.wells.length, 0) };
  }

  function pasteClipboard() {
    if (!clipboard || !anchorWellId) return;

    // ── Flood-fill mode: single copied well + multiple selected wells ─────────
    // Fill every selected well with the clipboard compound/concentration.
    if (clipboard.length === 1 && selectedWellIds.length > 1) {
      const src = clipboard[0];
      // Exclude no-ops: wells already filled with the exact same compound+concentration.
      const conflictIds = selectedWellIds.filter((id) => {
        const w = selectionLookup.get(id);
        if (!w?.isFilled) return false;
        if (w.compound === src.compound && w.concentration === src.concentration) return false;
        return true;
      });
      const conflictCount = conflictIds.length;
      const conflictWells = conflictIds.map((id) => canonicalWellId(id.slice(id.indexOf(":") + 1)));
      if (conflictCount > 0) {
        const overwrite = buildFloodFillPlates(selectedWellIds, false)!;
        const skip = buildFloodFillPlates(selectedWellIds, true)!;
        setPasteConflict({ newPlates: overwrite.plates, newWellCount: overwrite.wellCount, conflictCount, conflictWells, skipPlates: skip.plates, skipWellCount: skip.wellCount });
        return;
      }
      const result = buildFloodFillPlates(selectedWellIds, false);
      if (!result) return;
      setUndoStack((s) => [...s, preview]);
      setRedoStack([]);
      setSelectedWellIds([]);
      setAnchorWellId(null);
      onEditChange?.({ ...preview, plates: result.plates, wellCount: result.wellCount });
      return;
    }
    // ── Normal paste: stamp clipboard pattern relative to anchor ─────────────
    const [anchorPlateId, anchorWellName] = [anchorWellId.slice(0, anchorWellId.indexOf(":")), anchorWellId.slice(anchorWellId.indexOf(":") + 1)];
    const anchorRf = renderedPlates.find((rp) => rp.plateId === anchorPlateId);
    if (!anchorRf) return;
    const anchorNorm = normalizeWellKey(anchorWellName);
    const anchorParsed = anchorNorm.match(/^([A-Za-z]+)(\d+)$/);
    if (!anchorParsed) return;
    const anchorRowIdx = anchorRf.rowLabels.indexOf(anchorParsed[1].toUpperCase());
    const anchorColIdx = anchorRf.columnLabels.indexOf(parseInt(anchorParsed[2], 10));

    // Check bounds
    for (const entry of clipboard) {
      const tr = anchorRowIdx + entry.rowOffset;
      const tc = anchorColIdx + entry.colOffset;
      if (tr < 0 || tr >= anchorRf.rowLabels.length || tc < 0 || tc >= anchorRf.columnLabels.length) {
        setShiftWarning(`⚠ Paste blocked — ${clipboard.length > 1 ? "some wells" : "the well"} would fall outside the plate bounds.`);
        return;
      }
    }
    setShiftWarning(null);

    // Find conflicts: clipboard targets that already have wells
    const targetPlate = preview.plates.find((p) => p.plateId === anchorPlateId);
    if (!targetPlate) return;
    const existingWells = new Set(targetPlate.wells.map((w) => normalizeWellKey(w.well)));
    const conflictWells: string[] = [];
    for (const entry of clipboard) {
      const tr = anchorRowIdx + entry.rowOffset;
      const tc = anchorColIdx + entry.colOffset;
      const targetWell = formatWellId(anchorRf.rowLabels[tr], anchorRf.columnLabels[tc]);
      if (existingWells.has(normalizeWellKey(targetWell))) conflictWells.push(targetWell);
    }
    const conflictCount = conflictWells.length;

    if (conflictCount > 0) {
      // Pre-compute both overwrite and skip variants so the popup can commit either
      const overwrite = buildPastePlates(false)!;
      const skip = buildPastePlates(true)!;
      setPasteConflict({ newPlates: overwrite.plates, newWellCount: overwrite.wellCount, conflictCount, conflictWells, skipPlates: skip.plates, skipWellCount: skip.wellCount });
      return;
    }

    const result = buildPastePlates(false);
    if (!result) return;
    setUndoStack((s) => [...s, preview]);
    setRedoStack([]);
    setSelectedWellIds([]);
    setAnchorWellId(null);
    onEditChange?.({ ...preview, plates: result.plates, wellCount: result.wellCount });
  }

  function commitPaste(skipConflicts: boolean) {
    if (!pasteConflict) return;
    const plates = skipConflicts ? pasteConflict.skipPlates : pasteConflict.newPlates;
    const wellCount = skipConflicts ? pasteConflict.skipWellCount : pasteConflict.newWellCount;
    setPasteConflict(null);
    setUndoStack((s) => [...s, preview]);
    setRedoStack([]);
    setSelectedWellIds([]);
    setAnchorWellId(null);
    onEditChange?.({ ...preview, plates, wellCount });
  }

  function shiftLayoutBy(rowOffset: number, colOffset: number) {
    // Only shift FILLED wells. If some filled wells are selected, move only those.
    // Otherwise move all filled wells.
    const selectedFilledIds = new Set(
      selectedWellIds.filter((id) => selectionLookup.get(id)?.isFilled),
    );
    const moveAll = selectedFilledIds.size === 0;

    // First pass: check if ANY well would go out of bounds. If so, block the move entirely.
    let clippedCount = 0;
    for (const plate of preview.plates) {
      const rf = renderedPlates.find((rp) => rp.plateId === plate.plateId);
      if (!rf) continue;
      for (const well of plate.wells) {
        const norm = normalizeWellKey(well.well);
        const shouldMove = moveAll || selectedFilledIds.has(`${plate.plateId}:${canonicalWellId(well.well)}`);
        if (!shouldMove) continue;
        const parsed = norm.match(/^([A-Za-z]+)(\d+)$/);
        if (!parsed) continue;
        const rowIdx = rf.rowLabels.indexOf(parsed[1].toUpperCase());
        const colIdx = rf.columnLabels.indexOf(parseInt(parsed[2], 10));
        if (rowIdx === -1 || colIdx === -1) continue;
        const newRowIdx = rowIdx + rowOffset;
        const newColIdx = colIdx + colOffset;
        if (
          newRowIdx < 0 ||
          newRowIdx >= rf.rowLabels.length ||
          newColIdx < 0 ||
          newColIdx >= rf.columnLabels.length
        ) {
          clippedCount++;
        }
      }
    }
    if (clippedCount > 0) {
      setShiftWarning(
        `Move blocked — ${clippedCount} well${clippedCount > 1 ? "s" : ""} would fall outside the plate bounds.`,
      );
      return;
    }
    setShiftWarning(null);

    // Second pass: commit the move (guaranteed no clipping).
    const idMap = new Map<string, string>();
    const newPlates = preview.plates.map((plate) => {
      const rf = renderedPlates.find((rp) => rp.plateId === plate.plateId);
      if (!rf) return plate;
      const newWells = plate.wells.map((well) => {
        const norm = normalizeWellKey(well.well);
        const shouldMove = moveAll || selectedFilledIds.has(`${plate.plateId}:${canonicalWellId(well.well)}`);
        if (!shouldMove) return well;
        const parsed = norm.match(/^([A-Za-z]+)(\d+)$/)!;
        const newRowIdx = rf.rowLabels.indexOf(parsed[1].toUpperCase()) + rowOffset;
        const newColIdx = rf.columnLabels.indexOf(parseInt(parsed[2], 10)) + colOffset;
        const newWellName = formatWellId(rf.rowLabels[newRowIdx], rf.columnLabels[newColIdx]);
        idMap.set(`${plate.plateId}:${canonicalWellId(well.well)}`, `${plate.plateId}:${newWellName}`);
        return { ...well, well: newWellName };
      });
      return { ...plate, wells: newWells };
    });
    const newWellCount = newPlates.reduce((sum, p) => sum + p.wells.length, 0);

    // Don't call applyEdit — we want to preserve (and remap) the selection.
    setUndoStack((s) => [...s, preview]);
    setRedoStack([]);
    onEditChange?.({ ...preview, plates: newPlates, wellCount: newWellCount });
    setSelectedWellIds((curr) =>
      curr.map((id) => idMap.get(id) ?? id),
    );
    setAnchorWellId((prev) => (prev ? (idMap.get(prev) ?? prev) : prev));
  }

  function handleWellClick(plateId: string, wellName: string, shiftKey: boolean) {
    const id = `${plateId}:${wellName}`;
    if (!isEditMode || !shiftKey || !anchorWellId) {
      setAnchorWellId(id);
      setSelectedWellIds((curr) =>
        curr.includes(id) ? curr.filter((e) => e !== id) : [...curr, id],
      );
      return;
    }
    // Shift+click: rectangular range selection
    const colonIdx = anchorWellId.indexOf(":");
    const anchorPlate = anchorWellId.slice(0, colonIdx);
    const anchorWell = anchorWellId.slice(colonIdx + 1);
    if (anchorPlate !== plateId) {
      setAnchorWellId(id);
      setSelectedWellIds((curr) =>
        curr.includes(id) ? curr.filter((e) => e !== id) : [...curr, id],
      );
      return;
    }
    const plate = renderedPlates.find((p) => p.plateId === plateId);
    if (!plate) return;
    const rangeIds = getRectRange(plate, anchorWell, wellName);
    setSelectedWellIds((curr) => {
      const existing = new Set(curr);
      rangeIds.forEach((rid) => existing.add(rid));
      return Array.from(existing);
    });
  }

  // Helper: get all well IDs in the rectangular grid range between two well names on same plate
  function getRectRange(plate: (typeof renderedPlates)[number], wellA: string, wellB: string): string[] {
    const ap = wellA.match(/^([A-Za-z]+)(\d+)$/);
    const bp = wellB.match(/^([A-Za-z]+)(\d+)$/);
    if (!ap || !bp) return [];
    const aRowIdx = plate.rowLabels.indexOf(ap[1].toUpperCase());
    const aColIdx = plate.columnLabels.indexOf(parseInt(ap[2], 10));
    const bRowIdx = plate.rowLabels.indexOf(bp[1].toUpperCase());
    const bColIdx = plate.columnLabels.indexOf(parseInt(bp[2], 10));
    if (aRowIdx === -1 || bRowIdx === -1) return [];
    const minRow = Math.min(aRowIdx, bRowIdx);
    const maxRow = Math.max(aRowIdx, bRowIdx);
    const minCol = Math.min(aColIdx, bColIdx);
    const maxCol = Math.max(aColIdx, bColIdx);
    const ids: string[] = [];
    for (let r = minRow; r <= maxRow; r++) {
      for (let c = minCol; c <= maxCol; c++) {
        ids.push(`${plate.plateId}:${formatWellId(plate.rowLabels[r], plate.columnLabels[c])}`);
      }
    }
    return ids;
  }

  function handleWellPointerDown(plateId: string, wellName: string, shiftKey: boolean, altKey: boolean, selection: string[]) {
    if (showOriginalLocal) return;
    const id = `${plateId}:${wellName}`;
    isPointerDownRef.current = true;
    dragAnchorIdRef.current = id;
    dragShiftRef.current = shiftKey;
    dragDeselectRef.current = altKey;
    dragBaseSelectionRef.current = selection;
    setAnchorWellId(id);
    if (shiftKey && anchorWellId) {
      // Shift+pointerdown: add rectangular range to selection
      const colonIdx = anchorWellId.indexOf(":");
      const anchorPlate = anchorWellId.slice(0, colonIdx);
      if (anchorPlate === plateId) {
        const plate = renderedPlates.find((p) => p.plateId === plateId);
        if (plate) {
          const anchorWell = anchorWellId.slice(colonIdx + 1);
          const rangeIds = getRectRange(plate, anchorWell, wellName);
          setSelectedWellIds((curr) => {
            const existing = new Set(curr);
            rangeIds.forEach((rid) => existing.add(rid));
            return Array.from(existing);
          });
          return;
        }
      }
    }
    if (altKey) {
      // Alt+pointerdown: deselect this well
      setSelectedWellIds((curr) => curr.filter((e) => e !== id));
      return;
    }
    // Normal pointerdown: toggle this well
    setSelectedWellIds((curr) =>
      curr.includes(id) ? curr.filter((e) => e !== id) : [...curr, id],
    );
  }

  function handleWellPointerEnter(plateId: string, wellName: string) {
    if (!isPointerDownRef.current || !dragAnchorIdRef.current || showOriginalLocal) return;
    // Only act when shift (add region) or alt (remove region) is held.
    if (!dragShiftRef.current && !dragDeselectRef.current) return;
    const colonIdx = dragAnchorIdRef.current.indexOf(":");
    const anchorPlate = dragAnchorIdRef.current.slice(0, colonIdx);
    if (anchorPlate !== plateId) return;
    const anchorWell = dragAnchorIdRef.current.slice(colonIdx + 1);
    const plate = renderedPlates.find((p) => p.plateId === plateId);
    if (!plate) return;
    const rangeIds = getRectRange(plate, anchorWell, wellName);
    const rangeSet = new Set(rangeIds);
    if (dragDeselectRef.current) {
      // Subtractive: remove range from base selection
      const base = new Set(dragBaseSelectionRef.current);
      rangeSet.forEach((id) => base.delete(id));
      setSelectedWellIds(Array.from(base));
    } else {
      // Additive: merge base selection with new range
      const base = new Set(dragBaseSelectionRef.current);
      rangeSet.forEach((id) => base.add(id));
      setSelectedWellIds(Array.from(base));
    }
  }

  function getCompoundWellIds(compound: string): Set<string> {
    const ids = new Set<string>();
    renderedPlates.forEach((plate) => {
      plate.allWells.forEach((well) => {
        if (well.compound === compound && well.isFilled) ids.add(`${well.plateId}:${well.well}`);
      });
    });
    return ids;
  }

  function getEmptyWellIds(): Set<string> {
    const ids = new Set<string>();
    renderedPlates.forEach((plate) => {
      plate.allWells.forEach((well) => {
        if (!well.isFilled) ids.add(`${well.plateId}:${well.well}`);
      });
    });
    return ids;
  }

  function getConcWellIds(compound: string, concLabel: string): Set<string> {
    const ids = new Set<string>();
    renderedPlates.forEach((plate) => {
      plate.allWells.forEach((well) => {
        if (well.compound === compound && well.isFilled) {
          const wLabel = well.concentration === null ? "No concentration" : String(well.concentration);
          if (wLabel === concLabel) ids.add(`${well.plateId}:${well.well}`);
        }
      });
    });
    return ids;
  }

  function toggleHighlight(ids: Set<string>) {
    const alreadyHighlighted = ids.size > 0 && [...ids].every((id) => highlightedWellIds.has(id)) && highlightedWellIds.size === ids.size;
    setHighlightedWellIds(alreadyHighlighted ? new Set() : ids);
  }

  // ── Export helpers ─────────────────────────────────────────────────────────

  function buildExportSpec() {
    return {
      title,
      plates: renderedPlates.map((p) => ({
        plateId: p.plateId,
        rowLabels: p.rowLabels,
        columnLabels: p.columnLabels,
        allWells: p.allWells,
      })),
      wellColorLookup,
      compoundColorLookup,
      legendGroups,
      totalEmptyCount,
      plateDef,
      concentrationUnit: concentrationUnit ?? "µM",
      totalWellCount: preview.wellCount,
      plateCount: preview.plateCount,
    };
  }

  return (
    <section className="plate-grid-panel">
      <div className="plate-viewer-card panel-surface">
      <div className="plate-grid-header">
        <div>
          <p className="section-kicker">Visualization</p>
          <h2>{title}</h2>
        </div>
        <div className="plate-grid-summary">
          <span>{preview.plateCount} plate{preview.plateCount === 1 ? "" : "s"}</span>
          <span>{preview.wellCount} assigned wells</span>
        </div>
      </div>

      {children}

      {isEditMode && (
        <div className="edit-mode-toolbar">
          <div className="edit-toolbar-left">
            <button
              type="button"
              className="toolbar-btn"
              disabled={!undoStack.length}
              onClick={undoEdit}
              title="Undo (⌘Z)"
            >
              ↩ Undo <kbd>⌘Z</kbd>
            </button>
            <button
              type="button"
              className="toolbar-btn"
              disabled={!redoStack.length}
              onClick={redoEdit}
              title="Redo (⌘⇧Z)"
            >
              Redo ↪ <kbd>⌘⇧Z</kbd>
            </button>
            <button
              type="button"
              className={`toolbar-btn${showOriginalLocal ? " is-active" : ""}`}
              onClick={() => setShowOriginalLocal((v) => !v)}
              title="Toggle between edited and original layout"
            >
              {showOriginalLocal ? "Editing view" : "Compare original"}
            </button>
          </div>
          <div className="edit-toolbar-right">
            <button type="button" className="toolbar-btn is-revert" onClick={onRevertAll}>
              Revert all
            </button>
            <button type="button" className="toolbar-btn is-save" onClick={onSaveEdits}>
              Save edits
            </button>
          </div>
        </div>
      )}

      <div
        className="plate-grid-main"
        onPointerMove={(wellTooltipContent || showDefaultTooltip) ? (e) => { if (hoveredSingleWellId) setTooltipPos({ x: e.clientX, y: e.clientY }); } : undefined}
      >
        <div className="plate-viewer-column">
          <div className="plate-stage-meta">
            <span>{plateDef ? `${plateDef.label} (${plateDef.rows}×${plateDef.cols})` : "Target plate"}</span>
            <span>{preview.wellCount} assigned wells</span>
            <span>{selectedWells.length} selected</span>
          </div>

          <div className="plate-grid-stack">
            {renderedPlates.map((plate) => (
              <article className={`plate-card${isEditMode ? " is-edit-mode" : ""}`} key={plate.plateId}>
                <header className="plate-card-header">
                  <h3>{plate.plateId}</h3>
                  <span>{formatWellCount(plate.wells.length)}</span>
                </header>

                <div className="plate-grid-scroll">
                  <div
                    className="plate-grid"
                    style={{
                      gridTemplateColumns: `${plate.columnLabels.length >= 24 ? "22px" : "30px"} repeat(${plate.columnLabels.length}, minmax(0, 1fr))`,
                    }}
                  >
                    <div className="plate-grid-corner" />
                    {plate.columnLabels.map((column) => (
                      <div className="plate-grid-label" key={`${plate.plateId}-column-${column}`}>
                        {column}
                      </div>
                    ))}

                    {plate.rowLabels.map((rowLabel) => (
                      <Fragment key={`${plate.plateId}-row-${rowLabel}`}>
                        <div className="plate-grid-label">{rowLabel}</div>
                        {plate.columnLabels.map((column) => {
                          const wellName = formatWellId(rowLabel, column);
                          const well = plate.wellLookup.get(wellName);
                          const wellId = `${plate.plateId}:${wellName}`;
                          const isSelected = selectedWellIds.includes(wellId);
                          const isConcHovered = hoveredWellIds.has(wellId);
                          const isWellHovered = hoveredSingleWellId === wellId;
                          const isDimmed = highlightedWellIds.size > 0 && !highlightedWellIds.has(wellId);
                          const isHighlighted = highlightedWellIds.size > 0 && highlightedWellIds.has(wellId);
                          const isExcluded = excludedWells?.has(wellId) ?? false;

                          return (
                            <button
                              type="button"
                              key={`${plate.plateId}-${wellName}`}
                              className={[
                                "plate-well",
                                well?.isFilled ? "is-filled" : "is-empty",
                                isSelected ? "is-selected" : "",
                                isConcHovered ? "is-conc-hovered" : "",
                                isWellHovered ? "is-well-hovered" : "",
                                isDimmed ? "is-dimmed" : "",
                                isHighlighted ? "is-highlighted" : "",
                                isEditMode && !showOriginalLocal ? "is-editable" : "",
                                isExcluded ? "is-excluded" : "",
                              ]
                                .filter(Boolean)
                                .join(" ")}
                              style={
                                well?.isFilled
                                  ? {
                                      background:
                                        wellColorLookup
                                          .get(well.compound ?? "")
                                          ?.get(well.concentration === null ? "No concentration" : String(well.concentration)) ??
                                        DMSO_COLOR,
                                    }
                                  : undefined
                              }
                              title={
                                (wellTooltipContent || showDefaultTooltip)
                                  ? undefined
                                  : well?.isFilled
                                  ? `${well.well}: ${well.compound}${well.concentration !== null ? ` at ${well.concentration} ${concentrationUnit}` : ""}`
                                  : `${wellName}: empty`
                              }
                              onPointerDown={(e) => {
                                if (!isEditMode || showOriginalLocal) return;
                                e.preventDefault();
                                handleWellPointerDown(plate.plateId, wellName, e.shiftKey, e.altKey, selectedWellIds);
                              }}
                              onPointerEnter={(e) => {
                                if (isEditMode) handleWellPointerEnter(plate.plateId, wellName);
                                setHoveredSingleWellId(wellId);
                                if (wellTooltipContent || showDefaultTooltip) setTooltipPos({ x: e.clientX, y: e.clientY });
                              }}
                              onPointerLeave={() => { setHoveredSingleWellId(null); setTooltipPos(null); }}
                              onClick={(e) => {
                                if (isEditMode || showOriginalLocal) return;
                                handleWellClick(plate.plateId, wellName, e.shiftKey);
                              }}
                            >
                              {well?.isFilled ? null : (
                                <span className="plate-well-dot" aria-hidden="true" />
                              )}
                            </button>
                          );
                        })}
                      </Fragment>
                    ))}
                  </div>
                </div>
              </article>
            ))}
          </div>

        </div>

        <aside className="plate-details-column">
          <div className="details-panel-scroll">              {isEditMode && (
                <div className="edit-actions-panel">
                  <div className="edit-actions-header">
                    <span className="edit-actions-title">Edit wells</span>
                    {selectedWellIds.length > 0 && (
                      <span className="edit-sel-count">{selectedWellIds.length} selected</span>
                    )}
                  </div>
                  {selectedWellIds.length === 0 ? (
                    <div className="edit-empty-state">
                      <div className="edit-shortcut-section">
                        <span className="edit-shortcut-section-label">Select</span>
                        <div className="edit-shortcut-list">
                          <div className="edit-shortcut-row"><kbd className="edit-kbd">Click</kbd><span>single well</span></div>
                          <div className="edit-shortcut-row"><kbd className="edit-kbd">⇧ Drag</kbd><span>add region to selection</span></div>
                          <div className="edit-shortcut-row"><kbd className="edit-kbd">⌥ Drag</kbd><span>remove region from selection</span></div>
                        </div>
                      </div>
                      <div className="edit-shortcut-section">
                        <span className="edit-shortcut-section-label">Actions</span>
                        <div className="edit-shortcut-list">
                          <div className="edit-shortcut-row"><kbd className="edit-kbd">⌘A</kbd><span>all filled</span></div>
                          <div className="edit-shortcut-row"><kbd className="edit-kbd">⌘⇧A</kbd><span>all wells</span></div>
                          <div className="edit-shortcut-row"><kbd className="edit-kbd">⌘D</kbd><span>deselect</span></div>
                          <div className="edit-shortcut-row"><kbd className="edit-kbd">⌘C</kbd><span>copy selected</span></div>
                          <div className="edit-shortcut-row"><kbd className="edit-kbd">⌘V</kbd>{clipboard ? <span className="edit-clipboard-hint">{clipboard.length} well{clipboard.length > 1 ? "s" : ""} ready to paste</span> : <span>paste</span>}</div>
                          <div className="edit-shortcut-row"><kbd className="edit-kbd">Del</kbd><span>clear selected</span></div>
                          <div className="edit-shortcut-row"><kbd className="edit-kbd">⌘Z</kbd><span>undo</span></div>
                        </div>
                      </div>
                    </div>
                  ) : pasteConflict ? (
                    <div className="edit-conflict-panel">
                      <p className="edit-conflict-msg">
                        ⚠ {pasteConflict.conflictWells.join(", ")} {pasteConflict.conflictCount > 1 ? "are" : "is"} already filled. What would you like to do?
                      </p>
                      <div className="edit-conflict-btns">
                        <button type="button" className="edit-conflict-btn is-skip" onClick={() => commitPaste(true)}>
                          Skip conflicts
                        </button>
                        <button type="button" className="edit-conflict-btn is-overwrite" onClick={() => commitPaste(false)}>
                          Overwrite all
                        </button>
                        <button type="button" className="edit-conflict-btn is-cancel" onClick={() => setPasteConflict(null)}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : assignConflict ? (
                    <div className="edit-conflict-panel">
                      <p className="edit-conflict-msg">
                        {assignConflict.filledIds.length} selected well{assignConflict.filledIds.length > 1 ? "s are" : " is"} already assigned. What would you like to do?
                      </p>
                      <div className="edit-conflict-btns">
                        <button type="button" className="edit-conflict-btn is-skip" onClick={() => { setAssignConflict(null); doAssign(true); }}>
                          Skip assigned
                        </button>
                        <button type="button" className="edit-conflict-btn is-overwrite" onClick={() => { setAssignConflict(null); doAssign(false); }}>
                          Overwrite all
                        </button>
                        <button type="button" className="edit-conflict-btn is-cancel" onClick={() => setAssignConflict(null)}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="edit-actions-body">
                      <button
                        type="button"
                        className="edit-clear-btn"
                        onClick={clearSelectedWells}
                      >
                        Clear {selectedWellIds.length} well{selectedWellIds.length > 1 ? "s" : ""}
                      </button>
                      <div className="edit-assign-fields">
                        <div className="edit-field-group">
                          <label className="edit-field-label">Compound</label>
                          <EditCombobox
                            value={editCompound}
                            onChange={(v) => { setEditCompound(v); setEditConc(""); }}
                            onClear={() => { setEditCompound(""); setEditConc(""); }}
                            options={legendGroups.map((g) => ({ label: g.compound, value: g.compound }))}
                            placeholder="Type or pick existing…"
                          />
                        </div>
                        <div className="edit-field-group">
                          <label className="edit-field-label">
                            Concentration <span className="edit-field-unit">({concentrationUnit})</span>
                          </label>
                          <EditCombobox
                            value={editConc}
                            onChange={setEditConc}
                            onClear={() => setEditConc("")}
                            options={(legendGroups.find((g) => g.compound === editCompound)?.concentrations ?? []).map((c) => ({
                              label: c.numeric !== null ? `${c.numeric} ${concentrationUnit}` : "No concentration",
                              value: c.numeric !== null ? String(c.numeric) : "0",
                            }))}
                            placeholder="e.g. 10 or 0.5…"
                          />
                        </div>
                        <button
                          type="button"
                          className="edit-assign-btn"
                          disabled={!editCompound.trim() || !editConc.trim()}
                          onClick={assignCompoundToSelected}
                        >
                          Assign
                        </button>
                      </div>
                    </div>
                  )}
                  <div className="edit-shift-row">
                    <span className="edit-shift-label">
                      {selectedWellIds.filter((id) => selectionLookup.get(id)?.isFilled).length > 0
                        ? "Move selected"
                        : "Shift all filled"}
                    </span>
                    <div className="edit-shift-btns">
                      <button type="button" className="edit-shift-btn" title="Up (↑)" onClick={() => shiftLayoutBy(-1, 0)}>↑</button>
                      <button type="button" className="edit-shift-btn" title="Down (↓)" onClick={() => shiftLayoutBy(1, 0)}>↓</button>
                      <button type="button" className="edit-shift-btn" title="Left (←)" onClick={() => shiftLayoutBy(0, -1)}>←</button>
                      <button type="button" className="edit-shift-btn" title="Right (→)" onClick={() => shiftLayoutBy(0, 1)}>→</button>
                    </div>
                  </div>
                  {shiftWarning && <p className="edit-shift-warning">⚠ {shiftWarning}</p>}
                </div>
              )}            {legendGroups.map((group) => {
              const color = compoundColorLookup.get(group.compound) ?? DMSO_COLOR;
              const selectedForCompound = selectedWellsByCompound.get(group.compound) ?? [];
              return (
                <article className="info-group-card" key={group.compound}>
                  <div className="info-group-bar" style={{ background: color }} />
                  <div className="info-group-body">
                    <div className="info-group-header">
                      <span className="info-group-name">{group.compound}</span>
                      <div className="info-group-header-btns">
                        <span className="info-group-tally">{group.count}W total</span>
                        <button
                          type="button"
                          className="info-action-btn"
                          title="Highlight all wells for this compound"
                          onMouseEnter={() => setHoveredConcKey(`${group.compound}::__all__`)}
                          onMouseLeave={() => setHoveredConcKey(null)}
                          onClick={() => toggleHighlight(getCompoundWellIds(group.compound))}
                        >
                          Highlight all
                        </button>
                      </div>
                    </div>
                    {group.concentrations.map((conc) => {
                      const pillsForConc = selectedForCompound.filter((w) => {
                        const wLabel = w.concentration === null ? "No concentration" : String(w.concentration);
                        return wLabel === conc.label;
                      });
                      return (
                        <div className="info-conc-block" key={conc.label}>
                          <div className="info-conc-meta">
                            <span
                              className="info-conc-swatch"
                              style={{ background: wellColorLookup.get(group.compound)?.get(conc.label) ?? "transparent" }}
                            />
                            <span className="info-conc-label">{formatConcentration(conc.numeric, concentrationUnit)}</span>
                            <span className="info-conc-tally">{conc.count}W</span>
                            <button
                              type="button"
                              className="info-action-btn"
                              onMouseEnter={() => setHoveredConcKey(`${group.compound}::${conc.label}`)}
                              onMouseLeave={() => setHoveredConcKey(null)}
                              onClick={() => toggleHighlight(getConcWellIds(group.compound, conc.label))}
                            >
                              Highlight all
                            </button>
                          </div>
                          {pillsForConc.length > 0 && (
                            <div className="info-wells-row">
                              {pillsForConc.map((well) => (
                                <button
                                  type="button"
                                  key={`${well.plateId}-${well.well}`}
                                  className="info-well-pill"
                                  style={{ '--pill-color': color } as React.CSSProperties}
                                  title={well.well}
                                  onMouseEnter={() => setHoveredSingleWellId(`${well.plateId}:${well.well}`)}
                                  onMouseLeave={() => setHoveredSingleWellId(null)}
                                >
                                  {well.well}
                                </button>
                              ))}
                            </div>
                          )}
                          {concBlockExtras && (() => {
                            const extras = concBlockExtras(group.compound, conc.label);
                            return extras ? <div className="info-conc-extras">{extras}</div> : null;
                          })()}
                        </div>
                      );
                    })}
                  </div>
                </article>
              );
            })}
            {totalEmptyCount > 0 && (
              <article className="info-group-card" key="__empty__">
                <div className="info-group-bar" style={{ background: EMPTY_COLOR }} />
                <div className="info-group-body">
                  <div className="info-group-header">
                    <span className="info-group-name">Empty wells</span>
                    <div className="info-group-header-btns">
                      <span className="info-group-tally">{totalEmptyCount}W total</span>
                      <button
                        type="button"
                        className="info-action-btn"
                        title="Highlight all empty wells"
                        onMouseEnter={() => setHoveredConcKey("__empty__")}
                        onMouseLeave={() => setHoveredConcKey(null)}
                        onClick={() => toggleHighlight(getEmptyWellIds())}
                      >
                        Highlight all
                      </button>
                    </div>
                  </div>
                  {selectedEmptyWells.length > 0 && (
                    <div className="info-wells-row">
                      {selectedEmptyWells.map((well) => (
                        <button
                          type="button"
                          key={`${well.plateId}-${well.well}`}
                          className="info-well-pill"
                          style={{ '--pill-color': EMPTY_COLOR } as React.CSSProperties}
                          title={well.well}
                          onMouseEnter={() => setHoveredSingleWellId(`${well.plateId}:${well.well}`)}
                          onMouseLeave={() => setHoveredSingleWellId(null)}
                        >
                          {well.well}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </article>
            )}
          </div>
        </aside>
      </div>

      <section className="legend-panel legend-section">
        <div className="legend-heading">
          <p className="section-kicker">Legend</p>
          <h3>Compounds &amp; concentrations</h3>
        </div>
        <div className="legend-strip">
          {legendGroups.map((group) => {
            const color = compoundColorLookup.get(group.compound) ?? DMSO_COLOR;
            return (
              <article className="legend-compound-card" key={group.compound}>
                <div className="legend-compound-bar" style={{ background: color }} />
                <div className="legend-compound-body">
                  <div className="legend-compound-header">
                    <span className="legend-compound-name">{group.compound}</span>
                    <span className="legend-compound-count">{group.count}w</span>
                  </div>
                  <div className="legend-doses">
                    {group.concentrations.map((concentration) => (
                      <div className="legend-dose" key={`${group.compound}-${concentration.label}`}>
                        <span
                          className="legend-dose-swatch"
                          style={{ background: wellColorLookup.get(group.compound)?.get(concentration.label) ?? "transparent" }}
                        />
                        <span className="legend-dose-label">{formatConcentration(concentration.numeric, concentrationUnit)}</span>
                        <span className="legend-dose-count">{concentration.count}w</span>
                      </div>
                    ))}
                  </div>
                </div>
              </article>
            );
          })}
          {totalEmptyCount > 0 && (
            <article className="legend-compound-card" key="__empty__">
              <div className="legend-compound-bar" style={{ background: EMPTY_COLOR }} />
              <div className="legend-compound-body">
                <div className="legend-compound-header">
                  <span className="legend-compound-name">Empty</span>
                  <span className="legend-compound-count">{totalEmptyCount}w</span>
                </div>
              </div>
            </article>
          )}
        </div>
      </section>
      {(() => {
        if (!hoveredSingleWellId || !tooltipPos) return null;
        let content: ReactNode | null = null;
        if (wellTooltipContent) {
          content = wellTooltipContent(hoveredSingleWellId);
        } else if (showDefaultTooltip) {
          const w = selectionLookup.get(hoveredSingleWellId);
          const wellName = hoveredSingleWellId.slice(hoveredSingleWellId.indexOf(":") + 1);
          if (w?.isFilled) {
            content = (
              <>
                <div className="well-tt-name">{wellName}</div>
                <div className="well-tt-compound">{w.compound}</div>
                {w.concentration !== null && (
                  <div className="well-tt-stock">{w.concentration} {concentrationUnit}</div>
                )}
              </>
            );
          } else {
            content = (
              <>
                <div className="well-tt-name">{wellName}</div>
                <div className="well-tt-stock">Empty well</div>
              </>
            );
          }
        }
        if (!content) return null;
        return (
          <div
            className="well-tooltip-panel"
            style={{ left: tooltipPos.x + 16, top: tooltipPos.y + 8 }}
          >
            {content}
          </div>
        );
      })()}

      <div className="plate-export-actions" data-export-ignore="true">
        <p className="section-kicker">Export</p>
        <div className="plate-export-btns">
          <button
            type="button"
            className="plate-export-btn"
            onClick={() => downloadPlateCsv(preview, buildPlateExportFilename(resolvedExportProjectDetails, exportScope, "csv"))}
            title="Download layout as CSV (re-uploadable format)"
          >
            <span className="plate-export-icon">⬇</span> CSV
          </button>
          <button
            type="button"
            className="plate-export-btn"
            onClick={() => downloadPlateSvg(buildExportSpec(), buildPlateExportFilename(resolvedExportProjectDetails, exportScope, "svg"))}
            title="Download plate figure as SVG"
          >
            <span className="plate-export-icon">⬇</span> SVG
          </button>
          <button
            type="button"
            className="plate-export-btn"
            onClick={() => downloadPlatePng(buildExportSpec(), buildPlateExportFilename(resolvedExportProjectDetails, exportScope, "png"))}
            title="Download plate figure as PNG (2×)"
          >
            <span className="plate-export-icon">⬇</span> PNG
          </button>
        </div>
      </div>

      </div>
    </section>
  );
}
