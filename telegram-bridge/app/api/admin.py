"""Admin HTTP boundary contract for Phase B.

Admin endpoints remain owned by ``app.routes`` during incremental extraction.
This module intentionally does not import the legacy router, preventing a
circular dependency while the extraction is staged.
"""

__all__: list[str] = []
