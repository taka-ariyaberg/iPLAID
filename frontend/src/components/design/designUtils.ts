import type { CompoundDef, SolventDef } from "../../types";

/** Total wells required across all compounds and solvents. */
export function totalWellsNeeded(
  compounds: CompoundDef[],
  solvents: SolventDef[],
): number {
  const compoundWells = compounds.reduce(
    (sum, compound) => sum + compound.conc_entries.reduce((entrySum, entry) => entrySum + entry.replicates, 0),
    0,
  );
  const solventWells = solvents.reduce((sum, solvent) => sum + solvent.replicates, 0);
  return compoundWells + solventWells;
}
