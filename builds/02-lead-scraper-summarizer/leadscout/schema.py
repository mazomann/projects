"""What the LLM returns per company, and the JSON schema that constrains it."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LeadAssessment(BaseModel):
    company: str = Field(min_length=1)
    summary: str = Field(
        min_length=20, max_length=600, description="3 lines: what they do, who for, any signal of scale"
    )
    fit_score: int = Field(ge=1, le=10)
    fit_reasons: list[str] = Field(min_length=1, max_length=4)
    opener: str = Field(
        min_length=20,
        max_length=400,
        description="one personalised sentence referencing something specific on their site",
    )
    red_flags: list[str] = Field(default_factory=list)


JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["company", "summary", "fit_score", "fit_reasons", "opener", "red_flags"],
    "properties": {
        "company": {"type": "string"},
        "summary": {"type": "string"},
        "fit_score": {"type": "integer", "minimum": 1, "maximum": 10},
        "fit_reasons": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "opener": {"type": "string"},
        "red_flags": {"type": "array", "items": {"type": "string"}},
    },
}
