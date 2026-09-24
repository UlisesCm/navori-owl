import type { IncomingMessage } from "node:http";
import { UnauthorizedError, type Actor, type Role } from "@opsdesk/core";

const ROLES: readonly Role[] = ["viewer", "responder", "admin"];

/** Requests arrive already authenticated by the gateway in front of this service (out of
 * scope here); it forwards the caller's tenant, role and user id as headers. */
export function actorFromRequest(req: IncomingMessage): Actor & { userId: string } {
  const tenantId = req.headers["x-tenant-id"];
  const role = req.headers["x-role"];
  const userId = req.headers["x-user-id"];
  if (typeof tenantId !== "string" || !tenantId) {
    throw new UnauthorizedError("missing x-tenant-id");
  }
  if (typeof role !== "string" || !(ROLES as readonly string[]).includes(role)) {
    throw new UnauthorizedError("missing or invalid x-role");
  }
  if (typeof userId !== "string" || !userId) {
    throw new UnauthorizedError("missing x-user-id");
  }
  return { tenantId, role: role as Role, userId };
}
