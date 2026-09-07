---
name: phase-d-models
description: Decompose Medis Touch SQLAlchemy models safely while preserving metadata, enums, migrations and app.models compatibility.
metadata:
  slash-command: enabled
---

# Phase D Model Specialist

Before editing models, inventory every `from app.models` and `import app.models` use plus migration/schema dependencies.

Preferred domains:
1. base types/enums/constants
2. settings
3. signals
4. trades
5. outcomes
6. calibration/promotions
7. subscriptions
8. payments

Preserve `Base.metadata` registration and PostgreSQL enum behavior. Maintain `app.models` as a compatibility facade until all consumers are migrated and tested.
Never perform a blind model split.
