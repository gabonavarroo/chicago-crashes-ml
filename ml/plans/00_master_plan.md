# Master Plan: Chicago Crashes ML

## Scope

### In Scope

- Build two production ML workflows:
- `severity`: crash severity risk prediction at the crash-event level.
- `hotspot`: spatiotemporal hotspot forecasting for operational planning.
- Define and version data contracts, features, model specs, evaluation protocol, deployment outputs, monitoring, and runbook.
- Deliver SQL outputs consumable by downstream analytics and API surfaces.

### Out of Scope (Phase 1)

- Real-time streaming inference.
- Individual-level driver risk profiling.
- Automated intervention policy decisions without human review.

## Milestones and Dates

| Milestone | Date | Deliverable |
| --- | --- | --- |
| M0 Kickoff and Environment Ready | 2026-04-08 | `ml/` scaffold, owners assigned, baseline access validated |
| M1 Data Contract Frozen | 2026-04-24 | Signed `01_data_contract.md`, base table SQL approved |
| M2 Feature Catalog + Model Specs Approved | 2026-05-15 | `02_feature_catalog.md` and `03_model_specs.md` finalized |
| M3 Evaluation Sign-off | 2026-05-29 | `04_evaluation_protocol.md`, baseline-vs-candidate results |
| M4 Deployment Outputs Ready | 2026-06-12 | Prediction tables and scoring pipeline tested in staging |
| M5 Monitoring + Runbook Handoff | 2026-06-19 | `06-08` docs complete, on-call simulation passed |

## Ownership by Workstream

| Workstream | Owner | Backup | Primary Responsibilities |
| --- | --- | --- | --- |
| Program and Stakeholders | ML Product Manager (TBD) | Analytics Lead (TBD) | Scope governance, phase gates, stakeholder comms |
| Data Engineering | Data Engineering Lead (TBD) | Analytics Engineer (TBD) | Source ingestion, contracts, SQL base layers |
| ML Engineering | ML Engineer Lead (TBD) | Applied Scientist (TBD) | Feature pipelines, training code, scoring jobs |
| Validation and QA | Data Scientist (TBD) | QA Analyst (TBD) | Offline metrics, robustness checks, release validation |
| Platform and Deployment | MLOps Engineer (TBD) | Platform Engineer (TBD) | Artifact registry, schedules, monitoring, alerts |
| Governance and Ethics | Risk and Compliance Partner (TBD) | Product Manager (TBD) | Bias review, policy constraints, sign-off evidence |

## Phase Plan and Acceptance Criteria

### Phase 0: Kickoff and Setup (2026-04-08 to 2026-04-12)

Acceptance criteria:
- Repo structure created under `ml/`.
- Access to required source datasets confirmed.
- Owners and backups assigned for each workstream.
- Initial backlog and dependency map published.

### Phase 1: Data Foundation (2026-04-13 to 2026-04-24)

Acceptance criteria:
- `01_data_contract.md` approved by Data Engineering and Analytics.
- `build_ml_crash_base.sql` generates reproducible base rows with documented grain and keys.
- Data quality checks pass for completeness, uniqueness, and range sanity.
- Historical backfill window locked and documented.

### Phase 2: Features and Model Design (2026-04-27 to 2026-05-15)

Acceptance criteria:
- `02_feature_catalog.md` includes feature definitions, lineage, freshness, and leakage classification.
- `03_model_specs.md` documents candidate algorithms, hyperparameter spaces, and training logic.
- Train-validation-test split policy frozen in `configs/split_policy.yaml`.
- First reproducible training run completes for both models.

### Phase 3: Evaluation and Calibration (2026-05-18 to 2026-05-29)

Acceptance criteria:
- `04_evaluation_protocol.md` finalized with target metrics and segment reporting.
- Candidates outperform baseline thresholds on agreed primary metrics.
- Calibration curves and threshold strategy documented in `configs/thresholds.yaml`.
- Risk review for fairness and failure modes completed.

### Phase 4: Deployment Outputs and Integration (2026-06-01 to 2026-06-12)

Acceptance criteria:
- `build_prediction_tables.sql` materializes prediction outputs with versioned metadata.
- Batch scoring job runs end-to-end in staging with retry-safe behavior.
- Artifact bundle (model, calibration, metadata JSON) is versioned in `ml/artifacts/`.
- Consumer contract tests pass for downstream BI/API use cases.

### Phase 5: Monitoring, Retraining, and Handoff (2026-06-15 to 2026-06-19)

Acceptance criteria:
- `06_monitoring_and_retraining.md` defines drift triggers, retraining cadence, and alert routing.
- `08_runbook.md` includes triage, rollback, and incident communication steps.
- Dry-run on-call exercise succeeds with documented outcomes.
- Stakeholder sign-off obtained for production readiness.

## Dependency and Risk Notes

- External data schema changes can shift milestone M1 and M2.
- Label latency can delay evaluation lock for M3.
- Platform deployment windows can constrain M4 release timing.
- Governance reviews are mandatory gates and cannot be bypassed.
