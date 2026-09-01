# Database

PostgreSQL 17, installed locally (no Docker, no hosted service). One database, `automations`, shared by the three builds. Everything is plain SQL you can read.

```
db/
  migrations/001_init.sql   schema: vendor, invoice, invoice_line_item, lead, email_triage + two views
  migrate.py                applies migrations in order, records them in schema_migration
  seed.py                   loads the sample invoices, fixtures and inbox so the dashboard has data
  exercises.md              SQL practice against this schema, easy to hard, with answers
```

## Setup

```bash
# after installing PostgreSQL 17 (superuser password "postgres" on this machine; change it for anything shared)
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/automations
uv run python db/migrate.py          # creates the database if needed, applies migrations
uv run python db/seed.py             # optional sample data
psql "$DATABASE_URL"                 # poke around
```

## Design choices worth being able to explain

- **Money is `NUMERIC(12,2)`**, never float. Floats cannot represent 0.10 exactly and totals drift.
- **The database re-checks what the code checks.** `invoice_total_adds_up` and `draft_only_for_support_sales` are CHECK constraints, so a bug in any client (Python, TypeScript, Go, n8n) cannot write an inconsistent row.
- **Natural unique keys make re-runs idempotent**: `(vendor_id, invoice_number)`, `lead.url`, `email_triage.message_id`. Re-processing the same input is an upsert, not a duplicate.
- **Enums for closed sets** (`email_category`, `urgency_level`). Adding a category is a migration, which is the point: it should be a deliberate change.
- **Views for the dashboard** so the web app runs `SELECT * FROM v_invoice` instead of embedding joins.
- **Line items are a child table**, not a JSON column, so "top 10 things we bought this quarter" is a GROUP BY, not a JSON parse.

## Migrations

Files run in name order once each; `schema_migration` remembers what ran. To change the schema, add `002_<what>.sql`; never edit `001` after it has been applied anywhere.
