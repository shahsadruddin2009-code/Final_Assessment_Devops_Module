"""Convenience entry point: start the service with ``python run.py``.

This is equivalent to ``python -m app``. Both work because the repository root
is on the Python path, so the ``app`` package can be imported.
"""

from app.service import main

if __name__ == "__main__":
    main()
