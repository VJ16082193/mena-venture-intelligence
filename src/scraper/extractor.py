"""
extractor.py — Regex and keyword-based extraction of structured funding data
from raw article text.

All extraction is deterministic and testable. No external NLP dependencies
required for the base implementation.
"""

import re
from datetime import date
from typing import Optional

# ── Controlled vocabularies ────────────────────────────────────────────────────

ROUND_TYPES: list[tuple[str, str]] = [
    # (search_pattern, canonical_label)
    (r"\bpre[\s\-]?seed\b", "Pre-seed"),
    (r"\bseed\b", "Seed"),
    (r"\bseries\s+d\b", "Series D"),
    (r"\bseries\s+c\b", "Series C"),
    (r"\bseries\s+b\b", "Series B"),
    (r"\bseries\s+a\b", "Series A"),
    (r"\bgrowth[\s\-]?round\b", "Growth"),
    (r"\bbridge[\s\-]?round\b", "Bridge"),
    (r"\bventure[\s\-]?debt\b", "Venture Debt"),
    (r"\bdebt[\s\-]?financing\b", "Venture Debt"),
    (r"\bipo\b", "IPO"),
    (r"\bacquisition\b", "Acquisition"),
    (r"\bgrant\b", "Grant"),
]

MENA_COUNTRIES: dict[str, list[str]] = {
    "UAE": ["uae", "dubai", "abu dhabi", "sharjah", "ajman", "ras al khaimah", "united arab emirates"],
    "Saudi Arabia": ["saudi", "ksa", "riyadh", "jeddah", "dammam", "mecca", "medina", "saudi arabia"],
    "Egypt": ["egypt", "cairo", "alexandria", "giza"],
    "Qatar": ["qatar", "doha"],
    "Bahrain": ["bahrain", "manama"],
    "Kuwait": ["kuwait", "kuwait city"],
    "Jordan": ["jordan", "amman"],
    "Lebanon": ["lebanon", "beirut"],
    "Iraq": ["iraq", "baghdad"],
    "Morocco": ["morocco", "casablanca", "rabat"],
    "Tunisia": ["tunisia", "tunis"],
}

SECTOR_MAP: dict[str, list[str]] = {
    "Fintech": ["fintech", "payments", "neobank", "neo-bank", "lending", "insurtech", "wealthtech",
                "remittance", "banking", "financial technology", "digital banking", "buy now pay later",
                "bnpl", "digital wallet"],
    "E-commerce": ["e-commerce", "ecommerce", "marketplace", "retail tech", "d2c", "direct to consumer",
                   "social commerce", "online retail", "quick commerce"],
    "Healthtech": ["healthtech", "health tech", "digital health", "telemedicine", "medtech",
                   "pharmatech", "healthtech", "telehealth", "medical technology"],
    "Edtech": ["edtech", "ed-tech", "education technology", "e-learning", "elearning", "upskilling",
               "online learning", "coding bootcamp"],
    "Logistics": ["logistics", "supply chain", "last-mile", "delivery", "fleet management",
                  "warehousing", "freight", "fulfillment"],
    "Proptech": ["proptech", "prop tech", "real estate tech", "construction tech", "facility management",
                 "smart building"],
    "Agritech": ["agritech", "agri-tech", "agriculture tech", "food tech", "foodtech", "farm management",
                 "agri", "precision farming"],
    "SaaS / Enterprise": ["saas", "b2b software", "enterprise software", "hr tech", "hrtech", "erp",
                          "crm", "cloud software", "api", "developer tools"],
    "Energy / Cleantech": ["cleantech", "clean tech", "solar", "renewable", "ev charging", "climate tech",
                           "sustainability", "green tech", "energy tech"],
    "Gaming / Entertainment": ["gaming", "game studio", "esports", "streaming", "media tech",
                               "entertainment tech", "content platform"],
    "Mobility": ["mobility", "ride hailing", "ride-hailing", "autonomous vehicle", "ev startup",
                 "transportation", "micromobility"],
    "Cybersecurity": ["cybersecurity", "cyber security", "infosec", "security tech", "data security"],
    "AI / ML": ["artificial intelligence", "machine learning", "ai startup", "deep learning",
                "nlp", "computer vision", "generative ai"],
}

INVESTOR_TYPE_KEYWORDS: dict[str, list[str]] = {
    "VC": ["ventures", "capital", "fund", "partners", "invest", "venture"],
    "Corporate": ["corp", "group", "holding", "inc", "ltd", "technologies", "solutions"],
    "Government": ["government", "authority", "ministry", "sovereign", "national fund", "sdaia"],
    "Angel": [],  # Default fallback if no other type matched
    "Family Office": ["family office", "family investment"],
}


