/** Opaque cursor: base64 of "<createdAt>|<id>", the same tuple every list query orders and
 * seeks by. Never a raw row offset (OFFSET pagination silently skips/repeats rows when the
 * underlying set changes between pages). */
export interface Cursor {
  createdAt: string;
  id: string;
}

export function encodeCursor(cursor: Cursor): string {
  return Buffer.from(`${cursor.createdAt}|${cursor.id}`, "utf8").toString("base64url");
}

export function decodeCursor(raw: string): Cursor {
  const decoded = Buffer.from(raw, "base64url").toString("utf8");
  const sep = decoded.indexOf("|");
  if (sep < 0) {
    throw new Error(`invalid cursor: ${raw}`);
  }
  return { createdAt: decoded.slice(0, sep), id: decoded.slice(sep + 1) };
}
