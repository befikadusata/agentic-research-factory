-- 14.7 Multi-User Workspaces migration
-- Run via psql or add to an Alembic migration file.

CREATE TABLE IF NOT EXISTS workspaces (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name       VARCHAR(255) NOT NULL,
  owner_id   VARCHAR(255) NOT NULL,
  settings   JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workspaces_owner_id ON workspaces(owner_id);

CREATE TABLE IF NOT EXISTS workspace_members (
  workspace_id UUID        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id      VARCHAR(255) NOT NULL,
  role         VARCHAR(50)  NOT NULL DEFAULT 'viewer',  -- viewer | operator | admin
  PRIMARY KEY (workspace_id, user_id)
);

ALTER TABLE runs
  ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_runs_workspace_id ON runs(workspace_id);
