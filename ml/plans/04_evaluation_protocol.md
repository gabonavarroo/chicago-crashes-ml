# Evaluation Protocol

## Severity Metrics

- Primary metric: PR-AUC.
- Recall@Top-K risk percentile (operational recall under alert budget).
- Calibration quality is tracked with Brier score.
- Reliability bins compare predicted vs observed risk by probability bucket.

## Hotspot Metrics

- MAE on crash counts.
- RMSE on crash counts.
- Poisson deviance when the selected objective/loss is Poisson/Tweedie based.
- Top-K hotspot hit rate (overlap between predicted and actual top-K zones).

## Combined Operational Metric

- Rank zones by `expected_severe_harm = predicted_crash_count * predicted_severe_probability`.
- Evaluate precision and recall on top-ranked `expected_severe_harm` zones.

## Evaluation Slices

- Season (`winter`, `spring`, `summer`, `fall`).
- Weekday vs weekend.
- Geography bins (zone-level rollups).

## Release Gates

- Minimum threshold checks cover severity PR-AUC, recall@top-k percentile, and Brier score.
- Minimum threshold checks cover hotspot MAE/RMSE, Poisson deviance (if used), and top-K hit rate.
- Minimum threshold checks cover combined top-ranked `expected_severe_harm` precision/recall.
- Stability checks are required by season, weekday/weekend, and geography with no severe slice regressions.
- Bias/sanity checks require no ID/target leakage features.
- Bias/sanity checks require non-degenerate predictions (not constant/invalid).
- Bias/sanity checks require no extreme artifact patterns (for example coordinate-only dominance or over-concentrated risk).
