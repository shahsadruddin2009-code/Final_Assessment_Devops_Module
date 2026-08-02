"""Ensure the repository root is importable so tests can ``import app``."""

import os

# In-memory SQLite keeps the automated test suite hermetic and fast, with no
# Postgres instance required. Production/Kubernetes sets DATABASE_URL instead.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
