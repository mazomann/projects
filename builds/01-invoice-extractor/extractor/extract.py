"""PDF invoice -> validated Invoice. The LLM call is a plain function so it can be swapped or faked.

Usage:
    uv run python -m extractor.extract sample-data/inv-001.pdf            # prints JSON
    uv run python -m extractor.extract sample-data/*.pdf --csv out.csv    # one row per invoice
Env:
    ANTHROPIC_API_KEY   required for the real LLM call
    INVOICE_MODEL       default claude-sonnet-5
"""
from __future__ import annotations
import argparse, csv, json, os, sys
from pathlib import Path
from typing import Callable
from pydantic import ValidationError
from .pdf_text import pdf_to_text
from .schema import Invoice, JSON_SCHEMA

SYSTEM = (
    "You extract structured data from invoice text. Return only the fields in the schema. "
    "Dates as YYYY-MM-DD. Amounts as plain numbers without currency symbols. "
    "line_items amount = quantity * unit_price. subtotal = sum of amounts. total = subtotal + tax. "
    "If a field is genuinely absent use null (due_date) or 0 (tax). Do not invent values."
)

LLM = Callable[[str], dict]  # invoice text -> raw dict matching JSON_SCHEMA

def claude_llm(text: str) -> dict:
    """Real call: Claude structured output constrained to JSON_SCHEMA."""
    from anthropic import Anthropic
    client = Anthropic()  # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=os.environ.get("INVOICE_MODEL", "claude-sonnet-5"),
        max_tokens=2048,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"<invoice>\n{text}\n</invoice>"}],
        output_config={"format": {"type": "json_schema", "schema": JSON_SCHEMA}},
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("model refused the request")
    raw = next(b.text for b in resp.content if b.type == "text")
    return json.loads(raw)

def extract(pdf: str | Path, llm: LLM = claude_llm, retries: int = 1) -> Invoice:
    """Extract and validate. On a validation failure, retry once with the error fed back (LLMs fix arithmetic on a second pass)."""
    text = pdf_to_text(pdf)
    prompt = text
    last_err: Exception | None = None
    for _ in range(retries + 1):
        raw = llm(prompt)
        try:
            return Invoice(**raw)
        except ValidationError as e:
            last_err = e
            prompt = f"{text}\n\nYour previous extraction failed validation:\n{e}\nReturn a corrected extraction."
    raise last_err  # type: ignore[misc]

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--csv", help="append rows to this CSV instead of printing JSON")
    a = ap.parse_args(argv)
    rows, failures = [], 0
    for p in a.pdfs:
        try:
            inv = extract(p)
            rows.append(inv.to_row() | {"file": Path(p).name})
        except Exception as e:  # keep going; report at the end
            failures += 1
            print(f"FAILED {p}: {e}", file=sys.stderr)
    if a.csv:
        new = not Path(a.csv).exists()
        with open(a.csv, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["file"])
            if new: w.writeheader()
            w.writerows(rows)
        print(f"wrote {len(rows)} rows to {a.csv}, {failures} failed")
    else:
        print(json.dumps(rows, indent=2))
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
