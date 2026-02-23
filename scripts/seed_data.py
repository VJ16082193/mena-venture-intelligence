"""
scripts/seed_data.py — Seed the database with sample historical data for development/testing.

This does NOT scrape. It inserts representative MENA funding records directly
so the dashboard is usable before the pipeline has run enough to accumulate real data.

Usage:
    python scripts/seed_data.py
    python scripts/seed_data.py --clear   # Drop all data first
"""

import argparse
import sys
import os
from datetime import date, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import text

load_dotenv()

logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")

# ── Sample data ────────────────────────────────────────────────────────────────

SAMPLE_STARTUPS = [
    {"name": "Tabby", "country": "UAE", "sector": "Fintech", "description": "BNPL platform"},
    {"name": "Tamara", "country": "Saudi Arabia", "sector": "Fintech", "description": "Buy now, pay later"},
    {"name": "Trella", "country": "Egypt", "sector": "Logistics", "description": "Freight marketplace"},
    {"name": "Eyewa", "country": "UAE", "sector": "E-commerce", "description": "Eyewear e-commerce"},
    {"name": "Pure Harvest", "country": "UAE", "sector": "Agritech", "description": "Smart farms"},
    {"name": "Vezeeta", "country": "Egypt", "sector": "Healthtech", "description": "Digital health"},
    {"name": "Aqar", "country": "Saudi Arabia", "sector": "Proptech", "description": "Real estate platform"},
    {"name": "Foodics", "country": "Saudi Arabia", "sector": "SaaS / Enterprise", "description": "Restaurant POS"},
    {"name": "Anghami", "country": "UAE", "sector": "Gaming / Entertainment", "description": "Music streaming"},
    {"name": "Sarwa", "country": "UAE", "sector": "Fintech", "description": "Robo-advisor"},
    {"name": "Halan", "country": "Egypt", "sector": "Fintech", "description": "Microfinance & mobility"},
    {"name": "Unifonic", "country": "Saudi Arabia", "sector": "SaaS / Enterprise", "description": "CPaaS platform"},
    {"name": "ElasticRun", "country": "UAE", "sector": "Logistics", "description": "Rural commerce"},
    {"name": "Alef Education", "country": "UAE", "sector": "Edtech", "description": "K-12 digital learning"},
    {"name": "GreenTech Arabia", "country": "Saudi Arabia", "sector": "Energy / Cleantech", "description": "Solar solutions"},
]

SAMPLE_INVESTORS = [
    {"name": "STV", "type": "VC", "country": "Saudi Arabia"},
    {"name": "BECO Capital", "type": "VC", "country": "UAE"},
    {"name": "Wamda Capital", "type": "VC", "country": "UAE"},
    {"name": "500 Global", "type": "VC", "country": "USA"},
    {"name": "Global Ventures", "type": "VC", "country": "UAE"},
    {"name": "Shorooq Partners", "type": "VC", "country": "UAE"},
    {"name": "Flat6Labs", "type": "VC", "country": "Egypt"},
    {"name": "Algebra Ventures", "type": "VC", "country": "Egypt"},
    {"name": "Vision Ventures", "type": "VC", "country": "Saudi Arabia"},
    {"name": "Saudi Aramco Ventures", "type": "Corporate", "country": "Saudi Arabia"},
    {"name": "Mubadala Ventures", "type": "Government", "country": "UAE"},
    {"name": "Riyad TAQNIA Fund", "type": "Government", "country": "Saudi Arabia"},
]

ROUND_POOL = [
    ("Pre-seed", 0.25, 0.75),
    ("Seed", 1.0, 4.0),
    ("Seed", 1.5, 5.0),
    ("Series A", 8.0, 25.0),
    ("Series B", 20.0, 60.0),
    ("Series C", 50.0, 150.0),
]


