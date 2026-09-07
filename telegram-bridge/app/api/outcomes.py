"""Outcome HTTP boundary contract for Phase B.

The current route remains registered in ``app.routes`` until extraction is
completed. This seam deliberately contains no alternate persistence logic,
so there is no second outcome implementation to drift from the legacy path.
"""

import app.models as models


OUTCOME_MODEL = models.SignalOutcome

__all__ = ["OUTCOME_MODEL"]
