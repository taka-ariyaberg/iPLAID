import type { CompoundDef, DesignConfig, SolventDef } from "../../types";

export function defaultDesignConfig(rows = 16, cols = 24): DesignConfig {
  return {
    plate_rows: rows,
    plate_cols: cols,
    empty_edge: 1,
    compounds: [],
    solvents: [],
    concentrations_on_different_rows: true,
    concentrations_on_different_columns: true,
    replicates_on_same_plate: true,
    replicates_on_different_plates: false,
    allow_empty_wells: true,
    balance_controls_inside_plate: true,
    interconnected_plates: true,
    control_slack: 0,
    force_spread_controls: false,
    force_spread_concentrations: false,
    horizontal_cell_lines: 1,
    vertical_cell_lines: 1,
    timeout_seconds: 30,
    num_threads: 4,
    random_seed: null,
  };
}

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
