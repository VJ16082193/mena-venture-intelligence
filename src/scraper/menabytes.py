"""
menabytes.py — Scraper for menabytes.com

MENAbytes is the primary English-language source for MENA startup funding news.
The site uses a standard WordPress structure with a /category/funding/ listing page.
"""

from datetime import date, datetime
from typing import Optional

from loguru import logger

from src.scraper.base_scraper import BaseScraper
from src.scraper.extractor import (
    compute_confidence,
    extract_amount,
    extract_country,
    extract_round_type,
    extract_sector,
    infer_investor_type,
    is_funding_article,
)
from src.scraper.currency import to_usd

SOURCE_NAME = "MENAbytes"
BASE_URL = "https://www.menabytes.com"
FUNDING_URL = f"{BASE_URL}/category/funding/"


class MENABytesScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_name=SOURCE_NAME, base_url=BASE_URL)

    def get_article_links(self) -> list[str]:
        """Parse the /category/funding/ listing page and extract article URLs."""
        soup = self.fetch(FUNDING_URL)
        if not soup:
            return []

        links = []
        # MENAbytes uses <h2 class="entry-title"> for article titles in listings
        for tag in soup.select("h2.entry-title a, h3.entry-title a"):
            href = tag.get("href", "")
            if href and href.startswith("http") and BASE_URL in href:
                links.append(href)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique.append(link)

        return unique[:30]  # Process latest 30 articles per run

    def parse_article(self, url: str) -> Optional[dict]:
        """Extract structured funding data from a single MENAbytes article."""
        soup = self.fetch(url)
        if not soup:
            return None

        title = soup.select_one("h1.entry-title")
        title_text = title.get_text(strip=True) if title else ""

        content_div = soup.select_one("div.entry-content, div.post-content")
        body_text = content_div.get_text(separator=" ", strip=True) if content_div else ""

        if not is_funding_article(title_text, body_text):
            return None

        # Publication date
        pub_date = None
        time_tag = soup.select_one("time.entry-date, time[datetime]")
        if time_tag:
            try:
                dt_str = time_tag.get("datetime", "")
                pub_date = datetime.fromisoformat(dt_str[:10]).date()
            except Exception:
                pass

        # Core extraction
        full_text = title_text + " " + body_text
        amount, currency = extract_amount(full_text)
        amount_usd = to_usd(amount, currency) if (amount and currency) else None
        round_type = extract_round_type(full_text)
        country = extract_country(full_text)
        sector = extract_sector(full_text)

        # Startup name heuristic: first bolded entity or first proper noun after "raised"
        startup_name = _extract_startup_name(soup, title_text)

        # Investor extraction
        investors = _extract_investors(body_text)

        record = {
            "url": url,
            "title": title_text,
            "source": SOURCE_NAME,
            "publication_date": pub_date or date.today(),
            "raw_content": body_text[:5000],
            "startup_name": startup_name,
            "country": country,
            "sector": sector,
            "round_type": round_type,
            "amount_raw": amount,
            "currency": currency,
            "amount_usd": amount_usd,
            "investors": investors,
        }
        record["confidence"] = compute_confidence(record)
        return record


# ── Private helpers ───────────────────────────────────────────────────────────

def _extract_startup_name(soup, title_text: str) -> Optional[str]:
    """
    Attempt to extract startup name from:
    1. First <strong> tag in article body
    2. Title heuristic: word(s) before 'raises', 'secures', 'closes'
    """
    import re

    # Try bold tags in body first
    strong = soup.select_one("div.entry-content strong")
    if strong:
        name = strong.get_text(strip=True)
        if 2 <= len(name) <= 60 and name[0].isupper():
            return name

    # Title heuristic
    patterns = [
        r"^([A-Z][A-Za-z0-9\.\-\s]{1,40}?)\s+(?:raises|secures|closes|gets|lands|receives)",
        r"^([A-Z][A-Za-z0-9\.\-\s]{1,40}?),?\s+(?:a|an|the)\s+\w+\s+startup",
    ]
    for p in patterns:
        m = re.search(p, title_text)
        if m:
            return m.group(1).strip()

    return None


def _extract_investors(text: str) -> list[dict]:
    """
    Extract investor names from common patterns like:
    "led by [Investor]", "backed by [Investor]", "investors include [A], [B]"
    Returns list of {name: str, lead: bool}
    """
    import re

    investors = []
    seen = set()

    # Lead investor patterns
    lead_patterns = [
        r"led\s+by\s+([A-Z][A-Za-z0-9\s\.\-&,]{3,60}?)(?:\s+with|\s+and|\s*[,\.])",
        r"lead\s+investor[:\s]+([A-Z][A-Za-z0-9\s\.\-&]{3,60}?)(?:\s*[,\.])",
    ]
    for p in lead_patterns:
        m = re.search(p, text)
        if m:
            name = m.group(1).strip().rstrip(",.")
            if name and name not in seen:
                seen.add(name)
                investors.append({"name": name, "lead": True, "type": infer_investor_type(name)})

    # Participation patterns
    participation_patterns = [
        r"participation\s+(?:from|of)\s+([A-Z][A-Za-z0-9\s\.\-&,]{3,120}?)(?:\s*\.|\s*\n)",
        r"investors\s+include\s+([A-Z][A-Za-z0-9\s\.\-&,]{3,200}?)(?:\s*\.|\s*\n)",
        r"backed\s+by\s+([A-Z][A-Za-z0-9\s\.\-&,]{3,120}?)(?:\s*\.|\s*\n)",
    ]
    for p in participation_patterns:
        m = re.search(p, text)
        if m:
            # Split on commas and "and"
            raw = m.group(1)
            names = re.split(r",\s*|\s+and\s+", raw)
            for name in names:
                name = name.strip().rstrip(",.")
                if len(name) >= 3 and name not in seen and name[0].isupper():
                    seen.add(name)
                    investors.append({"name": name, "lead": False, "type": infer_investor_type(name)})

    return investors[:10]  # Cap at 10 investors per article
