"""Fetch a company homepage and reduce it to the text an analyst would read: title, meta description, headings, visible copy."""
from __future__ import annotations
import re
import httpx
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; lead-scout/0.1; +https://github.com/mazomann/ai-automation-portfolio)"
MAX_CHARS = 6000  # enough for a homepage; keeps token cost flat


def fetch_html(url: str, timeout: float = 15.0) -> str:
    with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": UA}) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.text


def html_to_text(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "nav", "footer", "iframe"]):
        t.decompose()
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    desc = ""
    m = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if m and m.get("content"):
        desc = m["content"].strip()
    heads = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])][:20]
    body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:MAX_CHARS]
    return {"title": title, "description": desc, "headings": heads, "text": body}


def scrape(url: str) -> dict:
    return {"url": url, **html_to_text(fetch_html(url))}
