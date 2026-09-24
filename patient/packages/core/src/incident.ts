export type Severity = "SEV1" | "SEV2" | "SEV3" | "SEV4";
export type IncidentStatus = "open" | "investigating" | "resolved" | "closed";

export interface Incident {
  id: string;
  tenantId: string;
  service: string;
  severity: Severity;
  status: IncidentStatus;
  title: string;
  createdAt: string;
  updatedAt: string;
  resolvedAt: string | null;
  version: number;
}

const SEVERITIES: readonly Severity[] = ["SEV1", "SEV2", "SEV3", "SEV4"];

export function isSeverity(value: string): value is Severity {
  return (SEVERITIES as readonly string[]).includes(value);
}

/** Incident state machine (design D1: "maquina de estados con resolvedAt"). */
const TRANSITIONS: Record<IncidentStatus, readonly IncidentStatus[]> = {
  open: ["investigating", "resolved"],
  investigating: ["resolved", "open"],
  resolved: ["closed", "investigating"],
  closed: [],
};

export function canTransition(from: IncidentStatus, to: IncidentStatus): boolean {
  return TRANSITIONS[from].includes(to);
}

/** Whether a transition into/out of "resolved" implies setting/clearing resolvedAt. */
export function nextResolvedAt(to: IncidentStatus, now: Date, previous: string | null): string | null {
  if (to === "resolved" || to === "closed") {
    return previous ?? now.toISOString();
  }
  return null;
}
