# Deployment and SQL Outputs

## Deployment Shape

- Batch scoring on scheduled intervals.
- Versioned model and calibration artifacts loaded from `ml/artifacts/`.

## SQL Deliverables

- Base training table build SQL.
- Hotspot time-series build SQL.
- Prediction output tables for downstream consumers.

## Operational Requirements

- Idempotent table writes.
- Traceable model version and score timestamp per prediction row.
