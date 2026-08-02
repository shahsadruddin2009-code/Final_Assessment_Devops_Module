"""Database engine and schema management for the delivery-tracking service.

Uses SQLAlchemy Core so the same query code runs unchanged against two
backends, selected purely by the ``DATABASE_URL`` environment variable:

  * SQLite — the zero-setup default, used for local development and the
    automated test suite (an in-memory database when running tests).
  * PostgreSQL — used in the containerised/Kubernetes/AWS deployment, so the
    service does not hold an unbounded, ever-growing dataset in process
    memory and every replica reads from a single source of truth.

Pulling records happens on demand (see ``app/data.py``); nothing is cached in
memory beyond the lifetime of a single request.
"""

from __future__ import annotations

import os

from sqlalchemy import Column, MetaData, String, Table, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

DEFAULT_DATABASE_URL = "sqlite:///northwind_deliveries.db"

metadata = MetaData()

deliveries_table = Table(
    "deliveries",
    metadata,
    Column("id", String, primary_key=True),
    Column("destination", String, nullable=False),
    Column("status", String, nullable=False),
    Column("driver", String, nullable=True),
)

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, created on first use."""
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        kwargs: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                # Shared in-memory database so every thread's connection sees
                # the same tables/rows: needed because the HTTP server is
                # multi-threaded.
                kwargs["poolclass"] = StaticPool
        _engine = create_engine(url, **kwargs)
    return _engine


def reset_engine() -> None:
    """Dispose of the cached engine so a new ``DATABASE_URL`` can take effect."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def init_db(seed_rows: list[dict] | None = None) -> None:
    """Create the schema if missing, then seed it if the table is empty."""
    engine = get_engine()
    metadata.create_all(engine)

    if not seed_rows:
        return

    with engine.begin() as conn:
        existing = conn.execute(deliveries_table.select()).first()
        if existing is None:
            conn.execute(deliveries_table.insert(), seed_rows)
