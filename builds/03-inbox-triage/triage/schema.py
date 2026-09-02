"""Triage decision per email. Categories drive what happens next:

support      -> draft a reply for a human to send
sales        -> draft a reply, tag as lead
billing      -> never auto-drafted; a human must look
spam         -> archive
needs_human  -> anything sensitive, angry, legal, or ambiguous; Slack ping

The policy the model cannot be trusted with lives in `enforce_policy`: no draft outside
support/sales, and anything under MIN_CONFIDENCE (except spam) escalates to a human.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, Field, model_validator

Category = Literal["support", "sales", "billing", "spam", "needs_human"]
Urgency = Literal["low", "normal", "high"]
DRAFTABLE = ("support", "sales")
MIN_CONFIDENCE = 0.7


class Triage(BaseModel):
    category: Category
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=10, max_length=300, description="one line a busy owner can scan")
    urgency: Urgency
    draft_reply: str | None = Field(default=None, description="only for support/sales; null otherwise")
    reason: str = Field(min_length=5, max_length=300)

    @model_validator(mode="after")
    def enforce_policy(self) -> Triage:
        if self.confidence < MIN_CONFIDENCE and self.category != "spam":
            self.category = "needs_human"
        if self.category not in DRAFTABLE:
            self.draft_reply = None
        return self


JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["category", "confidence", "summary", "urgency", "draft_reply", "reason"],
    "properties": {
        "category": {"type": "string", "enum": list(get_args(Category))},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
        "urgency": {"type": "string", "enum": list(get_args(Urgency))},
        "draft_reply": {"type": ["string", "null"]},
        "reason": {"type": "string"},
    },
}
