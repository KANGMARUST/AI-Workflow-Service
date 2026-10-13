-- Direct PostgreSQL/Supabase database connection schema. No public browser credentials.
-- FastAPI also creates these tables automatically on startup.
CREATE TABLE IF NOT EXISTS quotes (
    id VARCHAR(36) PRIMARY KEY,
    payload TEXT NOT NULL,
    file_hash VARCHAR(64)
);
CREATE INDEX IF NOT EXISTS ix_quotes_file_hash ON quotes(file_hash);
CREATE TABLE IF NOT EXISTS quote_history (
    id VARCHAR(36) PRIMARY KEY,
    quote_id VARCHAR(36) NOT NULL,
    version INTEGER NOT NULL,
    changed_at VARCHAR(40),
    snapshot TEXT
);
CREATE INDEX IF NOT EXISTS ix_quote_history_quote_id ON quote_history(quote_id);
-- Deny public PostgREST access; use an appropriate server-side direct DB role.
ALTER TABLE quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE quote_history ENABLE ROW LEVEL SECURITY;
