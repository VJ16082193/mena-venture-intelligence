"""
arabnet.py — Scraper for arabnet.me

ArabNet covers MENA digital economy news including funding, events, and reports.
"""

from datetime import date, datetime
from typing import Optional

from src.scraper.base_scraper import BaseScraper
from src.scraper.extractor import (
    compute_confidence, extract_amount, extract_country,
    extract_round_type, extract_sector, is_funding_article,
)
from src.scraper.currency import to_usd

SOURCE_NAME = "ArabNet"
BASE_URL = "https://www.arabnet.me"
NEWS_URL = f"{BASE_URL}/news"


class ArabNetScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_name=SOURCE_NAME, base_url=BASE_URL)

    def get_article_links(self) -> list[str]:
        soup = self.fetch(NEWS_URL)
        if not soup:
            return []

        links = []
        for tag in soup.select("a[href]"):
            href = tag.get("href", "")
            if not href:
                continue
            if href.startswith("/"):
                href = BASE_URL + href
            if BASE_URL in href and "/news/" in href:
                links.append(href)

        seen = set()
        return [x for x in links if not (x in seen or seen.add(x))][:25]

    def parse_article(self, url: str) -> Optional[dict]:
        soup = self.fetch(url)
        if not soup:
            return None

        title_tag = soup.select_one("h1")
        title_text = title_tag.get_text(strip=True) if title_tag else ""

        content = soup.select_one("div.article-content, div.content-body, main")
        body_text = content.get_text(separator=" ", strip=True) if content else ""

        if not is_funding_article(title_text, body_text):
            return None

        pub_date = None
        time_tag = soup.select_one("time[datetime], .published-date, .post-date")
        if time_tag:
            try:
                dt_str = time_tag.get("datetime") or time_tag.get_text(strip=True)
                pub_date = datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
            except Exception:
                pass

        full_text = title_text + " " + body_text
        amount, currency = extract_amount(full_text)
        amount_usd = to_usd(amount, currency) if (amount and currency) else None

        import re
        startup_name = None
        m = re.search(
            r"^([A-Z][A-Za-z0-9\.\-\s]{1,40}?)\s+(?:raises|secures|closes|receives|gets)",
            title_text
        )
        if m:
            startup_name = m.group(1).strip()

        record = {
            "url": url,
            "title": title_text,
            "source": SOURCE_NAME,
            "publication_date": pub_date or date.today(),
            "raw_content": body_text[:5000],
            "startup_name": startup_name,
            "country": extract_country(full_text),
            "sector": extract_sector(full_text),
            "round_type": extract_round_type(full_text),
            "amount_raw": amount,
            "currency": currency,
            "amount_usd": amount_usd,
            "investors": [],
        }
        record["confidence"] = compute_confidence(record)
        return record
