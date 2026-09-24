CREATE TABLE tenants (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE incidents (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  service TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  resolved_at TEXT,
  version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_incidents_tenant_created ON incidents(tenant_id, created_at, id);
CREATE INDEX idx_incidents_tenant_status ON incidents(tenant_id, status);
CREATE INDEX idx_incidents_tenant_service ON incidents(tenant_id, service);
