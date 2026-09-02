"""Score a list of company URLs against an ideal customer profile (ICP).

Usage:
    uv run python -m leadscout.scout urls.txt --csv leads.csv \
        --icp "small law firms in Florida that still do intake by phone"
    uv run python -m leadscout.scout urls.txt --icp "..." --hubspot     # also create companies (HUBSPOT_TOKEN)
Env: ANTHROPIC_API_KEY, LEAD_MODEL (default claude-sonnet-5), HUBSPOT_TOKEN (private app token)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

from .page import scrape
from .schema import JSON_SCHEMA, LeadAssessment

SYSTEM = (
    "You are a sales researcher. Given the text of a company website and an ideal customer profile (ICP), "
    "write a 3-line factual summary, score fit 1-10 (10 = textbook ICP match), give up to 4 concrete reasons, "
    "and write ONE opener sentence that references something specific from their site. "
    "Never invent facts that are not on the page. If the page is not a company site, score 1 and say why in red_flags."
)

LLM = Callable[[dict, str], dict]


def claude_llm(page: dict, icp: str) -> dict:
    from anthropic import Anthropic

    client = Anthropic()
    content = json.dumps({"icp": icp, "page": page}, ensure_ascii=False)
    resp = client.messages.create(
        model=os.environ.get("LEAD_MODEL", "claude-sonnet-5"),
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
        output_config={"format": {"type": "json_schema", "schema": JSON_SCHEMA}},
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("model refused")
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


def assess(url: str, icp: str, llm: LLM = claude_llm, fetch: Callable[[str], dict] = scrape) -> LeadAssessment:
    page = fetch(url)
    return LeadAssessment(**llm(page, icp))


def hubspot_upsert(a: LeadAssessment, url: str, token: str) -> str:
    """Create a company in HubSpot with the score as a custom property. Returns the record id."""
    import httpx

    domain = url.split("//", 1)[-1].split("/", 1)[0].removeprefix("www.")
    body = {
        "properties": {
            "name": a.company,
            "domain": domain,
            "description": a.summary,
            "lead_fit_score": a.fit_score,
            "lead_opener": a.opener,
        }
    }
    r = httpx.post(
        "https://api.hubapi.com/crm/v3/objects/companies",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["id"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", help="text file, one URL per line")
    ap.add_argument("--icp", required=True)
    ap.add_argument("--csv", default="leads.csv")
    ap.add_argument("--hubspot", action="store_true")
    ap.add_argument("--max", type=int, default=50, help="cost cap: max URLs per run")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between fetches (be polite)")
    a = ap.parse_args(argv)
    urls = [u.strip() for u in Path(a.urls).read_text().splitlines() if u.strip() and not u.startswith("#")][: a.max]
    token = os.environ.get("HUBSPOT_TOKEN")
    rows, failed = [], 0
    for i, u in enumerate(urls):
        try:
            r = assess(u, a.icp)
            row = {"url": u, **r.model_dump()}
            row["fit_reasons"] = " | ".join(r.fit_reasons)
            row["red_flags"] = " | ".join(r.red_flags)
            if a.hubspot and token:
                row["hubspot_id"] = hubspot_upsert(r, u, token)
            rows.append(row)
            print(f"[{i + 1}/{len(urls)}] {r.fit_score:>2}  {r.company}", file=sys.stderr)
        except Exception as e:
            failed += 1
            print(f"[{i + 1}/{len(urls)}] FAILED {u}: {e}", file=sys.stderr)
        if i < len(urls) - 1:
            time.sleep(a.delay)
    rows.sort(key=lambda r: -r["fit_score"])
    if rows:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"{len(rows)} scored, {failed} failed -> {a.csv}")
    return 1 if failed and not rows else 0


if __name__ == "__main__":
    sys.exit(main())
