/** M2/permissions: tenant isolation invariant (docs/permissions.md) — a resource from another
 * tenant must read as 404, never 403 (403 would confirm the resource exists). */
export type Role = "viewer" | "responder" | "admin";

export interface Actor {
  tenantId: string;
  role: Role;
}

export function canWrite(role: Role): boolean {
  return role === "responder" || role === "admin";
}
