/**
 * plateExport.ts
 *
 * Draws a clean plate-map figure onto an HTML canvas element.
 * Renders programmatically from data — NOT a DOM screenshot — so it looks like
 * a proper standalone figure rather than a cropped web-app panel.
 *
 * Visual language is identical to the UI: same compound/concentration colors,
 * same dark palette, same label style. Just without any interactive chrome.
 */

import type { LayoutPreview, TargetPlateDefinition } from "../types";

// ── Public types ──────────────────────────────────────────────────────────────

export type ExportWell = {
  well: string;
  compound: string | null;
  concentration: number | null;
  isFilled: boolean;
};

export type ExportPlate = {
  plateId: string;
  rowLabels: string[];
  columnLabels: number[];
  allWells: ExportWell[];
};

export type ExportLegendConc = {
  label: string;
  numeric: number | null;
  count: number;
};

export type ExportLegendGroup = {
  compound: string;
  count: number;
  concentrations: ExportLegendConc[];
};

export type PlateExportSpec = {
  title: string;
  plates: ExportPlate[];
  wellColorLookup: Map<string, Map<string, string>>;
  compoundColorLookup: Map<string, string>;
  legendGroups: ExportLegendGroup[];
  totalEmptyCount: number;
  plateDef?: TargetPlateDefinition;
  concentrationUnit: string;
  totalWellCount: number;
  plateCount: number;
};

// ── Palette — matches the UI exactly ─────────────────────────────────────────

const BG            = "#16161e";   // outer background (same as .panel-surface)
const CARD_BG       = "#1c1c2a";   // plate card background
const LEGEND_CARD   = "#13131b";   // legend compound card background
const TEXT_PRIMARY  = "#e2e8f0";
const TEXT_MUTED    = "#94a3b8";
const TEXT_DIM      = "#475569";
const LABEL_COLOR   = "rgba(34, 211, 238, 0.80)";  // column/row axis labels
const ACCENT        = "rgba(34, 211, 238, 0.90)";  // kicker / headings
const BORDER        = "rgba(255, 255, 255, 0.08)";
const EMPTY_WELL    = "#141421";   // opaque composite of rgba(14,14,22,0.5) over card bg

// ── Canvas renderer ───────────────────────────────────────────────────────────

