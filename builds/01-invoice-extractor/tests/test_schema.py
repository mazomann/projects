import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from extractor.pdf_text import pdf_to_text
from extractor.schema import Invoice

SAMPLES = Path(__file__).resolve().parent.parent / "sample-data"
EXPECTED = json.loads((SAMPLES / "expected.json").read_text())


@pytest.mark.parametrize("exp", EXPECTED, ids=[e["file"] for e in EXPECTED])
def test_expected_samples_validate(exp):
    inv = Invoice(**{k: v for k, v in exp.items() if k != "file"})
    assert inv.total == exp["total"]
    row = inv.to_row()
    assert row["vendor"] == exp["vendor"] and ";" in row["line_items"] or len(exp["line_items"]) == 1


def test_rejects_mismatched_totals():
    bad = dict(EXPECTED[0])
    bad.pop("file")
    bad["total"] = bad["total"] + 10
    with pytest.raises(ValidationError, match="total"):
        Invoice(**bad)


def test_rejects_due_before_invoice():
    bad = dict(EXPECTED[0])
    bad.pop("file")
    bad["due_date"] = "2020-01-01"
    with pytest.raises(ValidationError, match="due_date"):
        Invoice(**bad)


def test_currency_normalised():
    ok = dict(EXPECTED[1])
    ok.pop("file")
    ok["currency"] = "usd"
    assert Invoice(**ok).currency == "USD"


@pytest.mark.parametrize("exp", EXPECTED, ids=[e["file"] for e in EXPECTED])
def test_pdf_text_contains_key_fields(exp):
    text = pdf_to_text(SAMPLES / exp["file"])
    assert exp["vendor"] in text
    assert exp["invoice_number"] in text
    assert f"{exp['total']:,.2f}" in text
