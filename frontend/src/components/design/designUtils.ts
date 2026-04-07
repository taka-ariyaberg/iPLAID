import type { CompoundDef, ControlDef } from "../../types";

/** Total wells required across all compounds and controls. */
export function totalWellsNeeded(
  compounds: CompoundDef[],
  controls: ControlDef[],
): number {
  const cw  = compounds.reduce((s, c) => s + c.conc_entries.reduce((es, e) => es + e.replicates, 0), 0);
  const ctw = controls.reduce( (s, c) => s + c.conc_entries.reduce((es, e) => es + e.replicates, 0), 0);
  return cw + ctw;
}
