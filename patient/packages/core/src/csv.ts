/** RFC 4180 quoting: a field is quoted only if it contains a comma, quote or line break; an
 * embedded quote is escaped by doubling it. Reused by the CLI's `--format csv` (task 21) instead
 * of a hand-rolled `join(",")`. */
export type CsvValue = string | number | boolean | null | undefined;

function quoteField(value: CsvValue): string {
  const s = value === null || value === undefined ? "" : String(value);
  if (/[",\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

export function toCsv(headers: string[], rows: CsvValue[][]): string {
  const lines = [headers.map(quoteField).join(",")];
  for (const row of rows) {
    lines.push(row.map(quoteField).join(","));
  }
  return lines.join("\r\n") + "\r\n";
}
