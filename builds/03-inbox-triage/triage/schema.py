"""Triage decision per email. Categories drive what happens next:

  support      -> draft a reply for a human to send
  sales        -> draft a reply, tag as lead
  billing      -> never auto-drafted; a human must look
  spam         -> archive
  needs_human  -> anything sensitive, angry, legal, or ambiguous; Slack ping
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

Category = Literal["support", "sales", "billing", "spam", "needs_human"]
DRAFTABLE: set[str] = {"support", "sales"}


class Triage(BaseModel):
    category: Category
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=10, max_length=300, description="one line a busy owner can scan")
    urgency: Literal["low", "normal", "high"]
    draft_reply: str | None = Field(default=None, description="only for support/sales; null otherwise")
    reason: str = Field(min_length=5, max_length=300)

    def should_draft(self) -> bool:
        return self.category in DRAFTABLE and self.confidence >= 0.7 and bool(self.draft_reply)


JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["category", "confidence", "summary", "urgency", "draft_reply", "reason"],
    "properties": {
        "category": {"type": "string", "enum": ["support", "sales", "billing", "spam", "needs_human"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
        "urgency": {"type": "string", "enum": ["low", "normal", "high"]},
        "draft_reply": {"type": ["string", "null"]},
        "reason": {"type": "string"},
    },
}
