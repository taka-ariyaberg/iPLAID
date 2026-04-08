/**
 * DesignPlateViewer — read-only well-region display (Context 1).
 *
 * The usable wells are determined entirely by `emptyEdge` (supplied from the
 * external input field).  When a solved layout is provided it is displayed in
 * read-only mode using the existing colour system.
 */

import React, { useEffect, useMemo, useRef, useState } from "react";
import type { LayoutPreview } from "../../types";
import { getCompoundColor, getConcColor, DMSO_COLOR } from "../../utils/colorUtils";

// Accent colour for selection glow (matches iCELL cyan)
const ACCENT = "#00b8ff";

interface DesignPlateViewerProps {
  rows: number;
  cols: number;
  emptyEdge: number;
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

  // Rebuild selection whenever dimensions or edge change.
  useEffect(() => {
    setSelected(selectionFromEdge(rows, cols, emptyEdge));
  }, [rows, cols, emptyEdge]);

  // Solved layout colour map (memoised)
  const colorMap = useMemo(
    () => (solvedPreview ? buildCompoundColorMap(solvedPreview) : new Map()),
    [solvedPreview]
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

                // Colour in solved mode
                let solvedColor: string | null = null;
                if (solvedPreview) {
                  solvedColor = wellColorFromPreview(key, solvedPreview, colorMap);
                }

                // Background
                let bg = "rgba(255,255,255,0.04)";
                if (solvedColor) {
                  bg = solvedColor;
                } else if (isSelected) {
                  bg = `${ACCENT}26`;
                }

                // Box shadow glow
                let boxShadow = "none";
                let borderColor = "rgba(255,255,255,0.12)";
                let borderWidth = 1;
                if (isSelected) {
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
