/**
 * colorUtils.ts — central colour generation for the plate viewer.
 *
 * Groups (compounds):
 *   Equidistant hue assignment — 360° divided evenly among N compounds.
 *   Step = 360/N, so for any N the groups are always as far apart as possible.
 *   Offset by 30° so slot 0 starts at a vivid, non-red hue.
 *
 * Subgroups (concentrations):
 *   Same hue as parent compound, opacity 0.60 (lowest) → 1.00 (highest).
 */

/** Bright amber for DMSO/control wells — unmistakably distinct from all generated hues. */
export const DMSO_COLOR = 'rgba(251, 191, 36, 0.90)';

/** Near-invisible fill for unfilled wells. */
export const EMPTY_COLOR = 'rgba(255, 255, 255, 0.04)';

/**
 * Returns a vivid HSL colour for compound at position `index` out of `total` compounds.
 * Hues are distributed as 360°/total apart — maximum possible perceptual separation.
 * Call this with the sorted index of each compound so the assignment is stable.
 */
export function getCompoundColor(index: number, total: number): string {
  const hue = (30 + (index / Math.max(total, 1)) * 360) % 360;
  return `hsl(${hue.toFixed(1)}, 88%, 62%)`;
}

/**
 * Returns a vivid HSL colour for compound at insertion index `index`.
 * Uses golden-angle spacing (137.508°) so that adding a new compound
 * never shifts the colours already assigned to existing compounds.
 */
export function getStableCompoundColor(index: number): string {
  const hue = (30 + index * 137.508) % 360;
  return `hsl(${hue.toFixed(1)}, 88%, 62%)`;
}

/**
 * Returns the well fill colour for a concentration at a given rank within its group.
 * baseColor must be an hsl() string as returned by getCompoundColor.
 * Alpha: 0.60 (rank 0 = lowest conc) → 1.00 (rank total-1 = highest conc).
 */
export function getConcColor(baseColor: string, rank: number, total: number): string {
  const alpha = total <= 1
    ? 1.00
    : parseFloat((0.60 + (rank / (total - 1)) * 0.40).toFixed(2));
  const m = baseColor.match(/hsl\(([\d.]+),\s*([\d.]+)%,\s*([\d.]+)%\)/);
  if (m) return `hsla(${m[1]}, ${m[2]}%, ${m[3]}%, ${alpha})`;
  return baseColor;
}
