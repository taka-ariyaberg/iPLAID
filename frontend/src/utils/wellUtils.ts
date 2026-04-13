const WELL_PATTERN = /^([A-Za-z]+)0*(\d+)$/;

export function normalizeWellKey(well: string): string {
  const text = String(well).trim();
  const match = text.match(WELL_PATTERN);
  if (!match) return text;
  return `${match[1].toUpperCase()}${Number.parseInt(match[2], 10)}`;
}

export function formatWellId(rowLabel: string, column: number, minDigits = 2): string {
  const normalizedRow = String(rowLabel).trim().toUpperCase();
  const normalizedColumn = Number.parseInt(String(column), 10);
  const width = Math.max(minDigits, String(normalizedColumn).length);
  return `${normalizedRow}${String(normalizedColumn).padStart(width, "0")}`;
}

export function canonicalWellId(well: string, minDigits = 2): string {
  const text = String(well).trim();
  const match = text.match(WELL_PATTERN);
  if (!match) return text;
  return formatWellId(match[1], Number.parseInt(match[2], 10), minDigits);
}
