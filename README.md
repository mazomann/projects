# Projects

Automation builds shipped as runnable n8n workflows with real code inside. Each build folder has the workflow JSON, the code, sample data, a README with setup steps, and a short demo video.

| # | Build | What it automates | Stack | Status |
|---|-------|-------------------|-------|--------|
| 01 | [Invoice extractor](builds/01-invoice-extractor/) | PDF invoices -> structured rows in Google Sheets + summary notification | n8n, Python (21 tests), TypeScript (26 tests), Claude structured outputs, Google Sheets | built, live run pending API key |
| 02 | [Lead scraper + summarizer](builds/02-lead-scraper-summarizer/) | Company URLs -> scraped summary, fit score, opener -> Sheet + HubSpot CRM | n8n, Python (5 tests), Go CLI (4 packages tested), Claude, HubSpot | built, live run pending API key |
| 03 | [Inbox triage](builds/03-inbox-triage/) | Gmail -> classify, label, draft replies, daily digest, Slack escalation | n8n, Python (10 tests), Gmail, Claude, Slack | built, live run pending API key |

## Shared database and dashboard

All three builds write to one local PostgreSQL 17 database with a hand-written schema, CHECK constraints that mirror the code's validation, and views the dashboard reads. See [db/README.md](db/README.md) and the [SQL exercises](db/exercises.md). The [dashboard](apps/dashboard/) is a Node + TypeScript server with plain SQL queries and one HTML page.

```bash
uv run python db/migrate.py && uv run python db/seed.py
cd apps/dashboard && npm install && npm start     # http://localhost:3000
```

## Languages

Python is the primary implementation. Build 01 also has a [TypeScript twin](builds/01-invoice-extractor/ts/) and build 02 a [Go CLI](builds/02-lead-scraper-summarizer/go/), each with the same schema, validation rules, and tests, so the design can be compared across languages.

## Running any build locally

1. `npm install -g n8n` then `n8n start` (opens http://localhost:5678). See [n8n/README.md](n8n/README.md) for the env switches and headless import.
2. Import `builds/<name>/workflow.json` via Workflows -> Import from file.
3. Add the credentials listed in that build's README.
4. Run on the sample data in `builds/<name>/sample-data/`.

## Layout

- `builds/` one folder per shipped automation, plus [rescue-checklist.md](builds/rescue-checklist.md) for diagnosing broken workflows
- `db/` PostgreSQL 17 schema, migrations, seed data, and SQL exercises
- `apps/dashboard/` Node + TypeScript server over the same database
- `n8n/` local n8n config and env template

## Quality gates

Every package runs the same four gates before anything is called done: lint, format check, type check, tests.

```bash
cd builds/<name> && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q
cd builds/01-invoice-extractor/ts && npm run check       # eslint, prettier, tsc, vitest
cd builds/02-lead-scraper-summarizer/go && gofmt -l . && go vet ./... && go test ./...
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs all of them on every push, plus a job that spins up PostgreSQL 17, migrates, seeds, and asserts that a CHECK constraint rejects an invoice whose total does not match its line items.

## What I learned

- Structured output beats prompt-and-parse: give the model a JSON schema, validate the result against the same model the database constrains, and feed validation errors back on retry instead of accepting a near-miss.
- Validation belongs in two places on purpose. The Python model and the SQL CHECK constraints encode the same rules, so a bug in one is caught by the other.
- n8n is the delivery shell, not the logic. Expressions end at the first `}}`, so JSON bodies get built in Code nodes, and items are paired positionally rather than by hope.
- Writing build 01 twice, in Python and TypeScript, and build 02 in Go, made the design decisions visible: what was essential showed up in all of them, what was habit did not.
