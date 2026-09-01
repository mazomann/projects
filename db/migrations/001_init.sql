-- 001_init.sql
-- One database for all three builds. Hand-written on purpose: no ORM, so the schema is something
-- you can read, explain in an interview, and change with a second migration.
--
-- Conventions: snake_case, singular table names, every table has id + created_at,
-- money as NUMERIC(12,2) (never FLOAT), timestamps in UTC (TIMESTAMPTZ).

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migration (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- build 01: invoices
CREATE TABLE IF NOT EXISTS vendor (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invoice (
    id              BIGSERIAL PRIMARY KEY,
    vendor_id       BIGINT NOT NULL REFERENCES vendor(id),
    invoice_number  TEXT NOT NULL,
    invoice_date    DATE NOT NULL,
    due_date        DATE,
    currency        CHAR(3) NOT NULL DEFAULT 'USD',
    subtotal        NUMERIC(12,2) NOT NULL CHECK (subtotal >= 0),
    tax             NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (tax >= 0),
    total           NUMERIC(12,2) NOT NULL CHECK (total >= 0),
    source_file     TEXT,
    extracted_by    TEXT,                       -- model id, or 'manual'
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- the same reconciliation the code does, enforced by the database too
    CONSTRAINT invoice_total_adds_up CHECK (abs(subtotal + tax - total) <= 0.02),
    CONSTRAINT invoice_due_after_issue CHECK (due_date IS NULL OR due_date >= invoice_date),
    CONSTRAINT invoice_unique_per_vendor UNIQUE (vendor_id, invoice_number)
);

CREATE TABLE IF NOT EXISTS invoice_line_item (
    id          BIGSERIAL PRIMARY KEY,
    invoice_id  BIGINT NOT NULL REFERENCES invoice(id) ON DELETE CASCADE,
    position    SMALLINT NOT NULL,
    description TEXT NOT NULL,
    quantity    NUMERIC(12,3) NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(12,4) NOT NULL CHECK (unit_price >= 0),
    amount      NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    UNIQUE (invoice_id, position)
);

CREATE INDEX IF NOT EXISTS invoice_date_idx ON invoice (invoice_date DESC);

-- ---------------------------------------------------------------- build 02: leads
CREATE TABLE IF NOT EXISTS lead (
    id          BIGSERIAL PRIMARY KEY,
    url         TEXT NOT NULL UNIQUE,
    company     TEXT,
    summary     TEXT,
    fit_score   SMALLINT CHECK (fit_score BETWEEN 1 AND 10),
    fit_reasons TEXT[] NOT NULL DEFAULT '{}',
    opener      TEXT,
    red_flags   TEXT[] NOT NULL DEFAULT '{}',
    icp         TEXT,                          -- the profile it was scored against
    hubspot_id  TEXT,
    error       TEXT,                          -- why scoring failed, if it did
    scored_at   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lead_score_idx ON lead (fit_score DESC NULLS LAST);

-- ---------------------------------------------------------------- build 03: email triage
CREATE TYPE email_category AS ENUM ('support', 'sales', 'billing', 'spam', 'needs_human');
CREATE TYPE urgency_level  AS ENUM ('low', 'normal', 'high');

CREATE TABLE IF NOT EXISTS email_triage (
    id            BIGSERIAL PRIMARY KEY,
    message_id    TEXT NOT NULL UNIQUE,        -- Gmail message id, so re-runs are idempotent
    thread_id     TEXT,
    sender        TEXT NOT NULL,
    subject       TEXT NOT NULL DEFAULT '',
    received_at   TIMESTAMPTZ,
    category      email_category NOT NULL,
    confidence    NUMERIC(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    urgency       urgency_level NOT NULL DEFAULT 'normal',
    summary       TEXT NOT NULL,
    draft_reply   TEXT,
    reason        TEXT,
    drafted       BOOLEAN NOT NULL DEFAULT false,   -- a Gmail draft was created
    escalated     BOOLEAN NOT NULL DEFAULT false,   -- Slack ping sent
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT draft_only_for_support_sales
        CHECK (draft_reply IS NULL OR category IN ('support', 'sales'))
);

CREATE INDEX IF NOT EXISTS email_triage_day_idx ON email_triage (created_at DESC);

-- ---------------------------------------------------------------- views the dashboard reads
CREATE OR REPLACE VIEW v_invoice AS
SELECT i.id, v.name AS vendor, i.invoice_number, i.invoice_date, i.due_date, i.currency,
       i.subtotal, i.tax, i.total, i.source_file, i.created_at,
       (SELECT count(*) FROM invoice_line_item li WHERE li.invoice_id = i.id) AS line_count
FROM invoice i JOIN vendor v ON v.id = i.vendor_id;

CREATE OR REPLACE VIEW v_daily_triage AS
SELECT date_trunc('day', created_at)::date AS day, category, count(*) AS emails,
       count(*) FILTER (WHERE drafted) AS drafts, count(*) FILTER (WHERE escalated) AS escalations
FROM email_triage GROUP BY 1, 2 ORDER BY 1 DESC, 2;

INSERT INTO schema_migration (version) VALUES ('001_init') ON CONFLICT DO NOTHING;
COMMIT;
