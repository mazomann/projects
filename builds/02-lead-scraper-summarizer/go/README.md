# leadscout (Go)

Single-binary port of the Python `leadscout` CLI one directory up. Same pipeline, same prompt, same JSON schema, same CSV columns.

```
urls.txt -> fetch homepage (browser UA, 15 s timeout, redirects, 1 req / 1.5 s)
         -> HTML -> {title, description, headings, text <= 6000 chars}
         -> Claude Messages API, output constrained to the lead schema
         -> validate (score 1-10, company/opener present, <= 4 reasons)
         -> leads.csv sorted by fit_score desc  (+ optional HubSpot company)
```

## Build

```bash
cd go
go build ./cmd/leadscout          # produces ./leadscout (leadscout.exe on Windows)
go test ./...                     # no network, no API key needed
```

Requires Go 1.22+. Only dependency outside the standard library is `golang.org/x/net/html` for parsing.

## Run

```bash
export ANTHROPIC_API_KEY=sk-ant-...
./leadscout -urls ../sample-data/urls.txt -icp "small law firms that still do intake by phone" -csv leads.csv
HUBSPOT_TOKEN=pat-... ./leadscout -urls urls.txt -icp "..." -hubspot
```

| Flag | Default | Meaning |
|---|---|---|
| `-urls` | (required) | text file, one URL per line, `#` comments allowed |
| `-icp` | (required) | ideal customer profile, one sentence |
| `-csv` | `leads.csv` | output path |
| `-max` | `50` | cost cap: max URLs per run |
| `-delay` | `1.5` | seconds between fetches |
| `-hubspot` | off | create a company per lead (needs `HUBSPOT_TOKEN`) |

Env: `ANTHROPIC_API_KEY`, `LEAD_MODEL` (default `claude-sonnet-5`), `HUBSPOT_TOKEN`.

Progress goes to stderr (`[3/12]  9  Harbor & Pike Law` or `[4/12] FAILED https://... : reason`), the summary line `N scored, M failed -> leads.csv` goes to stdout. Exit code is 1 only when every URL failed, so a scheduled run with one dead site still succeeds.

## Check

The gate before committing. Run all of these from this directory (`builds/02-lead-scraper-summarizer/go`); Go lives at `C:\Program Files\Go\bin`.

```bash
gofmt -l .      # prints the path of every misformatted file; silence means pass (gofmt -w . fixes)
go vet ./...    # suspicious constructs the compiler allows
go test ./...   # unit tests, no network and no API key
```

Optional fourth gate, if `go install honnef.co/go/tools/cmd/staticcheck@latest` has been run:

```bash
staticcheck ./...   # unused code, simplifications, bug patterns vet misses
```

## How it mirrors the Python version

| Python | Go |
|---|---|
| `page.fetch_html` (httpx) | `internal/page.Fetch` (net/http, same UA, 15 s, redirects) |
| `page.html_to_text` (BeautifulSoup) | `internal/page.Reduce` (x/net/html; drops script/style/noscript/svg/nav/footer/iframe) |
| `schema.LeadAssessment` + `JSON_SCHEMA` (pydantic) | `internal/lead.Assessment` + `Validate()` + `lead.Schema` |
| `scout.claude_llm` (anthropic SDK) | `internal/llm.Anthropic.Assess` (raw `POST /v1/messages`, `output_config.format.json_schema`, refusal -> `ErrRefusal`) |
| `scout.hubspot_upsert` | `internal/hubspot.CreateCompany` |
| `scout.main` | `cmd/leadscout` |
| `tests/test_scout.py` | `go test ./...` against the same `sample-data/fixtures` |

The LLM client sits behind the `llm.Client` interface so tests inject a fake and the API test uses `httptest` with a canned Anthropic-shaped reply. No test touches the network.

Differences worth knowing: the Go validator enforces what the task spec asks for (score range, non-empty company and opener, at most four reasons) and does not replicate pydantic's summary/opener length bounds; the CSV only gets a `hubspot_id` column when at least one row has one, as `DictWriter` does.

## Why Go

The Python version needs `uv`, a virtualenv and four packages on whichever machine runs it. A client who wants this on a nightly Task Scheduler or cron job is better served by one static binary: `go build` produces a file they copy anywhere, with no runtime to install, no dependency drift, and cross-compilation (`GOOS=linux go build`) from the same source. The HTTP, JSON, CSV and flag handling are all standard library, so the only third-party code is the HTML parser.
