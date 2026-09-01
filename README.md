# AI Automation Portfolio

Automation builds shipped as runnable n8n workflows with real code inside. Each build folder has the workflow JSON, the code, sample data, a README with setup steps, and a short demo video.

| # | Build | What it automates | Stack | Status |
|---|-------|-------------------|-------|--------|
| 01 | [Invoice extractor](builds/01-invoice-extractor/) | PDF invoices -> structured rows in Google Sheets + summary notification | n8n, JavaScript, Python, Claude structured outputs, Google Sheets | built, tests passing, live run pending API key |
| 02 | [Lead scraper + summarizer](builds/02-lead-scraper-summarizer/) | Company URLs -> scraped summary, fit score, opener -> Sheet + HubSpot CRM | n8n, Python, httpx, Claude, HubSpot | built, tests passing, live run pending API key |
| 03 | [Inbox triage](builds/03-inbox-triage/) | Gmail -> classify, label, draft replies, daily digest, Slack escalation | n8n, Python, Gmail, Claude, Slack | built, tests passing, live run pending API key |

## Running any build locally

1. `npm install -g n8n` then `n8n start` (opens http://localhost:5678).
2. Import `builds/<name>/workflow.json` via Workflows -> Import from file.
3. Add the credentials listed in that build's README.
4. Run on the sample data in `builds/<name>/sample-data/`.

## Layout

- `builds/` one folder per shipped automation
- `n8n/` local n8n config and env template
- `gigs/` marketplace profiles, offers, proposal template, pipeline tracker
- `learning/` session log
