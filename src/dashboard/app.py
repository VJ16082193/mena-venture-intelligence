"""
app.py — MENA Venture Intelligence Dashboard (Streamlit)

Launch:
    streamlit run src/dashboard/app.py

Environment:
    DATABASE_URL must be set (see .env.example)
    DASHBOARD_CACHE_TTL_SECONDS controls query cache lifetime (default 1800)
"""

import os
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.analytics.investor import investor_leaderboard_enriched
from src.analytics.sector import sector_summary_with_share, top_sectors_by_momentum
from src.analytics.signals import early_stage_signals
from src.database.connection import health_check
from src.database.queries import (
    get_geography_summary,
    get_monthly_trend,
    get_overview_kpis,
    get_recent_deals,
    get_stage_by_country,
    search_investors,
    search_startups,
)

# ── Config ────────────────────────────────────────────────────────────────────
CACHE_TTL = int(os.getenv("DASHBOARD_CACHE_TTL_SECONDS", "1800"))
COUNTRIES = ["UAE", "Saudi Arabia", "Egypt", "Qatar", "Bahrain", "Kuwait", "Jordan", "Morocco"]
SECTORS = [
    "Fintech", "E-commerce", "Healthtech", "Edtech", "Logistics",
    "Proptech", "Agritech", "SaaS / Enterprise", "Energy / Cleantech",
    "Gaming / Entertainment", "Mobility", "Cybersecurity", "AI / ML",
]
ROUND_TYPES = [
    "Pre-seed", "Seed", "Series A", "Series B", "Series C",
    "Series D", "Growth", "Bridge", "Venture Debt", "Undisclosed",
]

