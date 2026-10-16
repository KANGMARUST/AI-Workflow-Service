-- QuoteFlow initial schema. Review before applying to an EMPTY database.
-- Replaces the earlier unimplemented draft; this is NOT an upgrade migration.
-- App uses a server-side PostgreSQL role. Do not expose these tables through an anonymous REST role.
-- Decimal source values are canonical JSON strings to retain precision across SQLite/PostgreSQL.

CREATE TABLE quotes (
	id VARCHAR(36) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	source_quote_id VARCHAR(36),
	source_filename TEXT,
	source_storage_path TEXT,
	source_hash VARCHAR(64),
	status VARCHAR(30) NOT NULL,
	payload JSON NOT NULL,
	extraction_raw JSON NOT NULL,
	extraction_status VARCHAR(30) NOT NULL,
	version INTEGER NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	updated_at VARCHAR(40) NOT NULL,
	deleted_at VARCHAR(40),
	PRIMARY KEY (id),
	UNIQUE (source_hash)
);

CREATE INDEX ix_quotes_deleted_at ON quotes (deleted_at);

CREATE INDEX ix_quotes_status ON quotes (status);

CREATE TABLE quote_items (
	id VARCHAR(36) NOT NULL,
	quote_id VARCHAR(36) NOT NULL,
	line_number INTEGER NOT NULL,
	item_name TEXT NOT NULL,
	item_name_original TEXT,
	payload JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(quote_id) REFERENCES quotes (id) ON DELETE CASCADE
);

CREATE INDEX ix_quote_items_quote_id ON quote_items (quote_id);

CREATE TABLE quote_revisions (
	id VARCHAR(36) NOT NULL,
	quote_id VARCHAR(36) NOT NULL,
	version INTEGER NOT NULL,
	action VARCHAR(40) NOT NULL,
	snapshot JSON NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(quote_id) REFERENCES quotes (id)
);

CREATE INDEX ix_quote_revisions_quote_id ON quote_revisions (quote_id);

CREATE TABLE agent_jobs (
	id VARCHAR(36) NOT NULL,
	quote_id VARCHAR(36),
	kind VARCHAR(30) NOT NULL,
	status VARCHAR(30) NOT NULL,
	provider VARCHAR(30) NOT NULL,
	result JSON NOT NULL,
	error TEXT,
	created_at VARCHAR(40) NOT NULL,
	updated_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(quote_id) REFERENCES quotes (id)
);

CREATE INDEX ix_agent_jobs_status ON agent_jobs (status);

CREATE INDEX ix_agent_jobs_quote_id ON agent_jobs (quote_id);

-- No anonymous policies. The server connects with its trusted DB role.
ALTER TABLE quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE quote_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE quote_revisions ENABLE ROW LEVEL SECURITY;