export function renderPlateExport(spec: PlateExportSpec): HTMLCanvasElement {
  const DPR       = 2;          // retina
  const PAD       = 48;         // outer horizontal/vertical padding
  const CARD_PAD  = 18;         // plate card inner padding
  const ROW_LBL_W = 26;         // width reserved for row letter labels (A, B, …)
  const COL_LBL_H = 20;         // height of the column-number row
  const PLATE_ID_H = 30;        // plate title row height inside card
  const PLATE_GAP  = 16;        // gap between consecutive plate cards

  // ── Well sizing ───────────────────────────────────────────────────────────
  // Cell size is chosen from the column count — no fixed canvas width.
  const maxCols = Math.max(...spec.plates.map(p => p.columnLabels.length), 1);
  const CELL    = maxCols >= 48 ? 12
                : maxCols >= 32 ? 16
                : maxCols >= 24 ? 20
                : maxCols >= 16 ? 24
                : 30;
  const WELL_GAP  = Math.max(2, Math.min(4, Math.floor(CELL * 0.14)));
  const WELL_SIZE = CELL - WELL_GAP;
  const WELL_R    = Math.max(1, Math.floor(WELL_SIZE * 0.22));

  // Canvas width is exactly what the widest plate card needs — no empty space.
  const CANVAS_W = PAD * 2 + CARD_PAD * 2 + ROW_LBL_W + maxCols * CELL;

  // ── Height pass ───────────────────────────────────────────────────────────
  // Section 1: plates
  let platesH = 0;
  for (const plate of spec.plates) {
    const gridH  = COL_LBL_H + plate.rowLabels.length * CELL;
    const cardH  = CARD_PAD + PLATE_ID_H + gridH + CARD_PAD;
    platesH += cardH + PLATE_GAP;
  }

  // Section 3: legend
  const LEGEND_ITEM_W  = 165;
  const LEGEND_ITEM_GAP = 8;
  const LEGEND_CARD_W  = LEGEND_ITEM_W - LEGEND_ITEM_GAP;
  const LEGEND_BAR_H   = 4;
  const legendCount    = spec.legendGroups.length + (spec.totalEmptyCount > 0 ? 1 : 0);
  const legendCols     = Math.max(1, Math.floor((CANVAS_W - PAD * 2 + LEGEND_ITEM_GAP) / LEGEND_ITEM_W));

  // Measure tallest legend card to get row height
  const maxConcsVisible = (cardH: number) => Math.floor((cardH - LEGEND_BAR_H - 16 - 15 - 10) / 13);
  const LEGEND_CARD_H  = LEGEND_BAR_H + 16 + 15 + Math.min(
    Math.max(...spec.legendGroups.map(g => g.concentrations.length), 1), 4
  ) * 13 + 12;
  const legendRows     = Math.ceil(legendCount / legendCols);
  const LEG_HDR_H      = 18 + 6 + 22 + 18;  // kicker + gap + title + gap
  const legendH        = LEG_HDR_H + legendRows * (LEGEND_CARD_H + LEGEND_ITEM_GAP);

  const CANVAS_H = PAD + platesH + legendH + PAD;

  // ── Create canvas ─────────────────────────────────────────────────────────
  const canvas = document.createElement("canvas");
  canvas.width  = CANVAS_W * DPR;
  canvas.height = CANVAS_H * DPR;
  const ctx = canvas.getContext("2d")!;
  ctx.scale(DPR, DPR);

  // canvas is transparent — no background fill

  // ── Section 1: Plates ─────────────────────────────────────────────────────
  let y = PAD;
  ctx.textAlign    = "left";
  ctx.textBaseline = "top";
  for (const plate of spec.plates) {
    const filledCount = plate.allWells.filter(w => w.isFilled).length;
    const gridH       = COL_LBL_H + plate.rowLabels.length * CELL;
    const cardW       = CARD_PAD + ROW_LBL_W + plate.columnLabels.length * CELL + CARD_PAD;
    const cardH       = CARD_PAD + PLATE_ID_H + gridH + CARD_PAD;

    // Card background
    fillRr(ctx, PAD, y, cardW, cardH, 16, CARD_BG);
    strokeRr(ctx, PAD, y, cardW, cardH, 16, BORDER, 1);

    let iy = y + CARD_PAD;

    // Plate ID
    ctx.font         = "600 13px system-ui,-apple-system,sans-serif";
    ctx.fillStyle    = TEXT_PRIMARY;
    ctx.textBaseline = "top";
    ctx.fillText(plate.plateId, PAD + CARD_PAD, iy);
    const idW = ctx.measureText(plate.plateId).width;
    ctx.font      = "400 12px system-ui,-apple-system,sans-serif";
    ctx.fillStyle = TEXT_DIM;
    ctx.fillText(`(${filledCount} wells)`, PAD + CARD_PAD + idW + 8, iy + 1);
    iy += PLATE_ID_H;

    const GRID_X = PAD + CARD_PAD + ROW_LBL_W;

    // Build well lookup (normalise key: strip leading zeros from column number)
    const wellMap = new Map<string, ExportWell>();
    for (const w of plate.allWells) {
      const key = w.well.replace(/^([A-Za-z]+)0*(\d+)$/, "$1$2");
      wellMap.set(key, w);
    }

    // Column labels
    ctx.font         = `700 ${Math.min(10, Math.floor(WELL_SIZE * 0.52))}px system-ui,-apple-system,sans-serif`;
    ctx.fillStyle    = LABEL_COLOR;
    ctx.textAlign    = "center";
    ctx.textBaseline = "middle";
    for (let ci = 0; ci < plate.columnLabels.length; ci++) {
      ctx.fillText(
        String(plate.columnLabels[ci]),
        GRID_X + ci * CELL + WELL_SIZE / 2,
        iy + COL_LBL_H / 2,
      );
    }

    // Rows + wells
    for (let ri = 0; ri < plate.rowLabels.length; ri++) {
      const rowLabel = plate.rowLabels[ri];
      const rowY     = iy + COL_LBL_H + ri * CELL;

      // Row label
      ctx.font         = `700 ${Math.min(10, Math.floor(WELL_SIZE * 0.52))}px system-ui,-apple-system,sans-serif`;
      ctx.fillStyle    = LABEL_COLOR;
      ctx.textAlign    = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(rowLabel, PAD + CARD_PAD + ROW_LBL_W / 2, rowY + WELL_SIZE / 2);

      // Wells
      for (let ci = 0; ci < plate.columnLabels.length; ci++) {
        const wellName = `${rowLabel}${plate.columnLabels[ci]}`;
        const well     = wellMap.get(wellName);
        const wx       = GRID_X + ci * CELL;
        const wy       = rowY;

        let fillColor: string;
        if (well?.isFilled && well.compound) {
          const concLabel = well.concentration === null ? "No concentration" : String(well.concentration);
          fillColor = spec.wellColorLookup.get(well.compound)?.get(concLabel) ?? "#888";
        } else {
          fillColor = EMPTY_WELL;
        }

        fillRr(ctx, wx, wy, WELL_SIZE, WELL_SIZE, WELL_R, fillColor);
        strokeRr(ctx, wx, wy, WELL_SIZE, WELL_SIZE, WELL_R, BORDER, 0.5);
      }
    }

    y += cardH + PLATE_GAP;
  }

  // ── Section 3: Legend ─────────────────────────────────────────────────────
  y += 8;

  // Kicker
  ctx.font         = "600 10px system-ui,-apple-system,sans-serif";
  ctx.fillStyle    = ACCENT;
  ctx.textBaseline = "top";
  ctx.textAlign    = "left";
  ctx.fillText("LEGEND", PAD, y);
  y += 18 + 6;

  // Title
  ctx.font      = "600 16px system-ui,-apple-system,sans-serif";
  ctx.fillStyle = TEXT_MUTED;
  ctx.fillText("Compounds & concentrations", PAD, y);
  y += 22 + 18;

  // Legend cards
  const allLegendItems: { compound: string; count: number; concentrations: ExportLegendConc[]; isEmpty: boolean }[] = [
    ...spec.legendGroups.map(g => ({ compound: g.compound, count: g.count, concentrations: g.concentrations, isEmpty: false })),
    ...(spec.totalEmptyCount > 0 ? [{ compound: "Empty", count: spec.totalEmptyCount, concentrations: [] as ExportLegendConc[], isEmpty: true }] : []),
  ];

  for (let idx = 0; idx < allLegendItems.length; idx++) {
    const item = allLegendItems[idx];
    const col  = idx % legendCols;
    const row  = Math.floor(idx / legendCols);
    const lx   = PAD + col * LEGEND_ITEM_W;
    const ly   = y + row * (LEGEND_CARD_H + LEGEND_ITEM_GAP);

    const baseColor = item.isEmpty
      ? "rgba(255, 255, 255, 0.15)"
      : (spec.compoundColorLookup.get(item.compound) ?? "#888");

    // Card
    fillRr(ctx, lx, ly, LEGEND_CARD_W, LEGEND_CARD_H, 10, LEGEND_CARD);
    strokeRr(ctx, lx, ly, LEGEND_CARD_W, LEGEND_CARD_H, 10, BORDER, 1);

    // Color bar — top-rounded only
    ctx.fillStyle = baseColor;
    ctx.globalAlpha = 0.9;
    ctx.beginPath();
    ctx.roundRect(lx, ly, LEGEND_CARD_W, LEGEND_BAR_H, [10, 10, 0, 0]);
    ctx.fill();
    ctx.globalAlpha = 1;

    // Compound name
    const maxChars   = Math.floor((LEGEND_CARD_W - 16) / 7);
    const displayName = item.compound.length > maxChars
      ? item.compound.slice(0, maxChars - 1) + "…"
      : item.compound;
    ctx.font         = "600 11px system-ui,-apple-system,sans-serif";
    ctx.fillStyle    = TEXT_PRIMARY;
    ctx.textAlign    = "left";
    ctx.textBaseline = "top";
    ctx.fillText(displayName, lx + 8, ly + LEGEND_BAR_H + 9);

    // Well count
    ctx.font      = "400 9px system-ui,-apple-system,monospace";
    ctx.fillStyle = TEXT_DIM;
    ctx.textAlign = "right";
    ctx.fillText(`${item.count}w`, lx + LEGEND_CARD_W - 8, ly + LEGEND_BAR_H + 10);

    // Concentrations
    const visConcs  = item.concentrations.slice(0, maxConcsVisible(LEGEND_CARD_H));
    let concY       = ly + LEGEND_BAR_H + 9 + 16;
    for (const conc of visConcs) {
      const swatchColor = spec.wellColorLookup.get(item.compound)?.get(conc.label) ?? baseColor;

      // Swatch circle
      ctx.beginPath();
      ctx.arc(lx + 14, concY + 4, 3, 0, Math.PI * 2);
      ctx.fillStyle = swatchColor;
      ctx.fill();

      // Concentration label
      const concText = conc.numeric !== null
        ? `${conc.numeric} ${spec.concentrationUnit}`
        : "No conc.";
      ctx.font      = "400 10px system-ui,-apple-system,sans-serif";
      ctx.fillStyle = TEXT_MUTED;
      ctx.textAlign = "left";
      ctx.fillText(concText, lx + 22, concY);

      // Well count
      ctx.font      = "400 9px monospace";
      ctx.fillStyle = TEXT_DIM;
      ctx.textAlign = "right";
      ctx.fillText(`${conc.count}w`, lx + LEGEND_CARD_W - 8, concY);

      concY += 13;
    }

    if (item.concentrations.length > visConcs.length) {
      ctx.font      = "400 9px system-ui,-apple-system,sans-serif";
      ctx.fillStyle = TEXT_DIM;
      ctx.textAlign = "left";
      ctx.fillText(`+${item.concentrations.length - visConcs.length} more…`, lx + 8, concY);
    }
  }

  return canvas;
}

