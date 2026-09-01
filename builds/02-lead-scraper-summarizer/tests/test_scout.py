from pathlib import Path
import pytest
from pydantic import ValidationError
from leadscout.page import html_to_text
from leadscout.schema import LeadAssessment
from leadscout.scout import assess

FIX = Path(__file__).resolve().parent.parent / "sample-data" / "fixtures"


def test_html_to_text_strips_chrome_and_keeps_signal():
    p = html_to_text((FIX / "lawfirm.html").read_text())
    assert p["title"].startswith("Harbor & Pike Law")
    assert "239-555-0100" in p["description"]
    assert "Practice areas" in p["headings"]
    assert "var x=1" not in p["text"] and "Home About Contact" not in p["text"]
    assert "receptionist" in p["text"]


def test_text_is_capped():
    big = "<html><body>" + "word " * 10000 + "</body></html>"
    assert len(html_to_text(big)["text"]) <= 6000


def fake_llm(page, icp):
    fit = 9 if "attorney" in page["text"] else 2
    if fit == 9:
        return {"company": "Harbor & Pike Law", "summary": "Three-attorney family law firm in Fort Myers doing phone intake via a receptionist.",
                "fit_score": 9, "fit_reasons": ["phone intake", "small firm"],
                "opener": "Saw that your receptionist takes intake details and an attorney calls back within a day.", "red_flags": []}
    return {"company": "Loopwise", "summary": "Self-serve SaaS analytics company, 120 employees, no sales call needed.",
            "fit_score": 2, "fit_reasons": ["not a services business"],
            "opener": "Noticed Loopwise is fully self-serve with a free tier and no sales call.", "red_flags": ["self-serve product, no intake process"]}


@pytest.mark.parametrize("fixture,expected", [("lawfirm.html", 9), ("saas.html", 2)])
def test_assess_with_fake_fetch_and_llm(fixture, expected):
    def fetch(url):
        return {"url": url, **html_to_text((FIX / fixture).read_text())}
    a = assess("https://x.test", "small law firms that do intake by phone", llm=fake_llm, fetch=fetch)
    assert a.fit_score == expected
    assert a.company


def test_schema_rejects_out_of_range_score():
    with pytest.raises(ValidationError):
        LeadAssessment(company="x", summary="y" * 30, fit_score=11, fit_reasons=["a"], opener="z" * 30)
