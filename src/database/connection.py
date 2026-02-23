"""
connection.py — SQLAlchemy engine and session factory.

Use get_session() as a context manager in all database operations:

    with get_session() as session:
        session.execute(...)
"""

import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

_DATABASE_URL = os.getenv("DATABASE_URL")
if not _DATABASE_URL:
    raise EnvironmentError(
        "DATABASE_URL is not set. Copy .env.example to .env and configure it."
    )

# Connection pool tuned for a single-server deployment
_engine = create_engine(
    _DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,       # validate connections before use
    pool_recycle=3600,        # recycle connections every hour
    echo=False,
)

_SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy Session, automatically committing on success
    or rolling back on exception.
    """
    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error(f"DB session rolled back due to: {exc}")
        raise
    finally:
        session.close()


def get_engine():
    """Return the shared engine (for Alembic or raw connection use)."""
    return _engine


def health_check() -> bool:
    """Return True if the database is reachable."""
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return False
