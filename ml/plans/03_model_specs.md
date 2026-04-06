# Model Specifications

## 1. Severity Label (Primary)

Define the primary binary severity target as:

- `severe_injury_flag = 1` if `injuries_fatal > 0` **OR** `injuries_incapacitating > 0`
- `severe_injury_flag = 0` otherwise

## 2. Hotspot Label

Define hotspot forecasting target as crash volume aggregated by spatial-temporal bucket:

- `crash_count` grouped by `(grid_id, time_bucket)`
- `time_bucket` can be configured by forecasting horizon:
  - Daily
  - Hourly

## 3. Combined Prioritization

Define a combined operational risk metric:

- `expected_severe_harm = predicted_crash_count * predicted_severe_probability`

This metric prioritizes areas/time windows where both crash likelihood and severe injury likelihood are high.

## 4. Feature Timing Policy

Maintain two explicit feature-set variants by data availability timing:

- **Dispatch-time feature set (strict):**
  - Includes only fields available at dispatch/scoring time.
  - Used for real-time or near-real-time operational inference.
- **Post-report analytical feature set (separate model variant):**
  - Includes additional fields available only after formal reporting.
  - Used for retrospective analysis and non-real-time modeling.

## 5. Leakage Exclusions

Apply strict leakage-prevention rules for model training and scoring:

- Exclude direct post-outcome fields from severity model features.
- Exclude any fields unavailable at the scoring timestamp.
