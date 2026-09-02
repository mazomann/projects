import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from triage.schema import Triage
from triage.triage import digest, triage_email

INBOX = json.loads((Path(__file__).resolve().parent.parent / "sample-data" / "inbox.json").read_text())
BY_ID = {e["id"]: e for e in INBOX}

# What a well-behaved model returns for each fixture; the tests check the policy layer around it.
FAKE = {
    "m1": {
        "category": "support",
        "confidence": 0.95,
        "summary": "Existing client locked out of portal after password resets.",
        "urgency": "normal",
        "draft_reply": (
            "Hi Dana, sorry about the lockout. I've flagged this to our team and someone will reset "
            "your access today. Could you confirm the email you use to sign in?"
        ),
        "reason": "existing customer, technical issue",
    },
    "m2": {
        "category": "sales",
        "confidence": 0.9,
        "summary": "6-person landscaping company wants monthly bookkeeping quote.",
        "urgency": "normal",
        "draft_reply": (
            "Hi Mike, thanks for reaching out. Monthly bookkeeping for a team your size is something "
            "we do often. Would Wednesday or Thursday afternoon work for a 20-minute call?"
        ),
        "reason": "new business enquiry",
    },
    "m3": {
        "category": "billing",
        "confidence": 0.92,
        "summary": "Vendor final notice: invoice 4471, $1,240 overdue 30 days.",
        "urgency": "high",
        "draft_reply": "We will pay this immediately.",
        "reason": "payment demand",
    },
    "m4": {
        "category": "spam",
        "confidence": 0.98,
        "summary": "Unsolicited AI lead-gen promotion.",
        "urgency": "low",
        "draft_reply": None,
        "reason": "marketing blast",
    },
    "m5": {
        "category": "needs_human",
        "confidence": 0.97,
        "summary": "Client angry about missed Friday report, mentions lawyer.",
        "urgency": "high",
        "draft_reply": None,
        "reason": "complaint with legal threat",
    },
}


def fake_llm(email, context):
    return dict(FAKE[email["id"]])


@pytest.mark.parametrize("mid", list(FAKE))
def test_categories_pass_through(mid):
    t = triage_email(BY_ID[mid], llm=fake_llm)
    assert t.category == FAKE[mid]["category"]


def test_billing_never_gets_a_draft_even_if_model_wrote_one():
    t = triage_email(BY_ID["m3"], llm=fake_llm)
    assert t.draft_reply is None


def test_low_confidence_escalates():
    def unsure(email, ctx):
        return {**FAKE["m1"], "confidence": 0.5}

    t = triage_email(BY_ID["m1"], llm=unsure)
    assert t.category == "needs_human" and t.draft_reply is None


def test_only_support_and_sales_draft():
    decisions = [(BY_ID[m], triage_email(BY_ID[m], llm=fake_llm)) for m in FAKE]
    assert {t.category for _, t in decisions if t.draft_reply} == {"support", "sales"}


def test_digest_orders_urgent_first_and_counts():
    decisions = [(BY_ID[m], triage_email(BY_ID[m], llm=fake_llm)) for m in FAKE]
    d = digest(decisions)
    assert d.startswith("Inbox digest: 5 emails, 2 need you, 2 drafts ready")
    needs = d.split("NEEDS YOU")[1].split("DRAFTS")[0]
    assert "Very disappointed" in needs and "Invoice 4471" in needs
    assert "spam 1" in d and "support 1" in d


def test_schema_rejects_unknown_category():
    with pytest.raises(ValidationError):
        Triage(category="other", confidence=0.9, summary="x" * 20, urgency="low", draft_reply=None, reason="because")
