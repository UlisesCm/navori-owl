CREATE TABLE comments (
  id TEXT PRIMARY KEY,
  incident_id TEXT NOT NULL REFERENCES incidents(id),
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  author_id TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_comments_incident ON comments(incident_id, created_at, id);
