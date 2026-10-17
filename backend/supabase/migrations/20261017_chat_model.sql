-- Additive migration for an existing chat installation. No quotation data changes.
BEGIN;
ALTER TABLE quote_chats ADD COLUMN IF NOT EXISTS model VARCHAR(200);
COMMIT;
