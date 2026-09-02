"""Fetch a company homepage and reduce it to the text an analyst would read.

Keeps the title, meta description, headings and visible copy.
"""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup, Tag

UA = "Mozilla/5.0 (compatible; lead-scout/0.1; +https://github.com/mazomann/projects)"
MAX_CHARS = 6000  # enough for a homepage; keeps token cost flat
TIMEOUT = 15.0


def fetch_html(url: str) -> str:
    with httpx.Client(follow_redirects=True, timeout=TIMEOUT, headers={"User-Agent": UA}) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.text


def html_to_text(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "nav", "footer", "iframe"]):
        t.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    m = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    content = m.get("content") if isinstance(m, Tag) else None
    desc = content.strip() if isinstance(content, str) else ""
    heads = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])][:20]
    body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:MAX_CHARS]
    return {"title": title, "description": desc, "headings": heads, "text": body}


def scrape(url: str) -> dict:
    return {"url": url, **html_to_text(fetch_html(url))}
