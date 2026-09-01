# 01 · Invoice extractor: PDF → validated JSON → Google Sheet

Drop PDF invoices in a folder, get one clean row per invoice in a spreadsheet plus a run summary in Slack. Totals are reconciled before anything is written, so a bad extraction is flagged instead of booked.

```
folder of PDFs -> extract text -> guard (scanned?) -> Claude structured output -> validate (totals add up?) -> Google Sheets -> Slack summary
                                      | no text                                     | fails
                                      +--------------> "needs attention" list <-----+
```

Two implementations of the same pipeline live here on purpose:

| | n8n workflow (`workflow.json`) | Python CLI (`extractor/`) |
|---|---|---|
| For | clients who want a visual, editable automation | tests, batch runs, and reading the logic as code |
| LLM call | HTTP Request node → Anthropic Messages API with a JSON schema | `anthropic` SDK, same schema |
| Validation | `Validate + flatten` Code node | `extractor/schema.py` (pydantic) |
| Tests | import and run on `sample-data/` | `uv run pytest` (21 tests, no API key needed) |

## Run the Python version

```bash
uv sync
uv run pytest                                              # fake LLM, no key
export ANTHROPIC_API_KEY=sk-ant-...                        # real extraction
uv run python -m extractor.extract sample-data/*.pdf --csv out.csv
```

## Run the n8n version

1. `n8n start`, open http://localhost:5678, Workflows → Import from file → `workflow.json`.
2. Credentials: **Anthropic** (API key), **Google Sheets** (OAuth2), **Slack** (OAuth2). Assign each to its node.
3. Environment (set before `n8n start`, or hardcode in the nodes):
   - `INVOICE_INBOX` folder to watch (defaults to `sample-data/`)
   - `INVOICE_SHEET_ID` Google Sheet id, with a tab named `Invoices`
   - `INVOICE_SLACK_CHANNEL` (default `#finance`)
   - `INVOICE_MODEL` (default `claude-sonnet-5`)
4. Click *Execute workflow*. Swap the manual trigger for a Schedule or Google Drive trigger for production.

## Design notes

- **Structured output, not prompt-and-pray.** The request pins a JSON schema (`output_config.format`), so the model cannot return prose or extra keys.
- **Validate before writing.** Line items must sum to the subtotal, subtotal + tax must equal total, due date cannot precede invoice date. The Python version retries once with the validation error fed back; the n8n version routes failures to the summary.
- **Scanned PDFs are detected and skipped**, not silently mis-read. Adding OCR (Tesseract or a vision model) is the obvious v2.
- **Cost per invoice:** about 1.5k input and 300 output tokens. On Claude Sonnet 5 that is about $0.006; on Haiku 4.5 about $0.003.

## What I learned building this

- n8n's Extract From File node handles PDF text with no code; the Code node is only needed for the guard and the reconciliation.
- Reconciliation catches most LLM mistakes: when totals do not add up, the model usually misread a quantity, and a second pass with the error message fixes it.
- Keeping a pure-Python twin made the logic testable with a fake LLM, which is what let this ship without spending API credit.
