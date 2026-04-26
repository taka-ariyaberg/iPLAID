import type { CompoundDef, SolventDef } from "../types";

export type FlatRow = {
  id: string;
  compound_name: string;
  concentration_uM: number;
  replicate_number: number;
  role: "treatment" | "solvent";
};

export type ParseResult = {
  rows: FlatRow[];
  errors: string[];
  warnings: string[];
};

export function parseCSVText(text: string): ParseResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const rows: FlatRow[] = [];

  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (lines.length === 0) {
    errors.push("File is empty.");
    return { rows, errors, warnings };
  }

  const header = lines[0].split(",").map((h) => h.trim().toLowerCase());
  const idx = {
    compound_name:    header.indexOf("compound_name"),
    concentration_um: header.findIndex((h) => h === "concentration_um"),
    replicate_number: header.indexOf("replicate_number"),
    role:             header.indexOf("role"),
  };

  const missing = (Object.entries(idx) as [string, number][])
    .filter(([, i]) => i === -1)
    .map(([col]) => col);
  if (missing.length > 0) {
    errors.push(`Missing required column(s): ${missing.join(", ")}.`);
    return { rows, errors, warnings };
  }

  lines.slice(1).forEach((line, lineIdx) => {
    const rowNum = lineIdx + 2;
    const cells = line.split(",").map((c) => c.trim());
    const name      = cells[idx.compound_name]    ?? "";
    const concRaw   = cells[idx.concentration_um] ?? "";
    const repsRaw   = cells[idx.replicate_number] ?? "";
    const roleLower = (cells[idx.role] ?? "").toLowerCase();

    if (!name) {
      warnings.push(`Row ${rowNum}: empty compound_name — skipped.`);
      return;
    }
    if (roleLower !== "treatment" && roleLower !== "solvent") {
      warnings.push(`Row ${rowNum}: unknown role "${roleLower}" — skipped.`);
      return;
    }

    const conc = parseFloat(concRaw);
    const reps = parseInt(repsRaw, 10);

    if (Number.isNaN(conc)) {
      errors.push(`Row ${rowNum} (${name}): concentration_uM "${concRaw}" is not a number.`);
      return;
    }
    if (Number.isNaN(reps) || reps < 1) {
      errors.push(`Row ${rowNum} (${name}): replicate_number "${repsRaw}" must be a positive integer.`);
      return;
    }

    rows.push({
      id:               `row-${rowNum}`,
      compound_name:    name,
      concentration_uM: conc,
      replicate_number: reps,
      role:             roleLower as "treatment" | "solvent",
    });
  });

  return { rows, errors, warnings };
}

export function groupRowsToCompounds(rows: FlatRow[]): {
  compounds: CompoundDef[];
  solvents: SolventDef[];
} {
  const compoundMap = new Map<string, CompoundDef>();
  const solventMap  = new Map<string, SolventDef>();

  for (const row of rows) {
    const key = row.compound_name.trim().toLowerCase();
    if (row.role === "treatment") {
      if (!compoundMap.has(key)) {
        compoundMap.set(key, { name: row.compound_name, conc_entries: [] });
      }
      compoundMap.get(key)!.conc_entries.push({
        value_um:   row.concentration_uM,
        replicates: row.replicate_number,
      });
    } else {
      solventMap.set(key, { name: row.compound_name, replicates: row.replicate_number });
    }
  }

  return {
    compounds: Array.from(compoundMap.values()),
    solvents:  Array.from(solventMap.values()),
  };
}
