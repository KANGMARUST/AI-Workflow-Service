-- Additive migration: quote-grounded chat tables only.

-- Apply once using the same trusted server role as the existing schema.

BEGIN;

CREATE TABLE quote_chats (
	id VARCHAR(36) NOT NULL,
	title VARCHAR(200) NOT NULL,
	quote_ids JSON NOT NULL,
	version INTEGER NOT NULL,
	pending_request_id VARCHAR(36),
	created_at VARCHAR(40) NOT NULL,
	updated_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_quote_chats_updated_at ON quote_chats (updated_at);

ALTER TABLE quote_chats ENABLE ROW LEVEL SECURITY;

CREATE TABLE quote_chat_messages (
	id VARCHAR(36) NOT NULL,
	chat_id VARCHAR(36) NOT NULL,
	sequence INTEGER NOT NULL,
	role VARCHAR(20) NOT NULL,
	content TEXT NOT NULL,
	sources JSON NOT NULL,
	metadata_json JSON NOT NULL,
	created_at VARCHAR(40) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (chat_id, sequence),
	FOREIGN KEY(chat_id) REFERENCES quote_chats (id) ON DELETE CASCADE
);

CREATE INDEX ix_quote_chat_messages_chat_id ON quote_chat_messages (chat_id);

ALTER TABLE quote_chat_messages ENABLE ROW LEVEL SECURITY;

-- No anonymous policies or public grants are created.

COMMIT;
