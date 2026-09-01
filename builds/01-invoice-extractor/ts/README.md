# Invoice extractor, TypeScript twin

Same pipeline as the Python package in `../extractor/`, written for Node 24:

```
PDF -> pdfToText (scanned guard) -> Claude structured output (JSON_SCHEMA) -> zod Invoice (totals reconciled) -> toRow()
```

## Run

```bash
npm install
npm test                                                   # 26 vitest tests, fake LLM, no key
npx tsc --noEmit                                           # typecheck
export ANTHROPIC_API_KEY=sk-ant-...                        # real extraction
npm run extract -- ../sample-data/inv-001.pdf              # prints JSON
npm run extract -- ../sample-data/*.pdf --csv out.csv      # one row per invoice, appended
npm run build && node dist/cli.js ../sample-data/inv-001.pdf
```

`INVOICE_MODEL` overrides the model (default `claude-sonnet-5`).

## How it mirrors the Python version

| Python | TypeScript | Notes |
|---|---|---|
| `extractor/schema.py` `Invoice` (pydantic) | `src/schema.ts` `Invoice` (zod) | Same field rules; `superRefine` does the reconciliation: line items sum to subtotal (+-0.02), subtotal + tax == total (+-0.02), due_date not before invoice_date, currency uppercased |
| `JSON_SCHEMA` | `JSON_SCHEMA` | Identical object; a test parses the Python literal and compares |
| `Invoice.to_row()` | `toRow(inv)` | Same keys and `"4 x desc @ 38.50; ..."` line-item format |
| `extractor/pdf_text.py` (pypdf) | `src/pdfText.ts` (pdf-parse 2.x) | Throws if under 40 chars of text |
| `extractor/extract.py` `extract(pdf, llm, retries=1)` | `src/extract.ts` `extract(pdfPath, llm = claudeLlm, retries = 1)` | `llm: (text) => Promise<unknown>`; on zod failure the error text is appended to the prompt and the LLM is called once more |
| `claude_llm` | `claudeLlm` | Same request: `messages.create` with `system`, `<invoice>` user message, `output_config.format = {type: "json_schema", schema}`; refusal stop reason raised |
| `python -m extractor.extract paths... --csv out.csv` | `npm run extract -- paths... --csv out.csv` | Same output, same exit code (1 if any file failed) |
| `tests/` (pytest) | `tests/` (vitest) | Same cases, plus a JSON_SCHEMA parity test and a `retries=0` test |

Errors thrown on validation are `ZodError` (the pydantic `ValidationError` equivalent); `formatZodError()` renders them one issue per line, which is what gets fed back to the model on retry.