st.set_page_config(
    page_title="MENA Venture Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        text-align: center;
    }
    .metric-value { font-size: 1.8rem; font-weight: 700; color: #1B3A6B; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
    .signal-badge {
        display: inline-block;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    h1 { color: #1B3A6B !important; }
    .stTabs [data-baseweb="tab"] { font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ── DB health gate ─────────────────────────────────────────────────────────────
if not health_check():
    st.error("⚠️ Cannot connect to the database. Check your DATABASE_URL and try again.")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 Filters")

    default_from = date.today() - timedelta(days=365)
    date_range = st.date_input(
        "Date Range",
        value=(default_from, date.today()),
        help="Filter deals by announcement date",
    )
    date_from = date_range[0] if isinstance(date_range, tuple) and len(date_range) > 0 else default_from
    date_to = date_range[1] if isinstance(date_range, tuple) and len(date_range) > 1 else date.today()

    countries = st.multiselect("Country", COUNTRIES, placeholder="All countries")
    sectors = st.multiselect("Sector", SECTORS, placeholder="All sectors")
    round_types = st.multiselect("Round Type", ROUND_TYPES, placeholder="All stages")

    st.divider()
    st.markdown("## 🔎 Search")
    search_startup_q = st.text_input("Startup name", placeholder="e.g. Tabby, Tamara...")
    search_investor_q = st.text_input("Investor name", placeholder="e.g. BECO, STV...")

    st.divider()
    st.caption("Data refreshes every 12 hours automatically.")
    if st.button("🔄 Refresh cache"):
        st.cache_data.clear()
        st.rerun()

# Normalize empty lists to None for query layer
_countries = countries or None
_sectors = sectors or None
_round_types = round_types or None

# ── Cached query wrappers ─────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def cached_kpis(c, s, r, df, dt):
    return get_overview_kpis(c, s, r, df, dt)

@st.cache_data(ttl=CACHE_TTL)
def cached_trend(c, s, r, df, dt):
    return get_monthly_trend(c, s, r, df, dt)

@st.cache_data(ttl=CACHE_TTL)
def cached_sector(c, df, dt):
    return sector_summary_with_share(c, df, dt)

@st.cache_data(ttl=CACHE_TTL)
def cached_momentum():
    return top_sectors_by_momentum()

@st.cache_data(ttl=CACHE_TTL)
def cached_investors(c, df, dt):
    return investor_leaderboard_enriched(c, df, dt)

@st.cache_data(ttl=CACHE_TTL)
def cached_geo(df, dt):
    return get_geography_summary(df, dt)

@st.cache_data(ttl=CACHE_TTL)
def cached_stage_country():
    return get_stage_by_country()

@st.cache_data(ttl=CACHE_TTL)
def cached_recent(c, s, r, df, dt):
    return get_recent_deals(c, s, r, df, dt)

@st.cache_data(ttl=CACHE_TTL)
def cached_signals():
    return early_stage_signals()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 📊 MENA Venture Intelligence")
st.caption(
    f"Showing deals: **{date_from.strftime('%b %d, %Y')}** → **{date_to.strftime('%b %d, %Y')}**"
    + (f"  |  Countries: {', '.join(countries)}" if countries else "  |  All countries")
)

# ── KPI Cards ─────────────────────────────────────────────────────────────────
kpis = cached_kpis(_countries, _sectors, _round_types, date_from, date_to)
c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 Total Capital", f"${kpis['total_capital_mn']:.1f}M")
c2.metric("📁 Total Deals", f"{kpis['total_deals']:,}")
c3.metric("📏 Avg Deal Size", f"${kpis['avg_deal_mn']:.1f}M")
c4.metric("🏢 Active Investors", f"{kpis['active_investors']:,}")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_flow, tab_sectors, tab_investors, tab_geo, tab_signals, tab_search = st.tabs([
    "📈 Deal Flow", "🏭 Sectors", "👥 Investors", "🌍 Geography", "🚨 Signals", "🔍 Search"
])

# ════════════════════════════ TAB 1: DEAL FLOW ════════════════════════════════
with tab_flow:
    trend_df = cached_trend(_countries, _sectors, _round_types, date_from, date_to)

    col_left, col_right = st.columns([2, 1])
    with col_left:
        if not trend_df.empty:
            fig = px.line(
                trend_df, x="month", y="total_mn_usd",
                title="Monthly Funding Volume (USD M)",
                labels={"month": "", "total_mn_usd": "Capital (USD M)"},
                template="plotly_white",
                line_shape="spline",
                markers=True,
            )
            fig.update_traces(line_color="#0E7C7B", line_width=2.5)
            fig.update_layout(hovermode="x unified", height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data for the selected filters.")

    with col_right:
        if not trend_df.empty:
            fig2 = px.bar(
                trend_df, x="month", y="deal_count",
                title="Monthly Deal Count",
                labels={"month": "", "deal_count": "Deals"},
                template="plotly_white",
                color_discrete_sequence=["#1B3A6B"],
            )
            fig2.update_layout(height=350)
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("#### Recent Deals")
    recent_df = cached_recent(_countries, _sectors, _round_types, date_from, date_to)
    if not recent_df.empty:
        display_df = recent_df.copy()
        display_df["amount_mn_usd"] = display_df["amount_mn_usd"].apply(
            lambda x: f"${x:.1f}M" if x > 0 else "Undisclosed"
        )
        st.dataframe(
            display_df[["startup", "country", "sector", "round_type", "amount_mn_usd", "announcement_date"]],
            use_container_width=True,
            hide_index=True,
        )
        csv = recent_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export to CSV", csv, "mena_deals.csv", "text/csv")
    else:
        st.info("No deals found for the selected filters.")

# ════════════════════════════ TAB 2: SECTORS ════════════════════════════════
with tab_sectors:
    sector_df = cached_sector(_countries, date_from, date_to)
    momentum_df = cached_momentum()

    col1, col2 = st.columns(2)
    with col1:
        if not sector_df.empty:
            fig = px.bar(
                sector_df.head(10), x="total_capital_mn", y="sector",
                orientation="h",
                title="Capital by Sector (USD M)",
                labels={"total_capital_mn": "Capital (USD M)", "sector": ""},
                template="plotly_white",
                color="total_capital_mn",
                color_continuous_scale="Blues",
            )
            fig.update_layout(height=400, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not sector_df.empty:
            fig2 = px.pie(
                sector_df.head(8), values="deal_count", names="sector",
                title="Deal Count Distribution",
                template="plotly_white",
                hole=0.4,
            )
            fig2.update_layout(height=400)
            st.plotly_chart(fig2, use_container_width=True)

    if not momentum_df.empty:
        st.markdown("#### Sector Momentum (6-Month Growth Rate)")
        st.dataframe(
            momentum_df[["sector", "recent_6m_mn", "prior_6m_mn", "growth_pct"]].rename(columns={
                "recent_6m_mn": "Recent 6M ($M)",
                "prior_6m_mn": "Prior 6M ($M)",
                "growth_pct": "Growth %",
            }),
            use_container_width=True, hide_index=True,
        )

# ════════════════════════════ TAB 3: INVESTORS ═══════════════════════════════
with tab_investors:
    inv_df = cached_investors(_countries, date_from, date_to)

    if not inv_df.empty:
        st.markdown("#### Investor Leaderboard")
        st.dataframe(
            inv_df[["investor", "type", "total_deals", "lead_deals", "lead_ratio_pct",
                    "deployed_mn_usd", "avg_check_mn"]].rename(columns={
                "investor": "Investor",
                "type": "Type",
                "total_deals": "Total Deals",
                "lead_deals": "Lead Deals",
                "lead_ratio_pct": "Lead %",
                "deployed_mn_usd": "Deployed ($M)",
                "avg_check_mn": "Avg Check ($M)",
            }),
            use_container_width=True, hide_index=True,
        )
        csv_inv = inv_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export Investor Data", csv_inv, "mena_investors.csv", "text/csv")
    else:
        st.info("No investor data available for the selected filters.")

# ════════════════════════════ TAB 4: GEOGRAPHY ═══════════════════════════════
with tab_geo:
    geo_df = cached_geo(date_from, date_to)
    stage_df = cached_stage_country()

    col1, col2 = st.columns(2)
    with col1:
        if not geo_df.empty:
            fig = px.bar(
                geo_df, x="country", y="total_capital_mn",
                title="Capital by Country (USD M)",
                labels={"country": "", "total_capital_mn": "Capital (USD M)"},
                template="plotly_white",
                color="total_capital_mn",
                color_continuous_scale="Teal",
            )
            fig.update_layout(height=380, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not geo_df.empty:
            fig2 = px.pie(
                geo_df, values="deal_count", names="country",
                title="Deal Count by Country",
                template="plotly_white",
                hole=0.4,
            )
            fig2.update_layout(height=380)
            st.plotly_chart(fig2, use_container_width=True)

    if not stage_df.empty:
        st.markdown("#### Stage Distribution by Country")
        pivot = stage_df.pivot_table(
            index="country", columns="round_type", values="deals", fill_value=0
        )
        st.dataframe(pivot, use_container_width=True)

# ════════════════════════════ TAB 5: SIGNALS ════════════════════════════════
with tab_signals:
    signals_df = cached_signals()

    st.markdown("#### Early-Stage Signals (Seed & Pre-seed, last 6 months, <$5M)")
    if not signals_df.empty:
        display = signals_df[["startup", "country", "sector", "round_type",
                               "amount_mn_usd", "announcement_date",
                               "prior_rounds", "signal_label"]].copy()
        display["amount_mn_usd"] = display["amount_mn_usd"].apply(
            lambda x: f"${x:.2f}M" if pd.notna(x) and x > 0 else "Undisclosed"
        )
        st.dataframe(
            display.rename(columns={
                "startup": "Startup", "country": "Country", "sector": "Sector",
                "round_type": "Stage", "amount_mn_usd": "Amount",
                "announcement_date": "Date", "prior_rounds": "Prior Rounds",
                "signal_label": "Signal",
            }),
            use_container_width=True, hide_index=True,
        )
        csv_sig = signals_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export Signals", csv_sig, "mena_signals.csv", "text/csv")
    else:
        st.info("No early-stage signals found for the current period.")

# ════════════════════════════ TAB 6: SEARCH ══════════════════════════════════
with tab_search:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Startup Search")
        if search_startup_q:
            result_df = search_startups(search_startup_q)
            if not result_df.empty:
                st.dataframe(result_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"No startups found matching '{search_startup_q}'")
        else:
            st.caption("Enter a startup name in the sidebar to search.")

    with col2:
        st.markdown("#### Investor Search")
        if search_investor_q:
            result_df = search_investors(search_investor_q)
            if not result_df.empty:
                st.dataframe(result_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"No investors found matching '{search_investor_q}'")
        else:
            st.caption("Enter an investor name in the sidebar to search.")
