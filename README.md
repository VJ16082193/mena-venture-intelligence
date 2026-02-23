# MENA Venture Intelligence Dashboard

A venture-grade intelligence platform designed to simulate internal deal sourcing workflows for VC teams tracking startup funding activity across the UAE and broader MENA region.

---

Built by Your **Vardhman Jain** 
Computer Science, BITS Dubai  
Venture & Startup Analytics

---

## What It Does

- **Scrapes** public funding news from MENAbytes, Wamda, and ArabNet every 12 hours
- **Extracts** structured deal data (startup name, round type, amount, investors, country, sector)
- **Normalizes** currencies to USD, standardizes sector labels, deduplicates entities
- **Stores** clean data in PostgreSQL
- **Surfaces** VC-grade analytics via an interactive Streamlit dashboard

---

## Why This Exists

Early-stage venture investing in MENA is fragmented across news sources and press releases. 
This project was built to simulate an internal VC deal sourcing workflow — transforming unstructured funding announcements into structured, queryable intelligence.

The goal: surface capital flow patterns, sector momentum, and investor behavior in a way that supports informed investment decisions.

---

## Example Insights Generated

- Sector-level capital deployment (rolling 12 months)
- Median seed round size by country
- Most active regional investors (deal count + lead frequency)
- Co-investment pair frequency mapping
- Early-stage companies raising under $5M in the last 6 months
- Capital concentration trends across UAE, KSA, and Egypt

---

## Quick Start

### 1. Clone and set up environment

```bash
git clone https://github.com/yourorg/mena-venture-intelligence.git
cd mena-venture-intelligence

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL at minimum
```

### 3. Run database migrations

```bash
# First time: initialize Alembic (already done in this repo)
alembic upgrade head
```

### 4. Seed sample data (optional, for development)

```bash
python scripts/seed_data.py
```

### 5. Run the pipeline manually

```bash
python scripts/run_pipeline.py          # All sources
python scripts/run_pipeline.py --dry-run  # Preview without writing to DB
```

### 6. Launch the dashboard

```bash
streamlit run src/dashboard/app.py
# Open http://localhost:8501
```

---

## Automated Pipeline

Start the scheduler (runs pipeline on boot + every 12 hours):

```bash
python main.py

# Or run once and exit:
python main.py --once
```

---

## Running Tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Project Structure

```
mena-venture-intelligence/
├── src/
│   ├── scraper/
│   │   ├── base_scraper.py       # Abstract base class — all scrapers inherit from this
│   │   ├── menabytes.py          # MENAbytes.com scraper
│   │   ├── wamda.py              # Wamda.com scraper
│   │   ├── arabnet.py            # ArabNet.me scraper
│   │   ├── extractor.py          # Regex/NLP extraction logic
│   │   ├── currency.py           # FX normalization (static + optional live rates)
│   │   └── pipeline.py           # Orchestrates full scrape → extract → store run
│   ├── database/
│   │   ├── models.py             # SQLAlchemy ORM models
│   │   ├── connection.py         # Engine, session factory, health check
│   │   ├── dedup.py              # Fuzzy deduplication for startups and investors
│   │   ├── writer.py             # Persist pipeline results to PostgreSQL
│   │   ├── validation.py         # Pre-insert data validation
│   │   ├── queries.py            # All analytics query functions (return DataFrames)
│   │   └── migrations/           # Alembic migration files
│   ├── analytics/
│   │   ├── sector.py             # Sector momentum and share calculations
│   │   ├── investor.py           # Investor leaderboard enrichment
│   │   └── signals.py            # Early-stage signal detection
│   └── dashboard/
│       └── app.py                # Streamlit dashboard (single file)
├── scripts/
│   ├── run_pipeline.py           # Manual pipeline trigger with --dry-run support
│   └── seed_data.py              # Insert representative historical data for dev/testing
├── tests/
│   ├── test_extractor.py         # Extraction logic unit tests
│   ├── test_dedup.py             # Deduplication unit tests
│   ├── test_validation.py        # Validation unit tests
│   └── test_currency.py          # Currency normalization unit tests
├── main.py                       # Scheduler entrypoint
├── requirements.txt
├── .env.example
├── alembic.ini
└── README.md
```

---

## Database Schema

| Table | Purpose |
|---|---|
| `startups` | Canonical startup entities |
| `funding_rounds` | Individual funding events |
| `investors` | Canonical investor entities |
| `funding_round_investors` | Many-to-many bridge (includes lead flag) |
| `articles` | Source article metadata and raw content |

Migrate: `alembic upgrade head`

---

## Deployment (Render)

### Dashboard

1. Create a **Web Service** pointing to this repo
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `streamlit run src/dashboard/app.py --server.port $PORT --server.address 0.0.0.0`
4. Add env vars: `DATABASE_URL`, `LOG_LEVEL=INFO`

### Pipeline (Cron)

1. Create a **Cron Job** service
2. Command: `python main.py --once`
3. Schedule: `0 */12 * * *` (every 12 hours)

### Database

Create a **PostgreSQL** instance on Render, copy the Internal Database URL to `DATABASE_URL`.

After first deploy, run migrations via a one-off job:
```bash
alembic upgrade head
```

---

## Adding a New Scraper

1. Create `src/scraper/yournewsource.py` inheriting from `BaseScraper`
2. Implement `get_article_links()` and `parse_article()`
3. Import and add to the `scrapers` list in `src/scraper/pipeline.py`
4. Add tests in `tests/test_extractor.py` with representative article fixtures

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | **required** | PostgreSQL connection string |
| `PIPELINE_SCHEDULE_HOURS` | `12` | Hours between pipeline runs |
| `MIN_CONFIDENCE_SCORE` | `40` | Records below this are flagged, not inserted |
| `SCRAPER_DELAY_SECONDS` | `2.0` | Delay between HTTP requests per source |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `DASHBOARD_CACHE_TTL_SECONDS` | `1800` | Streamlit query cache lifetime |
| `FX_REFRESH_DAYS` | `7` | How often to refresh exchange rates |
| `FX_API_KEY` | *(blank)* | ExchangeRate-API key for live FX rates |

---

## Known Limitations

- **Coverage**: Only captures publicly announced deals. Private rounds are not tracked.
- **Extraction accuracy**: Regex-based NLP is imperfect. Low-confidence records are flagged rather than auto-inserted.
- **Source fragility**: Scrapers break if source sites change their HTML structure.
- **FX rates**: Static rates have minor error vs. actual spot rates on announcement dates.
- **Valuation data**: Rarely disclosed in MENA press — `valuation_usd` will be NULL for most records.

---

## Design Principles

- Lean architecture (no unnecessary infrastructure)
- Data quality first (deduplication, normalization, validation)
- VC-oriented analytics (metrics aligned with investment workflows)
- Modular structure for maintainability

---

## License

This project is a venture intelligence simulation tool built for academic and research purposes.
