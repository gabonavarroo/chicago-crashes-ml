# Feature Catalog

## Feature Groups

- Temporal: hour, day-of-week, seasonality indicators.
- Spatial: grid cell, corridor class, proximity aggregates.
- Environment: weather, visibility, road condition.
- Historical: trailing incident rates and moving averages.

## Feature Governance

- Each feature must include source, transform logic, and freshness SLA.
- Leakage risk classification is required (`none`, `possible`, `blocked`).
- Deprecated features must include replacement guidance.
