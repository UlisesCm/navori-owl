import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/** Every CLI command opens the same on-disk sqlite file, under patient/data/ (gitignored),
 * unless OPSDESK_DB overrides it — tests always override it to ":memory:". */
export function defaultDbPath(): string {
  if (process.env.OPSDESK_DB) return process.env.OPSDESK_DB;
  const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
  return join(root, "data", "opsdesk.db");
}
