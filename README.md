# AI Automation Portfolio

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

- `builds/` one folder per shipped automation, plus [rescue-checklist.md](builds/rescue-checklist.md) for fixing other people's broken workflows
- `n8n/` local n8n config and env template
- `gigs/` marketplace [profile copy](gigs/profiles/profile.md), [offers and pricing](gigs/offers/offers.md), [proposal template](gigs/proposals/template.md), pipeline tracker
- `learning/` session log
