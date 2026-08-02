"""Data access layer for the Northwind delivery-tracking service.

Records live in a real database (see ``app/db.py``) instead of a Python list,
so the process does not accumulate an unbounded, ever-growing dataset in
memory: every function here pulls exactly the rows it needs from the database
on demand. ``DATABASE_URL`` selects the backend — SQLite by default (local
dev/tests), PostgreSQL in the containerised/Kubernetes/AWS deployment.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.db import deliveries_table, get_engine, init_db

SEED_DELIVERIES = [
    {"id": "NL-1001", "destination": "Manchester", "status": "in_transit", "driver": "A. Okafor"},
    {"id": "NL-1002", "destination": "Bristol", "status": "delivered", "driver": "R. Nowak"},
    {"id": "NL-1003", "destination": "Leeds", "status": "pending", "driver": None},
    {"id": "NL-1004", "destination": "Glasgow", "status": "in_transit", "driver": "S. Patel"},
    {"id": "NL-1005", "destination": "Cardiff", "status": "delivered", "driver": "M. Haddad"},
]

# Kept for callers/tests that inspect the seed data directly.
DELIVERIES = SEED_DELIVERIES

VALID_STATUSES = frozenset({"pending", "in_transit", "delivered"})

_ready = False


def ensure_ready() -> None:
    """Create the schema and seed it on first use. Safe to call repeatedly."""
    global _ready
    if not _ready:
        init_db(SEED_DELIVERIES)
        _ready = True


def _row_to_dict(row) -> dict:
    return {"id": row.id, "destination": row.destination, "status": row.status, "driver": row.driver}


def all_deliveries() -> list[dict]:
    """Pull every delivery record from the database."""
    ensure_ready()
    with get_engine().connect() as conn:
        rows = conn.execute(select(deliveries_table).order_by(deliveries_table.c.id)).all()
    return [_row_to_dict(row) for row in rows]


def find_delivery(delivery_id: str) -> dict | None:
    """Pull the delivery with the given id from the database, or None if unknown."""
    ensure_ready()
    with get_engine().connect() as conn:
        row = conn.execute(
            select(deliveries_table).where(deliveries_table.c.id == delivery_id)
        ).first()
    return _row_to_dict(row) if row is not None else None


def filter_by_status(status: str) -> list[dict]:
    """Pull all deliveries currently in the given status from the database."""
    ensure_ready()
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(deliveries_table)
            .where(deliveries_table.c.status == status)
            .order_by(deliveries_table.c.id)
        ).all()
    return [_row_to_dict(row) for row in rows]


def count_by_status() -> dict[str, int]:
    """Return a histogram of deliveries per status, computed by the database."""
    ensure_ready()
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(deliveries_table.c.status, func.count())
            .group_by(deliveries_table.c.status)
        ).all()
    return {status: count for status, count in rows}

