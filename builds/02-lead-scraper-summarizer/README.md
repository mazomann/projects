# 02 · Lead scout: company URLs → summary, fit score, opener → Sheet + HubSpot

Paste prospect URLs into a sheet. The workflow fetches each homepage, reduces it to the text a researcher would read, asks Claude for a 3-line summary, a 1-10 fit score against your ideal customer profile, up to four reasons, and one personalised opener sentence. Scores go back to the sheet; good fits are created as companies in HubSpot's free CRM.

```
Sheet (url) -> unscored only, cost cap -> fetch homepage (1 req / 1.5 s) -> HTML -> text -> Claude structured output -> validate -> write back to sheet -> score >= 7? -> HubSpot company
                                                                    | fetch failed / empty page -> skipped, error column filled
```

| | n8n workflow (`workflow.json`) | Python CLI (`leadscout/`) |
|---|---|---|
| Input | Google Sheet tab `Prospects` with a `url` column | text file, one URL per line |
| Fetch | HTTP Request node, batched 1 per 1.5 s | `httpx`, 1.5 s delay |
| HTML → text | regex in a Code node | BeautifulSoup |
| LLM | Anthropic Messages API with JSON schema | same, via SDK |
| Output | sheet columns + HubSpot company | CSV sorted by score + optional HubSpot |
| Tests | run on the sample sheet | `uv run pytest` (5 tests, fixtures, no network) |

## Python

```bash
uv sync && uv run pytest
export ANTHROPIC_API_KEY=sk-ant-...
uv run python -m leadscout.scout sample-data/urls.txt --icp "small law firms that still do intake by phone" --csv leads.csv
HUBSPOT_TOKEN=pat-... uv run python -m leadscout.scout urls.txt --icp "..." --hubspot
```

## n8n

1. Import `workflow.json`. Credentials: Anthropic, Google Sheets, HubSpot (private app token with `crm.objects.companies.write`).
2. Sheet tab `Prospects` with columns: `url`, `company`, `summary`, `fit_score`, `fit_reasons`, `opener`, `red_flags`, `scored_at`, `error`.
3. Env: `LEAD_SHEET_ID`, `LEAD_ICP` (one sentence), `LEAD_MAX` (per run, default 50), `LEAD_MIN_SCORE` (HubSpot threshold, default 7), `LEAD_MODEL`.
4. Execute. Re-running only touches rows with an empty `fit_score`, so it is safe to schedule.

## Design notes

- **Politeness and cost caps are built in**: one fetch every 1.5 s, at most 50 URLs a run, 6,000 characters per page sent to the model. About 2k input tokens per company, roughly $0.005 on Claude Sonnet 5.
- **Grounded output**: the prompt forbids facts not on the page, and the opener has to cite something specific. Off-target pages (parked domains, login walls) get a score of 1 with the reason in `red_flags`.
- **Idempotent**: scored rows are skipped, failed rows keep the error text so a human can fix the URL.
- **Why HubSpot only above a threshold**: the CRM stays clean; the sheet keeps everything.

## What I learned

- n8n's expression parser ends an expression at the first `}}`, so any JSON object literal has to be built in a Code node and passed through as a single value.
- Item pairing across Code nodes in "run once for all items" mode is positional; filtering must happen before the branch that calls the API or the indexes drift.
