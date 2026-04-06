# Master Plan: Chicago Crashes ML

## 1. Scope

### In Scope
- Build an end-to-end ML workflow for:
  - **Crash severity prediction** (record-level supervised classification)
  - **Crash hotspot forecasting** (spatiotemporal risk scoring)
- Define reproducible data contracts, feature catalog, model specs, and evaluation protocol.
- Implement SQL data products that support training and scoring.
- Stand up deployment outputs, monitoring, retraining triggers, and runbooks.

### Out of Scope (Phase 1)
- Real-time streaming inference.
- Fully automated online learning.
- Non-crash multimodal data ingestion (e.g., external camera feeds).

## 2. Milestones and Dates

| Milestone | Date (UTC) | Deliverable |
|---|---:|---|
| M0: Planning kickoff complete | 2026-04-10 | Approved plan set in `ml/plans/` |
| M1: Data contract + base SQL complete | 2026-04-24 | Stable `build_ml_crash_base.sql` and documented schema contract |
| M2: Feature catalog + feature builds complete | 2026-05-08 | Feature definitions and reproducible feature pipeline |
| M3: Baseline models trained | 2026-05-22 | Severity + hotspot baseline models with saved artifacts |
| M4: Evaluation and thresholding sign-off | 2026-06-05 | Final metrics report and decision thresholds |
| M5: Deployment outputs + runbook ready | 2026-06-19 | Prediction tables, ops runbook, and rollback steps |
| M6: Monitoring live + retraining policy active | 2026-07-03 | Monitoring dashboards and retraining SOP |

## 3. Ownership by Workstream

| Workstream | Owner Role | Backup Role | Primary Files |
|---|---|---|---|
| Program management | ML Product Owner | Analytics Lead | `plans/00_master_plan.md` |
| Data contracts and extraction | Data Engineer | Analytics Engineer | `plans/01_data_contract.md`, `src/data_extract.py`, `sql/build_ml_crash_base.sql` |
| Feature engineering | ML Engineer | Data Scientist | `plans/02_feature_catalog.md`, `src/feature_build.py` |
| Modeling (severity) | Data Scientist | ML Engineer | `src/train_severity.py`, `configs/severity.yaml` |
| Modeling (hotspot) | Data Scientist | GIS/Analytics Engineer | `src/train_hotspot.py`, `configs/hotspot.yaml` |
| Evaluation and policy | ML Engineer | Data Scientist | `plans/04_evaluation_protocol.md`, `src/evaluate.py`, `configs/thresholds.yaml` |
| Deployment + SQL outputs | Analytics Engineer | Data Engineer | `plans/05_deployment_and_sql_outputs.md`, `sql/build_prediction_tables.sql`, `src/score.py` |
| Monitoring & retraining | MLOps Engineer | ML Engineer | `plans/06_monitoring_and_retraining.md`, `configs/split_policy.yaml` |
| Risk & ethics | Responsible AI Lead | Product Owner | `plans/07_risks_and_ethics.md` |
| Operations runbook | On-call ML Engineer | Platform Engineer | `plans/08_runbook.md` |

## 4. Acceptance Criteria by Phase

### Phase 0: Planning and Governance
- All plan documents exist with owners, open questions, and version dates.
- Stakeholders sign off on scope and success metrics.

### Phase 1: Data Foundation
- Data contract defines required fields, quality constraints, and freshness SLAs.
- Base SQL build is deterministic and idempotent for backfills.
- Data quality checks pass for null rates, key uniqueness, and temporal validity.

### Phase 2: Features and Baselines
- Feature catalog includes definitions, lineage, expected ranges, and leakage review.
- Feature build script reproduces train/validation/test datasets from config.
- Baseline model artifacts are generated and version-tagged.

### Phase 3: Evaluation and Decisioning
- Evaluation protocol covers temporal split policy, calibration, fairness slices, and threshold selection.
- Models meet agreed performance floors (e.g., PR-AUC/lift for severity; recall@K or map-risk metrics for hotspot).
- Thresholds are documented with business trade-offs and approval sign-off.

### Phase 4: Deployment and Data Products
- SQL prediction tables publish on a defined schedule with schema tests.
- Scoring pipeline produces deterministic outputs for the same model + input snapshot.
- Rollback procedure validated in lower environment.

### Phase 5: Monitoring and Continuous Improvement
- Monitoring tracks model drift, data drift, service health, and KPI deltas.
- Retraining policy includes trigger thresholds, approval gates, and audit logs.
- Incident response runbook is test-executed and reviewed.

## 5. Dependencies and Risks (Summary)
- Timely access to crash, roadway, and contextual data sources.
- Stable geospatial reference system for hotspot aggregation.
- Policy alignment on fairness and intervention constraints.

## 6. Reporting Cadence
- Weekly workstream sync (status, blockers, decisions).
- Biweekly stakeholder checkpoint (milestone readiness).
- End-of-phase review with acceptance criteria checklist.
