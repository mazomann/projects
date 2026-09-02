"""Pipeline tests with a fake LLM: no API key, no network."""

import json
from pathlib import Path

import pytest

from extractor.extract import extract

SAMPLES = Path(__file__).resolve().parent.parent / "sample-data"
EXPECTED = {
    e["file"]: {k: v for k, v in e.items() if k != "file"} for e in json.loads((SAMPLES / "expected.json").read_text())
}


def fake_llm_for(name):
    def llm(text):
        return dict(EXPECTED[name])

    return llm


@pytest.mark.parametrize("name", list(EXPECTED))
def test_extract_end_to_end_with_fake_llm(name):
    inv = extract(SAMPLES / name, llm=fake_llm_for(name))
    assert inv.total == EXPECTED[name]["total"]
    assert inv.vendor == EXPECTED[name]["vendor"]


def test_retry_feeds_validation_error_back():
    calls = []

    def flaky(text):
        calls.append(text)
        raw = dict(EXPECTED["inv-001.pdf"])
        if len(calls) == 1:
            raw["total"] = 1.0  # wrong on first pass
        return raw

    inv = extract(SAMPLES / "inv-001.pdf", llm=flaky)
    assert len(calls) == 2
    assert "failed validation" in calls[1]
    assert inv.total == EXPECTED["inv-001.pdf"]["total"]


def test_gives_up_after_retry():
    def always_wrong(text):
        raw = dict(EXPECTED["inv-001.pdf"])
        raw["total"] = 1.0
        return raw

    with pytest.raises(Exception, match="total"):
        extract(SAMPLES / "inv-001.pdf", llm=always_wrong)


def test_scanned_pdf_detected(tmp_path):
    from reportlab.pdfgen import canvas

    p = tmp_path / "blank.pdf"
    c = canvas.Canvas(str(p))
    c.showPage()
    c.save()
    with pytest.raises(ValueError, match="scanned"):
        extract(p, llm=lambda t: {})
