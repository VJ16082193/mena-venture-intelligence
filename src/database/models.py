"""
models.py — SQLAlchemy ORM models mirroring the normalized PostgreSQL schema.

Table relationships:
    startups           1──* funding_rounds
    investors          *──* funding_rounds  (via funding_round_investors)
    articles           1──* funding_rounds  (source traceability)
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey,
    Integer, Numeric, SmallInteger, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── startups ──────────────────────────────────────────────────────────────────

class Startup(Base):
    __tablename__ = "startups"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String(255), nullable=False)
    country      = Column(String(100), nullable=False)
    sector       = Column(String(100), nullable=True)
    founded_year = Column(SmallInteger, nullable=True)
    description  = Column(Text, nullable=True)
    website      = Column(String(500), nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(),
                          onupdate=func.now(), nullable=False)

    funding_rounds = relationship("FundingRound", back_populates="startup",
                                  cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Startup id={self.id} name='{self.name}' country='{self.country}'>"


# ── funding_rounds ────────────────────────────────────────────────────────────

class FundingRound(Base):
    __tablename__ = "funding_rounds"
    __table_args__ = (
        UniqueConstraint("startup_id", "round_type", "announcement_date",
                         name="uq_round_startup_type_date"),
    )

    id                = Column(Integer, primary_key=True, autoincrement=True)
    startup_id        = Column(Integer, ForeignKey("startups.id", ondelete="CASCADE"), nullable=False)
    round_type        = Column(String(50), nullable=False)
    amount_usd        = Column(Numeric(15, 2), nullable=True)
    amount_original   = Column(Numeric(15, 2), nullable=True)
    currency_original = Column(String(3), nullable=True)
    announcement_date = Column(Date, nullable=False)
    valuation_usd     = Column(Numeric(15, 2), nullable=True)
    article_id        = Column(Integer, ForeignKey("articles.id"), nullable=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    startup   = relationship("Startup", back_populates="funding_rounds")
    article   = relationship("Article")
    investors = relationship("FundingRoundInvestor", back_populates="funding_round",
                             cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<FundingRound id={self.id} startup_id={self.startup_id} "
            f"type='{self.round_type}' date={self.announcement_date}>"
        )


# ── investors ─────────────────────────────────────────────────────────────────

class Investor(Base):
    __tablename__ = "investors"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(255), nullable=False, unique=True)
    type       = Column(String(50), nullable=True)   # VC, Angel, Corporate, Government, Family Office
    country    = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    rounds = relationship("FundingRoundInvestor", back_populates="investor")

    def __repr__(self):
        return f"<Investor id={self.id} name='{self.name}' type='{self.type}'>"


# ── funding_round_investors (bridge) ──────────────────────────────────────────

class FundingRoundInvestor(Base):
    __tablename__ = "funding_round_investors"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    funding_round_id = Column(Integer, ForeignKey("funding_rounds.id", ondelete="CASCADE"), nullable=False)
    investor_id      = Column(Integer, ForeignKey("investors.id", ondelete="CASCADE"), nullable=False)
    lead_investor    = Column(Boolean, default=False, nullable=False)

    funding_round = relationship("FundingRound", back_populates="investors")
    investor      = relationship("Investor", back_populates="rounds")

    def __repr__(self):
        return (
            f"<FundingRoundInvestor round={self.funding_round_id} "
            f"investor={self.investor_id} lead={self.lead_investor}>"
        )


# ── articles ──────────────────────────────────────────────────────────────────

class Article(Base):
    __tablename__ = "articles"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    title                 = Column(Text, nullable=False)
    source                = Column(String(255), nullable=False)
    url                   = Column(Text, unique=True, nullable=False)
    publication_date      = Column(Date, nullable=True)
    raw_content           = Column(Text, nullable=True)
    processed_flag        = Column(Boolean, default=False, nullable=False)
    extraction_confidence = Column(SmallInteger, nullable=True)
    created_at            = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<Article id={self.id} source='{self.source}' url='{self.url[:60]}'>"
