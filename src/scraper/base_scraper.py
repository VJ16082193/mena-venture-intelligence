"""
base_scraper.py — Abstract base class for all source-specific scrapers.

Each scraper implementation must:
  1. Override get_article_links() to return a list of article URLs
  2. Override parse_article() to return a structured dict from a single URL
"""

import time
from abc import ABC, abstractmethod
from typing import Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger


class BaseScraper(ABC):
    """
    Base HTTP scraper with rate limiting, session reuse, and error isolation.

    Subclasses implement `get_article_links` and `parse_article` for each source.
    """

    USER_AGENT = "MENAVentureBot/1.0 (Research Intelligence Tool; non-commercial)"

    def __init__(self, source_name: str, base_url: str, delay: float = 2.0):
        self.source_name = source_name
        self.base_url = base_url
        self.delay = delay

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    # ── Abstract interface ─────────────────────────────────────────────────────

    @abstractmethod
    def get_article_links(self) -> list[str]:
        """
        Fetch the index / RSS / listing page for this source and return
        a list of individual article URLs to process.
        """
        ...

    @abstractmethod
    def parse_article(self, url: str) -> Optional[dict]:
        """
        Fetch a single article URL and return a structured dict, or None
        if the article is not a funding announcement.

        Expected keys (all optional except url/title/source/publication_date):
            url, title, source, publication_date,
            startup_name, country, sector, founded_year, description,
            round_type, amount_raw, currency, amount_usd,
            investors (list of {name, lead}),
            confidence (int 0-100)
        """
        ...

    # ── Shared utilities ──────────────────────────────────────────────────────

    def fetch(self, url: str) -> Optional[BeautifulSoup]:
        """
        Perform a rate-limited GET request and return a BeautifulSoup object.
        Returns None on network/HTTP errors (caller decides how to handle).
        """
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            time.sleep(self.delay)
            return BeautifulSoup(resp.text, "lxml")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"[{self.source_name}] HTTP {e.response.status_code} — {url}")
        except requests.exceptions.Timeout:
            logger.warning(f"[{self.source_name}] Timeout — {url}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[{self.source_name}] Request failed — {url}: {e}")
        return None

    def scrape_all(self) -> list[dict]:
        """
        Orchestrate a full scrape: fetch links → parse each article.
        Returns a list of structured article dicts (None results are dropped).
        """
        logger.info(f"[{self.source_name}] Starting scrape")
        links = []
        try:
            links = self.get_article_links()
        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch article links: {e}")
            return []

        logger.info(f"[{self.source_name}] Found {len(links)} article links")
        results = []
        for url in links:
            try:
                parsed = self.parse_article(url)
                if parsed:
                    results.append(parsed)
            except Exception as e:
                logger.error(f"[{self.source_name}] Failed to parse {url}: {e}")

        logger.info(f"[{self.source_name}] Extracted {len(results)} funding articles")
        return results