# ── Amount extraction ─────────────────────────────────────────────────────────

_AMOUNT_PATTERN = re.compile(
    r"[\$£€]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*"
    r"(billion|million|bn|mn|b|m)\b",
    re.IGNORECASE,
)

_CURRENCY_PATTERN = re.compile(
    r"\b(USD|AED|SAR|EGP|QAR|KWD|BHD|OMR|EUR|GBP)\b",
    re.IGNORECASE,
)


def extract_amount(text: str) -> tuple[Optional[float], Optional[str]]:
    """
    Extract the first monetary amount from text.
    Returns (raw_amount_in_units, currency_string) or (None, None).

    Examples:
        "$5 million"      → (5_000_000.0, "USD")
        "AED 20 million"  → (20_000_000.0, "AED")
        "SR 100m"         → (100_000_000.0, None)
    """
    match = _AMOUNT_PATTERN.search(text)
    if not match:
        return None, None

    raw = float(match.group(1).replace(",", ""))
    unit = match.group(2).lower()
    multiplier = 1_000_000_000 if unit in ("billion", "bn", "b") else 1_000_000
    amount = raw * multiplier

    # Try to find a currency symbol/code nearby (within 30 chars of match)
    start = max(0, match.start() - 30)
    snippet = text[start : match.end() + 10]

    currency = "USD"  # default assumption for MENA tech press
    if "$" in snippet or "USD" in snippet.upper():
        currency = "USD"
    elif "AED" in snippet.upper() or "Dh" in snippet or "دH" in snippet:
        currency = "AED"
    elif "SAR" in snippet.upper() or "SR" in snippet or "﷼" in snippet:
        currency = "SAR"
    elif "EGP" in snippet.upper() or "LE" in snippet:
        currency = "EGP"
    elif "QAR" in snippet.upper():
        currency = "QAR"
    elif "KWD" in snippet.upper():
        currency = "KWD"
    elif "BHD" in snippet.upper():
        currency = "BHD"
    else:
        cc = _CURRENCY_PATTERN.search(snippet)
        if cc:
            currency = cc.group(1).upper()

    return amount, currency


def extract_round_type(text: str) -> Optional[str]:
    """Return the most specific matching round type label, or None."""
    text_lower = text.lower()
    for pattern, label in ROUND_TYPES:
        if re.search(pattern, text_lower):
            return label
    return None


def extract_country(text: str) -> Optional[str]:
    """Return the first matching MENA country, or None."""
    text_lower = text.lower()
    for country, keywords in MENA_COUNTRIES.items():
        for kw in keywords:
            if kw in text_lower:
                return country
    return None


def extract_sector(text: str) -> Optional[str]:
    """Return the first matching sector from the controlled vocabulary, or None."""
    text_lower = text.lower()
    for sector, keywords in SECTOR_MAP.items():
        for kw in keywords:
            if kw in text_lower:
                return sector
    return None


def infer_investor_type(name: str) -> str:
    """Heuristically infer investor type from name tokens."""
    name_lower = name.lower()
    for inv_type, keywords in INVESTOR_TYPE_KEYWORDS.items():
        if inv_type == "Angel":
            continue
        for kw in keywords:
            if kw in name_lower:
                return inv_type
    return "Angel"


def is_funding_article(title: str, body: str) -> bool:
    """
    Quick gate: returns True if the article is likely a funding announcement.
    Avoids wasting extraction effort on non-funding stories.
    """
    funding_signals = [
        r"\braise[sd]?\b", r"\bfunding\b", r"\binvestment\b", r"\bsecures?\b",
        r"\bclosed?\b.*\bround\b", r"\bseries\s+[a-d]\b", r"\bseed\s+round\b",
        r"\bventure\b", r"\bcapital\b.*\bmillion\b", r"\bmillion\b.*\bfund\b",
    ]
    combined = (title + " " + body[:500]).lower()
    matches = sum(1 for p in funding_signals if re.search(p, combined))
    return matches >= 2


def compute_confidence(record: dict) -> int:
    """
    Score a partially-extracted record 0–100.
    Each critical field adds points; presence of all key fields = high confidence.
    """
    score = 0
    if record.get("startup_name"):
        score += 25
    if record.get("round_type"):
        score += 20
    if record.get("amount_usd"):
        score += 20
    if record.get("announcement_date"):
        score += 15
    if record.get("country"):
        score += 10
    if record.get("investors"):
        score += 10
    return min(score, 100)
