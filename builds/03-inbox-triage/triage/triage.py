"""Classify emails, draft safe replies, build the daily digest.

Usage:
    uv run python -m triage.triage sample-data/inbox.json                # prints decisions + digest
Env: ANTHROPIC_API_KEY, TRIAGE_MODEL (default claude-sonnet-5), BUSINESS_CONTEXT (one paragraph about the business)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Callable
from .schema import Triage, JSON_SCHEMA

DEFAULT_CONTEXT = (
    "Small professional-services firm. Office hours Mon-Fri 9-5. Replies are warm, brief, and never promise "
    "prices, legal outcomes, or deadlines. Anything about invoices, refunds, complaints, legal threats, or "
    "personal data goes to a human."
)

SYSTEM_TEMPLATE = (
    "You triage a shared inbox for this business:\n{context}\n\n"
    "Classify each email into exactly one category: support (existing customer question), sales (new business "
    "enquiry), billing (invoices, payments, refunds), spam (unsolicited marketing, phishing, irrelevant), or "
    "needs_human (angry, legal, sensitive, ambiguous, or anything you are not confident about). "
    "For support and sales only, write a short reply draft in the business's voice that answers what you safely can "
    "and offers a next step; never invent facts, prices, or commitments. For every other category draft_reply is null. "
    "Confidence below 0.7 means needs_human."
)

LLM = Callable[[dict, str], dict]


def claude_llm(email: dict, context: str) -> dict:
    from anthropic import Anthropic
    client = Anthropic()
    resp = client.messages.create(
        model=os.environ.get("TRIAGE_MODEL", "claude-sonnet-5"),
        max_tokens=1024,
        system=SYSTEM_TEMPLATE.format(context=context),
        messages=[{"role": "user", "content": json.dumps(
            {k: email.get(k, "") for k in ("from", "subject", "date", "body")}, ensure_ascii=False)}],
        output_config={"format": {"type": "json_schema", "schema": JSON_SCHEMA}},
    )
    if resp.stop_reason == "refusal":
        return {"category": "needs_human", "confidence": 0.0, "summary": "model declined to process this email",
                "urgency": "normal", "draft_reply": None, "reason": "refusal"}
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


def triage_email(email: dict, context: str = DEFAULT_CONTEXT, llm: LLM = claude_llm) -> Triage:
    t = Triage(**llm(email, context))
    # Belt and braces: the schema allows a draft on any category, the policy does not.
    if t.category not in ("support", "sales"):
        t.draft_reply = None
    if t.confidence < 0.7 and t.category != "spam":
        t.category = "needs_human"
        t.draft_reply = None
    return t


def digest(decisions: list[tuple[dict, Triage]]) -> str:
    """Plain-text daily digest: what needs a human first, then drafts waiting, then counts."""
    counts = Counter(t.category for _, t in decisions)
    urgent = [(e, t) for e, t in decisions if t.category == "needs_human" or t.urgency == "high"]
    drafts = [(e, t) for e, t in decisions if t.should_draft()]
    lines = [f"Inbox digest: {len(decisions)} emails, {len(urgent)} need you, {len(drafts)} drafts ready"]
    if urgent:
        lines.append("\nNEEDS YOU")
        for e, t in sorted(urgent, key=lambda x: x[1].urgency != "high"):
            lines.append(f"  [{t.urgency}] {e.get('from', '?')}: {e.get('subject', '')}\n      {t.summary}")
    if drafts:
        lines.append("\nDRAFTS WAITING FOR APPROVAL")
        for e, t in drafts:
            lines.append(f"  ({t.category}) {e.get('from', '?')}: {e.get('subject', '')}")
    lines.append("\nBY CATEGORY  " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inbox", help="JSON list of {from, subject, date, body}")
    a = ap.parse_args(argv)
    emails = json.loads(Path(a.inbox).read_text(encoding="utf-8"))
    context = os.environ.get("BUSINESS_CONTEXT", DEFAULT_CONTEXT)
    decisions = []
    for e in emails:
        t = triage_email(e, context)
        decisions.append((e, t))
        print(f"{t.category:<12} {t.confidence:.2f} {t.urgency:<6} {e.get('subject', '')[:60]}", file=sys.stderr)
    print(digest(decisions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
