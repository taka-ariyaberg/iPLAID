/**
 * DesignPlateViewer — interactive well-region selector (Context 1).
 *
 * Selection interactions:
 *   Click               — toggle single well (clears others unless Cmd held)
 *   Cmd+Click           — toggle single well without clearing others
 *   Shift+Click         — extend rectangular range from anchor
 *   Shift+Drag          — rubber-band ADD to usable region
 *   Opt+Click           — deselect single well
 *   Opt+Drag            — rubber-band REMOVE from usable region
 *   Cmd+A               — select all currently usable wells (respects empty_edge)
 *   Cmd+D               — deselect all selected wells
 *   Cmd+Shift+A         — select every well (full plate)
 *   Cmd+Shift+D         — deselect every well
 *
 * The selected set drives `empty_edge` (largest uniform symmetric edge that
 * fits inside the bounding box of the selection).  The value is reported via
 * `onEmptyEdgeChange`.  When a solved layout is provided it is displayed in
 * read-only mode using the existing colour system.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { LayoutPreview } from "../../types";
import { getCompoundColor, getConcColor, DMSO_COLOR } from "../../utils/colorUtils";

// Accent colour for selection glow (matches iCELL cyan)
const ACCENT = "#00b8ff";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type WellCoord = { row: number; col: number };

interface DesignPlateViewerProps {
  rows: number;
  cols: number;
  emptyEdge: number;
  onEmptyEdgeChange: (edge: number) => void;
  /** If provided, display solved layout (read-only) */
  solvedPreview?: LayoutPreview | null;
  /** Total wells needed (shown in badge) */
  wellsNeeded: number;
}

// ---------------------------------------------------------------------------
// Row labels: A, B, C … Z, AA, AB …
// ---------------------------------------------------------------------------

function rowLabel(r: number): string {
  const labels: string[] = [];
  let n = r;
  do {
    labels.unshift(String.fromCharCode(65 + (n % 26)));
    n = Math.floor(n / 26) - 1;
  } while (n >= 0);
  return labels.join("");
}

function wellName(r: number, c: number): string {
  return `${rowLabel(r)}${c + 1}`;
}

// ---------------------------------------------------------------------------
// Geometry helpers
// ---------------------------------------------------------------------------

function rectWells(r1: number, c1: number, r2: number, c2: number): Set<string> {
  const minR = Math.min(r1, r2);
  const maxR = Math.max(r1, r2);
  const minC = Math.min(c1, c2);
  const maxC = Math.max(c1, c2);
  const s = new Set<string>();
  for (let r = minR; r <= maxR; r++) {
    for (let c = minC; c <= maxC; c++) {
      s.add(`${r},${c}`);
    }
  }
  return s;
}

function edgeWells(rows: number, cols: number, edge: number): Set<string> {
  if (edge <= 0) return new Set();
  const s = new Set<string>();
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (r < edge || r >= rows - edge || c < edge || c >= cols - edge) {
        s.add(`${r},${c}`);
      }
    }
  }
  return s;
}

/** Compute symmetric empty_edge from a set of selected wells. */
function computeEdgeFromSelection(selected: Set<string>, rows: number, cols: number): number {
  if (selected.size === 0) return 0;
  let minR = rows, maxR = -1, minC = cols, maxC = -1;
  selected.forEach((key) => {
    const [r, c] = key.split(",").map(Number);
    if (r < minR) minR = r;
    if (r > maxR) maxR = r;
    if (c < minC) minC = c;
    if (c > maxC) maxC = c;
  });
  // edge = minimum distance from plate boundary
  const topEdge = minR;
  const botEdge = rows - 1 - maxR;
  const leftEdge = minC;
  const rightEdge = cols - 1 - maxC;
  return Math.min(topEdge, botEdge, leftEdge, rightEdge);
}

// ---------------------------------------------------------------------------
// Build initial selection from edge
// ---------------------------------------------------------------------------

function selectionFromEdge(rows: number, cols: number, edge: number): Set<string> {
  const s = new Set<string>();
  for (let r = edge; r < rows - edge; r++) {
    for (let c = edge; c < cols - edge; c++) {
      s.add(`${r},${c}`);
    }
  }
  return s;
}

