/** Parse a `Liquid Name` string of the form `[Compound][StockMM]` into its parts.
 *  Returns null concentration for pure solvent rows (0 mM stock, no meaningful molar stock value). */
export function parseLiquidName(liquidName: string): { compound: string; stockMM: number | null } {
  const m = liquidName.match(/^\[(.*?)\]\[(.*?)\]$/);
  if (!m) return { compound: liquidName, stockMM: null };
  const compound = m[1];
  const stockMM = parseFloat(m[2]);
  if (isNaN(stockMM) || stockMM === 0) return { compound, stockMM: null };
  return { compound, stockMM };
}