def seed(clear: bool = False):
    from src.database.connection import get_session, health_check
    from src.database.models import Base
    from src.database.connection import get_engine

    if not health_check():
        logger.error("Cannot connect to database. Aborting.")
        sys.exit(1)

    if clear:
        logger.warning("Clearing all data from funding_round_investors, funding_rounds, articles, investors, startups...")
        with get_session() as s:
            s.execute(text("DELETE FROM funding_round_investors"))
            s.execute(text("DELETE FROM funding_rounds"))
            s.execute(text("DELETE FROM articles"))
            s.execute(text("DELETE FROM investors"))
            s.execute(text("DELETE FROM startups"))
        logger.info("All data cleared.")

    with get_session() as session:
        # Insert investors
        investor_ids = {}
        for inv in SAMPLE_INVESTORS:
            result = session.execute(
                text("INSERT INTO investors (name, type, country) VALUES (:n, :t, :c) "
                     "ON CONFLICT (name) DO UPDATE SET type=EXCLUDED.type RETURNING id"),
                {"n": inv["name"], "t": inv["type"], "c": inv["country"]}
            )
            investor_ids[inv["name"]] = result.scalar()
        logger.info(f"Inserted {len(investor_ids)} investors")

        # Insert startups and funding rounds
        rounds_inserted = 0
        for startup in SAMPLE_STARTUPS:
            startup_result = session.execute(
                text("INSERT INTO startups (name, country, sector, description) "
                     "VALUES (:n, :c, :s, :d) RETURNING id"),
                {"n": startup["name"], "c": startup["country"],
                 "s": startup["sector"], "d": startup["description"]}
            )
            startup_id = startup_result.scalar()

            # Generate 1-3 historical rounds per startup
            n_rounds = random.randint(1, 3)
            base_date = date.today() - timedelta(days=random.randint(30, 500))
            round_pool_sample = random.sample(ROUND_POOL, min(n_rounds, len(ROUND_POOL)))

            for i, (rtype, min_m, max_m) in enumerate(sorted(round_pool_sample, key=lambda x: x[1])):
                amount_usd = random.uniform(min_m, max_m) * 1_000_000
                ann_date = base_date + timedelta(days=i * random.randint(180, 400))
                if ann_date > date.today():
                    ann_date = date.today() - timedelta(days=random.randint(1, 30))

                # Insert article stub
                article_url = f"https://menabytes.com/sample/{startup['name'].lower().replace(' ', '-')}-{rtype.lower().replace(' ', '-')}-{ann_date}"
                art_result = session.execute(
                    text("INSERT INTO articles (title, source, url, publication_date, processed_flag) "
                         "VALUES (:t, :s, :u, :d, TRUE) ON CONFLICT (url) DO NOTHING RETURNING id"),
                    {
                        "t": f"{startup['name']} raises ${amount_usd/1e6:.1f}M {rtype} round",
                        "s": "MENAbytes",
                        "u": article_url,
                        "d": ann_date,
                    }
                )
                article_id = art_result.scalar()

                round_result = session.execute(
                    text("""
                        INSERT INTO funding_rounds
                            (startup_id, round_type, amount_usd, currency_original, announcement_date, article_id)
                        VALUES (:sid, :rt, :amt, 'USD', :adate, :aid)
                        ON CONFLICT (startup_id, round_type, announcement_date) DO NOTHING
                        RETURNING id
                    """),
                    {"sid": startup_id, "rt": rtype, "amt": round(amount_usd, 2),
                     "adate": ann_date, "aid": article_id}
                )
                round_id = round_result.scalar()
                if not round_id:
                    continue
                rounds_inserted += 1

                # Attach 1-3 random investors
                lead_assigned = False
                selected_investors = random.sample(list(investor_ids.items()), random.randint(1, 3))
                for inv_name, inv_id in selected_investors:
                    is_lead = not lead_assigned
                    lead_assigned = True
                    session.execute(
                        text("INSERT INTO funding_round_investors (funding_round_id, investor_id, lead_investor) "
                             "VALUES (:rid, :iid, :lead) ON CONFLICT DO NOTHING"),
                        {"rid": round_id, "iid": inv_id, "lead": is_lead}
                    )

        logger.success(f"Seed complete — {len(SAMPLE_STARTUPS)} startups, {rounds_inserted} funding rounds")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")
    args = parser.parse_args()
    seed(clear=args.clear)


if __name__ == "__main__":
    main()
