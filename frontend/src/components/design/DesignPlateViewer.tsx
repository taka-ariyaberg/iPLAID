/**
 * DesignPlateViewer — read-only well-region display (Context 1).
 *
 * The usable wells are determined entirely by `emptyEdge` (supplied from the
 * external input field).  When a solved layout is provided it is displayed in
 * read-only mode using the existing colour system.
 */

import React, { useEffect, useMemo, useRef, useState } from "react";
import type { CompoundDef, ControlDef, LayoutPreview } from "../../types";
import { getConcColor, DMSO_COLOR, getStableCompoundColor } from "../../utils/colorUtils";
import { useWaitingTroll, TrollOverlay, TrollProgressBar } from "./WaitingTroll";
import type { WellAssignment } from "./WaitingTroll";

// Accent colour for selection glow (matches iCELL cyan)
const ACCENT = "#00b8ff";

interface DesignPlateViewerProps {
  rows: number;
  cols: number;
  emptyEdge: number;
  /** Compounds and controls — used to colour-fill wells in preview */
  compounds: CompoundDef[];
  controls: ControlDef[];
  /** If provided, display solved layout (read-only) */
  solvedPreview?: LayoutPreview | null;
  /** Total wells needed (shown in badge) */
  wellsNeeded: number;
  /** True while the solver is running — activates the WaitingTroll animation */
  isGenerating: boolean;
  /** Called when the troll animation reaches 100% — lets DesignPanel reveal the result */
  onTrollDone?: () => void;
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
// Build compound fill map
// ---------------------------------------------------------------------------

/**
 * Returns a map of well-key → colour for the first N usable wells,
 * filled left-to-right, top-to-bottom, in the order entries were added.
 * Compounds use getStableCompoundColor; controls use the DMSO amber.
 */
function buildFillMap(
  compounds: CompoundDef[],
  controls: ControlDef[],
  rows: number,
  cols: number,
  edge: number
): Map<string, string> {
  // Build an ordered list of (color, wellCount) segments
  const segments: Array<{ color: string; count: number }> = [];
  compounds.forEach((cmp, ci) => {
    const baseColor = getStableCompoundColor(ci);
    const total = cmp.conc_entries.length;
    cmp.conc_entries.forEach((entry, ri) => {
      const color = getConcColor(baseColor, ri, total);
      if (entry.replicates > 0) segments.push({ color, count: entry.replicates });
    });
  });
  controls.forEach((ctrl) => {
    const count = ctrl.conc_entries.reduce((s, e) => s + e.replicates, 0);
    if (count > 0) segments.push({ color: DMSO_COLOR, count });
  });

  const map = new Map<string, string>();
  // Walk usable wells in reading order
  let segIdx = 0;
  let remaining = segments[0]?.count ?? 0;
  for (let r = edge; r < rows - edge; r++) {
    for (let c = edge; c < cols - edge; c++) {
      while (segIdx < segments.length && remaining === 0) {
        segIdx++;
        remaining = segments[segIdx]?.count ?? 0;
      }
      const color = segIdx < segments.length
        ? segments[segIdx].color
        : null; // no token for empty wells
      if (color !== null) map.set(`${r},${c}`, color);
      if (segIdx < segments.length) remaining--;
    }
  }
  return map;
}

// ---------------------------------------------------------------------------
// Build selection from edge
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

/**
 * Returns the colour for a well in the solved preview.
 * Compound identity is looked up in the config compoundsList so that the
 * same stable index → getStableCompoundColor mapping used in buildFillMap
 * is reused here.  This guarantees visual consistency between config mode
 * and solved-view mode.
 */
function wellColorFromPreview(
  wellKey: string,
  preview: LayoutPreview,
  configCompounds: CompoundDef[]
): string | null {
  for (const plate of preview.plates) {
    for (const w of plate.wells) {
      const r = w.rowLabel.charCodeAt(0) - 65;
      const c = w.column - 1;
      if (`${r},${c}` === wellKey) {
        if (!w.compound || w.compound === "DMSO") return DMSO_COLOR;
        // Match by name to get the stable config index → same colour as config preview
        const ci = configCompounds.findIndex((cmp) => cmp.name === w.compound);
        return getStableCompoundColor(ci >= 0 ? ci : 0);
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
  compounds,
  controls,
  solvedPreview,
  wellsNeeded,
  isGenerating,
  onTrollDone,
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

  // Rebuild selection whenever dimensions or edge change.
  useEffect(() => {
    setSelected(selectionFromEdge(rows, cols, emptyEdge));
  }, [rows, cols, emptyEdge]);

  // Compound fill map — always computed so the troll can snapshot it
  const fillMap = useMemo(
    () => buildFillMap(compounds, controls, rows, cols, emptyEdge),
    [compounds, controls, rows, cols, emptyEdge]
  );

  // Flat assignment list derived from fillMap (stable reference for the hook)
  const fillAssignments = useMemo<WellAssignment[]>(
    () => Array.from(fillMap.entries()).map(([key, color]) => ({ key, color })),
    [fillMap]
  );

  // All usable positions — the full shuffle pool for the troll (includes empty wells)
  const allUsableKeys = useMemo<string[]>(() => {
    const keys: string[] = [];
    for (let r = emptyEdge; r < rows - emptyEdge; r++)
      for (let c = emptyEdge; c < cols - emptyEdge; c++)
        keys.push(`${r},${c}`);
    return keys;
  }, [rows, cols, emptyEdge]);

  // WaitingTroll: shuffles assigned-well tokens across the full usable pool while generating
  const { tokens, progress } = useWaitingTroll(isGenerating, fillAssignments, allUsableKeys, onTrollDone);

  // Active fill: nothing during generation (overlay handles it) or in solved mode
  const activeFillMap = !isGenerating && !solvedPreview ? fillMap : new Map<string, string>();

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

      {/* Grid wrapper — TrollOverlay is absolutely positioned inside here */}
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
                // In solved mode there is no selection glow — compound colours speak for themselves.
                // During generation there is no glow either — troll overlay handles visuals.
                const isSelected = !isGenerating && !solvedPreview && selected.has(key);

                // Colour in solved mode (never shown while troll is still animating)
                let solvedColor: string | null = null;
                if (solvedPreview && !isGenerating) {
                  solvedColor = wellColorFromPreview(key, solvedPreview, compounds);
                }

                // Compound fill colour (idle config or troll-shuffled during generation)
                const fillColor = activeFillMap.get(key) ?? null;

                // During generation darken usable wells slightly — tokens sit on top
                const darkenForTroll    = isGenerating && selected.has(key);
                // During generation make forbidden wells near-black so the boundary is clearly visible
                const darkenForbidden   = isGenerating && !selected.has(key);

                // Background
                let bg = "rgba(255,255,255,0.04)";
                if (solvedColor) {
                  bg = solvedColor;
                } else if (darkenForbidden) {
                  // Near-opaque black — clearly darker than anything in the usable region
                  bg = "rgba(0,0,0,0.92)";
                } else if (darkenForTroll) {
                  // Usable area: slightly tinted backdrop so tokens are visible above it
                  bg = "rgba(0,0,0,0.25)";
                } else if (fillColor) {
                  bg = fillColor;
                } else if (isSelected) {
                  bg = `${ACCENT}26`;
                }

                // Border / glow
                // • Usable well with no fill yet → ACCENT glow so the region is visible
                // • Usable well with compound fill → plain border, no glow (colour speaks for itself)
                // • Solved preview → plain border keyed to the solved colour, no glow
                // • Everything else → subtle default border
                let boxShadow = "none";
                let borderColor = "rgba(255,255,255,0.12)";
                let borderWidth = 1;
                if (solvedColor) {
                  borderColor = solvedColor;
                } else if (fillColor) {
                  borderColor = fillColor;
                } else if (isSelected) {
                  // Empty usable well — show the region glow
                  boxShadow = `inset 0 0 8px ${ACCENT}99, 0 0 12px ${ACCENT}66`;
                  borderColor = ACCENT;
                  borderWidth = 2;
                }

                const wn = wellName(r, c);

                return (
                  <div
                    key={c}
                    className="design-well"
                    style={{
                      width: wellSize,
                      height: wellSize,
                      minWidth: wellSize,
                      minHeight: wellSize,
                      borderRadius: 4,
                      background: bg,
                      border: `${borderWidth}px solid ${borderColor}`,
                      boxShadow,
                      transition: "background 0.45s ease, box-shadow 0.1s ease-out, border-color 0.1s ease-out",
                      cursor: "default",
                      position: "relative",
                    }}
                    onMouseEnter={() => setHoveredWell(wn)}
                    onMouseMove={(e) => setTooltipPos({ x: e.clientX + 16, y: e.clientY + 16 })}
                    onMouseLeave={() => setHoveredWell(null)}
                  />
                );
              })}
            </React.Fragment>
          ))}
        </div>

        {/* Troll overlay: tokens travel inside the grid-wrapper coordinate space */}
        {isGenerating && (
          <TrollOverlay
            tokens={tokens}
            wellSize={wellSize}
            gap={gap}
            headerSize={headerSize}
          />
        )}
      </div>

      {/* WaitingTroll progress bar */}
      {isGenerating && <TrollProgressBar progress={progress} />}

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
