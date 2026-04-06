# Model Specifications

## Severity Model

- Problem type: multiclass classification.
- Candidate families: gradient boosting, regularized linear baseline.
- Outputs: calibrated class probabilities and top-risk label.
- Severity label (primary): `severe_injury_flag = 1` if `injuries_fatal > 0` OR `injuries_incapacitating > 0`, else `0`.

## Hotspot Model

- Problem type: count/risk forecasting by cell-time bucket.
- Candidate families: gradient boosting regressor, Poisson baseline.
- Outputs: risk score and hotspot flag based on configurable threshold.
- Hotspot label: `crash_count` aggregated by `(grid_id, time_bucket)` for the selected forecasting horizon (daily or hourly).

## Combined Prioritization

- `expected_severe_harm = predicted_crash_count * predicted_severe_probability`.

## Feature Timing Policy

- Dispatch-time feature set (strict): include only variables known at scoring time.
- Post-report analytical feature set: maintained as a separate model variant.

## Leakage Exclusions

- Exclude direct post-outcome fields from severity model features.
- Exclude any fields unavailable at scoring timestamp.

## Reproducibility Requirements

- Fixed random seeds and immutable training snapshots.
- Saved training configs and metadata per model version.