// ── Drawing helpers ───────────────────────────────────────────────────────────

function fillRr(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number,
  r: number | number[],
  color: string,
) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fill();
}

function strokeRr(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number,
  r: number | number[],
  color: string,
  lw: number,
) {
  ctx.strokeStyle = color;
  ctx.lineWidth = lw;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.stroke();
}

// ── Download helpers ──────────────────────────────────────────────────────────

export function buildExportFilename(title: string, ext: string): string {
  const base = title.replace(/\s+/g, "_").replace(/[^\w-]/g, "");
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  return `${base}_${date}.${ext}`;
}

export function downloadPlatePng(spec: PlateExportSpec, filename: string): void {
  const canvas  = renderPlateExport(spec);
  const dataUrl = canvas.toDataURL("image/png");
  triggerDownload(dataUrl, filename);
}

export function downloadPlateSvg(spec: PlateExportSpec, filename: string): void {
  const canvas     = renderPlateExport(spec);
  const pngDataUrl = canvas.toDataURL("image/png");
  const w          = canvas.width / 2;  // logical pixels (canvas drawn at 2× DPR)
  const h          = canvas.height / 2;
  const svgContent = [
    `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"`,
    `     width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">`,
    `  <image width="${w}" height="${h}" xlink:href="${pngDataUrl}"/>`,
    `</svg>`,
  ].join("\n");
  const blob = new Blob([svgContent], { type: "image/svg+xml" });
  const url  = URL.createObjectURL(blob);
  triggerDownload(url, filename);
  URL.revokeObjectURL(url);
}

export function downloadPlateCsv(preview: LayoutPreview, filename: string): void {
  const rows: string[] = ["plateID,well,cmpdname,CONCuM,cmpdnum"];
  preview.plates.forEach((plate) => {
    plate.wells.forEach((well) => {
      const conc    = well.concentration ?? 0;
      const cmpdnum = `${well.compound}_${conc}`;
      rows.push(`${plate.plateId},${well.well},${well.compound},${conc},${cmpdnum}`);
    });
  });
  const blob = new Blob([rows.join("\n")], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  triggerDownload(url, filename);
  URL.revokeObjectURL(url);
}

function triggerDownload(url: string, filename: string): void {
  const a    = document.createElement("a");
  a.href     = url;
  a.download = filename;
  a.click();
}
