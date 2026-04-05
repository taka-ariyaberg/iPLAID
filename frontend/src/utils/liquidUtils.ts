/** Parse a `Liquid Name` string of the form `[Compound][StockMM]` into its parts.
 *  Returns null concentration for DMSO (pure solvent, no meaningful molar stock value). */
export function parseLiquidName(liquidName: string): { compound: string; stockMM: number | null } {
  const m = liquidName.match(/^\[(.*?)\]\[(.*?)\]$/);
  if (!m) return { compound: liquidName, stockMM: null };
  const compound = m[1];
  const stockMM = parseFloat(m[2]);
  if (compound.toUpperCase() === "DMSO") return { compound, stockMM: null };
  return { compound, stockMM: isNaN(stockMM) ? null : stockMM };
}