// ---------------------------------------------------------------------------
// Colour helpers for solved layout display
// ---------------------------------------------------------------------------

function buildCompoundColorMap(preview: LayoutPreview): Map<string, string> {
  const compounds: string[] = [];
  preview.compoundSummary?.forEach((cs) => {
    if (!compounds.includes(cs.name)) compounds.push(cs.name);
  });
  const map = new Map<string, string>();
  compounds.forEach((name, i) => {
    map.set(name, getCompoundColor(i, compounds.length));
  });
  return map;
}

function wellColorFromPreview(
  wellKey: string,
  preview: LayoutPreview,
  colorMap: Map<string, string>
): string | null {
  for (const plate of preview.plates) {
    for (const w of plate.wells) {
      const r = w.rowLabel.charCodeAt(0) - 65;
      const c = w.column - 1;
      if (`${r},${c}` === wellKey) {
        if (!w.compound || w.compound === "DMSO") return DMSO_COLOR;
        const base = colorMap.get(w.compound) ?? "rgba(129,140,248,0.85)";
        const concVals = plate.wells
          .filter((ww) => ww.compound === w.compound)
          .map((ww) => ww.concentration ?? 0)
          .sort((a, b) => a - b);
        const rank = concVals.indexOf(w.concentration ?? 0);
        return getConcColor(base, rank, concVals.length);
      }
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DesignPlateViewer({
  rows,
  cols,
  emptyEdge,
  onEmptyEdgeChange,
  solvedPreview,
  wellsNeeded,
}: DesignPlateViewerProps) {
  // Selected wells = the region the user has drawn. Starts empty (nothing glowing).
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Zoom (0.5 – 2.0, same range as iCELL)
  const [zoom, setZoom] = useState(1);

  // Measure the wrapper so the plate fills it at zoom=1
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(600);
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setContainerWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Hover tooltip
  const [hoveredWell, setHoveredWell] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  // Keep a ref to the current emptyEdge so the dimension-change effect can
  // read it without adding it to the dependency array (which would cause it
  // to also fire when only the edge changes — that's handled separately below).
  const emptyEdgeRef = useRef(emptyEdge);
  emptyEdgeRef.current = emptyEdge;

  // When the plate dimensions change (plate-type switch), rebuild the selection
  // from whatever the current emptyEdge is.  This preserves the glow: if
  // emptyEdge is 0, selectionFromEdge returns ALL wells so they all glow.
  const lastComputedEdgeRef = useRef<number>(emptyEdge);
  useEffect(() => {
    const edge = emptyEdgeRef.current;
    const next = selectionFromEdge(rows, cols, edge);
    lastComputedEdgeRef.current = edge;
    setSelected(next);
    onEmptyEdgeChange(edge);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, cols]);

  // Sync selection when emptyEdge is changed externally (user typed a value).
  // We compare against the edge computed from the current selection to avoid
  // a feedback loop when the selection itself drives an edge update.
  useEffect(() => {
    if (emptyEdge === lastComputedEdgeRef.current) return; // came from our own selection change
    const next = selectionFromEdge(rows, cols, emptyEdge);
    lastComputedEdgeRef.current = emptyEdge;
    setSelected(next);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [emptyEdge]);

  // Mirror selected in a ref so global event handlers always read fresh state
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  // Drag state — hasMoved distinguishes a click from a drag
  const dragRef = useRef<{
    active: boolean;
    mode: "add" | "remove";
    anchor: WellCoord;
    hasMoved: boolean;
  } | null>(null);
  const [dragOverlay, setDragOverlay] = useState<Set<string>>(new Set());
  // Track current drag endpoint separately so pointer-capture works across cells
  const dragCurrentRef = useRef<WellCoord | null>(null);

  // Solved layout colour map (memoised)
  const colorMap = useMemo(
    () => (solvedPreview ? buildCompoundColorMap(solvedPreview) : new Map()),
    [solvedPreview]
  );

  // ---------------------------------------------------------------------------
  // Publish edge when selection changes
  // ---------------------------------------------------------------------------

  const publishEdge = useCallback(
    (next: Set<string>) => {
      const newEdge = computeEdgeFromSelection(next, rows, cols);
      onEmptyEdgeChange(newEdge);
    },
    [rows, cols, onEmptyEdgeChange]
  );

  const updateSelected = useCallback(
    (next: Set<string>) => {
      setSelected(next);
      const edge = computeEdgeFromSelection(next, rows, cols);
      lastComputedEdgeRef.current = edge; // mark as our own change so the emptyEdge effect ignores it
      publishEdge(next);
    },
    [publishEdge, rows, cols]
  );

  // ---------------------------------------------------------------------------
  // Keyboard shortcuts
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (solvedPreview) return;
    function onKey(e: KeyboardEvent) {
      // Let inputs handle their own Cmd+A / Cmd+D
      const target = e.target as HTMLElement;
      if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return;
      const cmd = e.metaKey || e.ctrlKey;
      if (!cmd) return;

      if (e.key === "a") {
        // Cmd+A — select all wells
        e.preventDefault();
        updateSelected(rectWells(0, 0, rows - 1, cols - 1));
      } else if (e.key === "d") {
        // Cmd+D — deselect all
        e.preventDefault();
        updateSelected(new Set());
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [rows, cols, solvedPreview, updateSelected]);

  // Global pointerup: commits the drag even when released outside the grid.
  // The individual-well onPointerUp handles the normal case; this catches
  // releases in gaps or outside the viewer entirely.
  useEffect(() => {
    if (solvedPreview) return;
    function onWindowPointerUp() {
      if (!dragRef.current?.active) return;
      const drag = dragRef.current;
      const last = dragCurrentRef.current ?? drag.anchor;
      const current = selectedRef.current;
      if (!drag.hasMoved) {
        const key = `${drag.anchor.row},${drag.anchor.col}`;
        const next = new Set(current);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        updateSelected(next);
      } else {
        const rect = rectWells(drag.anchor.row, drag.anchor.col, last.row, last.col);
        const next = new Set(current);
        if (drag.mode === "remove") {
          rect.forEach((k) => next.delete(k));
        } else {
          rect.forEach((k) => next.add(k));
        }
        updateSelected(next);
      }
      dragRef.current = null;
      dragCurrentRef.current = null;
      setDragOverlay(new Set());
    }
    window.addEventListener("pointerup", onWindowPointerUp);
    return () => window.removeEventListener("pointerup", onWindowPointerUp);
  }, [solvedPreview, updateSelected]);

  // ---------------------------------------------------------------------------
  // Well interaction handlers
  // ---------------------------------------------------------------------------
  //
  //   Click (no movement)   → toggle single well
  //   Drag                  → ADD the dragged rectangle to existing selection
  //   Opt+Drag              → REMOVE the dragged rectangle from existing selection
  //   Cmd+A                 → select all wells
  //   Cmd+D                 → deselect all wells

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>, r: number, c: number) => {
      if (solvedPreview) return;
      e.preventDefault();
      // NOTE: do NOT call setPointerCapture here — that would lock all pointer
      // events to the first well and break drag-over-multiple-wells behaviour.
      const mode: "add" | "remove" = e.altKey ? "remove" : "add";
      dragRef.current = { active: true, mode, anchor: { row: r, col: c }, hasMoved: false };
      dragCurrentRef.current = { row: r, col: c };
      setDragOverlay(new Set([`${r},${c}`]));
    },
    [solvedPreview]
  );

  const handlePointerMove = useCallback(
    (_e: React.PointerEvent<HTMLDivElement>, r: number, c: number) => {
      if (!dragRef.current?.active) return;
      const drag = dragRef.current;
      const prev = dragCurrentRef.current;
      // Mark as moved only when we enter a different cell
      if (prev && (prev.row !== r || prev.col !== c)) {
        drag.hasMoved = true;
      }
      dragCurrentRef.current = { row: r, col: c };
      const rect = rectWells(drag.anchor.row, drag.anchor.col, r, c);
      setDragOverlay(rect);
    },
    []
  );

  const handlePointerUp = useCallback(
    (_e: React.PointerEvent<HTMLDivElement>, r: number, c: number) => {
      if (!dragRef.current?.active) return;
      const drag = dragRef.current;

      if (!drag.hasMoved) {
        // ── Click: toggle the single well ──────────────────────────────────
        const key = `${drag.anchor.row},${drag.anchor.col}`;
        const next = new Set(selected);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        updateSelected(next);
      } else {
        // ── Drag: operate on the bounding rectangle ─────────────────────
        const rect = rectWells(drag.anchor.row, drag.anchor.col, r, c);
        const next = new Set(selected);
        if (drag.mode === "remove") {
          rect.forEach((k) => next.delete(k));
        } else {
          rect.forEach((k) => next.add(k));
        }
        updateSelected(next);
      }

      dragRef.current = null;
      dragCurrentRef.current = null;
      setDragOverlay(new Set());
    },
    [selected, updateSelected]
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const usableCount = selected.size;

  // Auto-fit: compute base well size so all columns fit in the container at zoom=1
  // Account for header col (≈24px) + gaps between cols + 24px padding on each side
  const HEADER = 24;
  const GAP = 4;
  const PADDING = 24 * 2;
  const availableForWells = containerWidth - HEADER - GAP * cols - PADDING;
  const autoBase = Math.max(6, Math.min(28, Math.floor(availableForWells / cols)));
  const wellSize = Math.round(autoBase * zoom);
  const headerSize = Math.round(HEADER * zoom);
  const gap = GAP;
  const labelFontSize = Math.max(8, Math.min(11, wellSize * 0.38));

  return (
    <div className="design-plate-viewer" ref={containerRef}>
      {/* Controls bar */}
      <div className="design-plate-controls">
        <div className="design-zoom-controls">
          <button
            type="button"
            className="design-zoom-btn"
            onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.1).toFixed(1)))}
          >
            −
          </button>
          <span className="design-zoom-level">{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            className="design-zoom-btn"
            onClick={() => setZoom((z) => Math.min(2, +(z + 0.1).toFixed(1)))}
          >
            +
          </button>
        </div>
        <div className="design-plate-info">
          {rows}×{cols}&nbsp;·&nbsp;{selected.size} selected
          {selected.size > 0 && <span style={{ marginLeft: 6 }}>· edge {emptyEdge}</span>}
          {wellsNeeded > 0 && (
            <span
              style={{ marginLeft: 8, color: wellsNeeded > usableCount ? "var(--icell-danger)" : "var(--icell-success)" }}
            >
              · {wellsNeeded} assigned
            </span>
          )}
        </div>
      </div>

      {/* Grid wrapper */}
      <div className="design-plate-grid-wrapper">
        <div
          className="design-plate-grid"
          style={{ gridTemplateColumns: `${headerSize}px repeat(${cols}, ${wellSize}px)`, gap }}
        >
          {/* Corner */}
          <div className="design-grid-header design-corner-cell" />

          {/* Column headers */}
          {Array.from({ length: cols }, (_, c) => (
            <div
              key={`col-${c}`}
              className="design-grid-header design-col-label"
              style={{ fontSize: labelFontSize, width: wellSize }}
            >
              {c + 1}
            </div>
          ))}

          {/* Rows */}
          {Array.from({ length: rows }, (_, r) => (
            <React.Fragment key={r}>
              <div
                className="design-grid-header design-row-label"
                style={{ fontSize: labelFontSize, height: wellSize }}
              >
                {rowLabel(r)}
              </div>

              {Array.from({ length: cols }, (_, c) => {
                const key = `${r},${c}`;
                // In solved mode there is no selection glow — the compound colours speak for themselves.
                const isSelected = !solvedPreview && selected.has(key);
                const inOverlay = dragOverlay.has(key);
                const drag = dragRef.current;
                const overlayMode = drag?.mode ?? "add";

                // Colour in solved mode
                let solvedColor: string | null = null;
                if (solvedPreview) {
                  solvedColor = wellColorFromPreview(key, solvedPreview, colorMap);
                }

                // Background
                let bg = "rgba(255,255,255,0.04)";
                if (solvedColor) {
                  bg = solvedColor;
                } else if (inOverlay) {
                  bg = overlayMode === "remove"
                    ? "rgba(255,59,85,0.30)"
                    : `${ACCENT}55`;
                } else if (isSelected) {
                  bg = `${ACCENT}26`;
                }

                // Box shadow glow
                let boxShadow = "none";
                let borderColor = "rgba(255,255,255,0.12)";
                let borderWidth = 1;
                if (inOverlay) {
                  const col = overlayMode === "remove" ? "#ff3b55" : ACCENT;
                  boxShadow = `inset 0 0 6px ${col}66, 0 0 8px ${col}44`;
                  borderColor = col;
                } else if (isSelected) {
                  if (solvedColor) {
                    boxShadow = `inset 0 0 8px ${solvedColor}, 0 0 12px ${solvedColor}`;
                    borderColor = solvedColor;
                  } else {
                    boxShadow = `inset 0 0 8px ${ACCENT}99, 0 0 12px ${ACCENT}66`;
                    borderColor = ACCENT;
                  }
                  borderWidth = 2;
                }

                const wn = wellName(r, c);

                return (
                  <div
                    key={c}
                    className={`design-well${isSelected ? " design-well-selected" : ""}`}
                    style={{
                      width: wellSize,
                      height: wellSize,
                      minWidth: wellSize,
                      minHeight: wellSize,
                      borderRadius: 4,
                      background: bg,
                      border: `${borderWidth}px solid ${borderColor}`,
                      boxShadow,
                      transition: "box-shadow 0.1s ease-out, border-color 0.1s ease-out",
                      cursor: solvedPreview ? "default" : "pointer",
                      position: "relative",
                    }}
                    onPointerDown={(e) => handlePointerDown(e, r, c)}
                    onPointerMove={(e) => {
                      handlePointerMove(e, r, c);
                      setTooltipPos({ x: e.clientX + 16, y: e.clientY + 16 });
                    }}
                    onPointerUp={(e) => handlePointerUp(e, r, c)}
                    onMouseEnter={() => setHoveredWell(wn)}
                    onMouseMove={(e) => setTooltipPos({ x: e.clientX + 16, y: e.clientY + 16 })}
                    onMouseLeave={() => setHoveredWell(null)}
                  />
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Floating tooltip */}
      {hoveredWell && (
        <div
          className="design-well-tooltip"
          style={{ left: tooltipPos.x, top: tooltipPos.y }}
        >
          <div className="design-well-tooltip-title">{hoveredWell}</div>
          {solvedPreview
            ? (() => {
                const [rl, colStr] = [hoveredWell.replace(/\d+/, ""), hoveredWell.replace(/\D+/, "")];
                const r = rl.charCodeAt(0) - 65;
                const c = parseInt(colStr) - 1;
                const key = `${r},${c}`;
                for (const plate of solvedPreview.plates) {
                  for (const w of plate.wells) {
                    const wr = w.rowLabel.charCodeAt(0) - 65;
                    const wc = w.column - 1;
                    if (`${wr},${wc}` === key) {
                      return (
                        <>
                          <div className="design-well-tooltip-line">{w.compound ?? "Empty"}</div>
                          {w.concentration != null && (
                            <div className="design-well-tooltip-line">{w.concentration} µM</div>
                          )}
                        </>
                      );
                    }
                  }
                }
                return <div className="design-well-tooltip-line">Unassigned</div>;
              })()
            : (() => {
                const [rl, colStr] = [hoveredWell.replace(/\d+$/, ""), hoveredWell.replace(/^[A-Z]+/, "")];
                const r = rl.length === 1
                  ? rl.charCodeAt(0) - 65
                  : (rl.charCodeAt(0) - 64) * 26 + (rl.charCodeAt(1) - 65);
                const c = parseInt(colStr) - 1;
                const key = `${r},${c}`;
                const isSel = selected.has(key);
                return (
                  <div className="design-well-tooltip-line">
                    {isSel ? "Selected (available)" : "Unselected"}
                  </div>
                );
              })()
          }
        </div>
      )}
    </div>
  );
}
