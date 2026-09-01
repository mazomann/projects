"""Invoice schema and validation. Shared by the CLI and the tests; mirrors the JSON schema sent to the LLM."""
from __future__ import annotations
from datetime import date
from pydantic import BaseModel, Field, field_validator, model_validator

class LineItem(BaseModel):
    description: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    amount: float = Field(ge=0)

class Invoice(BaseModel):
    vendor: str = Field(min_length=1)
    invoice_number: str = Field(min_length=1)
    invoice_date: date
    due_date: date | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    subtotal: float = Field(ge=0)
    tax: float = Field(ge=0)
    total: float = Field(ge=0)
    line_items: list[LineItem] = Field(min_length=1)

    @field_validator("currency")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def reconcile(self) -> "Invoice":
        """Totals must add up. Catches the most common LLM extraction mistakes."""
        items = round(sum(li.amount for li in self.line_items), 2)
        if abs(items - self.subtotal) > 0.02:
            raise ValueError(f"line items sum to {items}, subtotal says {self.subtotal}")
        if abs(round(self.subtotal + self.tax, 2) - self.total) > 0.02:
            raise ValueError(f"subtotal {self.subtotal} + tax {self.tax} != total {self.total}")
        if self.due_date and self.due_date < self.invoice_date:
            raise ValueError("due_date before invoice_date")
        return self

    def to_row(self) -> dict:
        """Flat row for a spreadsheet: one row per invoice, line items joined."""
        return {
            "vendor": self.vendor,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else "",
            "currency": self.currency,
            "subtotal": self.subtotal,
            "tax": self.tax,
            "total": self.total,
            "line_items": "; ".join(f"{li.quantity:g} x {li.description} @ {li.unit_price:.2f}" for li in self.line_items),
        }

# JSON schema handed to the LLM (strict: no extra keys, everything required so nothing is silently skipped).
JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["vendor", "invoice_number", "invoice_date", "due_date", "currency", "subtotal", "tax", "total", "line_items"],
    "properties": {
        "vendor": {"type": "string"},
        "invoice_number": {"type": "string"},
        "invoice_date": {"type": "string", "description": "ISO 8601 date, YYYY-MM-DD"},
        "due_date": {"type": ["string", "null"], "description": "ISO 8601 date or null if absent"},
        "currency": {"type": "string", "description": "ISO 4217 code, e.g. USD"},
        "subtotal": {"type": "number"},
        "tax": {"type": "number"},
        "total": {"type": "number"},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["description", "quantity", "unit_price", "amount"],
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit_price": {"type": "number"},
                    "amount": {"type": "number"},
                },
            },
        },
    },
}
