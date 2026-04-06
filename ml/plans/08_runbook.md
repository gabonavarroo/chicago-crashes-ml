# Runbook

## End-to-End Run Commands (`extract -> train -> evaluate -> score`)

### 0) Set run context

```bash
cd /Users/gabo/Developer/Gabon/chicago-crashes-ml
RUN_DATE="$(date -u +%F)"
SNAPSHOT_VERSION="v1"
```

### 1) Extract

```bash
python ml/src/data_extract.py \
  --snapshot-version "${SNAPSHOT_VERSION}" \
  --extraction-date "${RUN_DATE}"
```

Expected output:
- `ml/artifacts/snapshots/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/manifest.json`
- `ml_crash_base_v1.parquet`
- `ml_hotspot_ts_v1.parquet`

### 2) Train (feature build + model training)

```bash
python ml/src/feature_build.py \
  --snapshot-version "${SNAPSHOT_VERSION}" \
  --extraction-date "${RUN_DATE}"

python ml/src/train_severity.py \
  --snapshot-version "${SNAPSHOT_VERSION}" \
  --extraction-date "${RUN_DATE}"

python ml/src/train_hotspot.py \
  --snapshot-version "${SNAPSHOT_VERSION}" \
  --extraction-date "${RUN_DATE}"
```

Expected output:
- `ml/artifacts/features/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/manifest.json`
- `ml/artifacts/models/severity/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/severity_model.pkl`
- `ml/artifacts/models/severity/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/severity_calibrator.pkl`
- `ml/artifacts/models/hotspot/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/hotspot_model.pkl`

### 3) Evaluate (release gates)

```bash
python ml/src/evaluate.py \
  --snapshot-version "${SNAPSHOT_VERSION}" \
  --extraction-date "${RUN_DATE}" \
  --split test
```

Expected output:
- `ml/artifacts/evaluation/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/evaluation_report.md`
- `ml/artifacts/evaluation/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/evaluation_metrics.json`

### 4) Score

```bash
python ml/src/score.py \
  --snapshot-version "${SNAPSHOT_VERSION}" \
  --snapshot-extraction-date "${RUN_DATE}" \
  --severity-model-extraction-date "${RUN_DATE}" \
  --hotspot-model-extraction-date "${RUN_DATE}"
```

Expected output:
- `ml/artifacts/predictions/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/ml_severity_predictions.parquet`
- `ml/artifacts/predictions/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/ml_hotspot_forecasts.parquet`
- `ml/artifacts/predictions/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/ml_combined_risk_rankings.parquet`
- `ml/artifacts/predictions/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/manifest.json`

## Failure Handling and Restart Steps

### Triage

- Identify failing stage: `extract`, `feature_build`, `train_severity`, `train_hotspot`, `evaluate`, `score`, `publish`.
- Capture error log, command used, `snapshot_version`, and `extraction_date`.
- Check whether the stage produced a complete manifest/output set.

### Safe restart policy

- Re-run only the failed stage and downstream stages.
- Keep `SNAPSHOT_VERSION` and `RUN_DATE` fixed during restart.
- If a stage output directory is partial/corrupt, clear only that stage directory before re-running.

### Stage restart commands

```bash
# extract restart
python ml/src/data_extract.py --snapshot-version "${SNAPSHOT_VERSION}" --extraction-date "${RUN_DATE}"

# feature build restart
python ml/src/feature_build.py --snapshot-version "${SNAPSHOT_VERSION}" --extraction-date "${RUN_DATE}"

# severity train restart
python ml/src/train_severity.py --snapshot-version "${SNAPSHOT_VERSION}" --extraction-date "${RUN_DATE}"

# hotspot train restart
python ml/src/train_hotspot.py --snapshot-version "${SNAPSHOT_VERSION}" --extraction-date "${RUN_DATE}"

# evaluate restart
python ml/src/evaluate.py --snapshot-version "${SNAPSHOT_VERSION}" --extraction-date "${RUN_DATE}" --split test

# score restart
python ml/src/score.py \
  --snapshot-version "${SNAPSHOT_VERSION}" \
  --snapshot-extraction-date "${RUN_DATE}" \
  --severity-model-extraction-date "${RUN_DATE}" \
  --hotspot-model-extraction-date "${RUN_DATE}"
```

### Rollback

- If release gates fail or production anomalies occur, revert consumers to the previous `snapshot_version` and previous prediction partition.
- Record rollback reason and corrective action in release notes.

## Data Dependency Checklist

- Source DB connectivity available (`DATABASE_URL` or DB host/user/pass vars configured).
- Curated source tables present and readable:
- `ml_crash_base_v1`
- `ml_hotspot_ts_v1`
- Config files present and valid:
- `ml/configs/split_policy.yaml`
- `ml/configs/thresholds.yaml`
- `ml/configs/hotspot.yaml`
- Upstream schema for prediction serving applied:
- `ml/sql/build_prediction_tables.sql`
- Feature artifacts available before training:
- `ml/artifacts/features/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/`
- Model artifacts available before scoring:
- `ml/artifacts/models/severity/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/`
- `ml/artifacts/models/hotspot/version=${SNAPSHOT_VERSION}/extraction_date=${RUN_DATE}/`

## Versioning and Release Notes Process

1. Set `SNAPSHOT_VERSION`:
- Increment for incompatible feature/schema/model-contract changes.
- Keep same version for threshold-only tuning.
2. Freeze `RUN_DATE` as immutable extraction partition for the release.
3. Run full pipeline and confirm release gates from `evaluation_metrics.json`.
4. Write release notes entry (recommended path: `ml/plans/release_notes.md`) including:
- Release ID: `${SNAPSHOT_VERSION}-${RUN_DATE}`
- Data window and extraction date
- Severity/hotspot model versions used in score manifest
- Gate results (`PASS/FAIL` + key metrics deltas)
- Operational changes (thresholds, configs, schedules)
- Known risks and rollback pointer
5. Share release notes with policy and operations stakeholders.

## Stakeholder Outputs

### Daily Top-N High-Risk Zones (combined score)

Use `ml_combined_risk_rankings` and the latest scoring timestamp:

```sql
WITH latest_run AS (
    SELECT MAX(score_ts_utc) AS score_ts_utc
    FROM ml_combined_risk_rankings
),
ranked AS (
    SELECT
        c.grid_id,
        c.forecast_time,
        c.horizon_hours,
        c.expected_severe_harm,
        c.risk_rank,
        c.risk_tier,
        c.predicted_crash_count,
        c.severity_probability
    FROM ml_combined_risk_rankings c
    JOIN latest_run l
      ON c.score_ts_utc = l.score_ts_utc
    WHERE c.horizon_hours = 1
)
SELECT *
FROM ranked
ORDER BY expected_severe_harm DESC, risk_rank ASC
LIMIT 50;
```

### Weekly Factor Importance Summary (policy team)

Publish a weekly feature-importance table from model artifacts/retraining output:
- Suggested table: `ml_factor_importance_weekly`
- Required columns: `week_start`, `model_name`, `feature_name`, `importance_value`, `importance_rank`, `directionality_note`, `policy_note`.

Weekly policy extract query:

```sql
SELECT
    week_start,
    model_name,
    feature_name,
    importance_value,
    importance_rank,
    directionality_note,
    policy_note
FROM ml_factor_importance_weekly
WHERE week_start = date_trunc('week', CURRENT_DATE)::date
ORDER BY model_name, importance_rank
LIMIT 100;
```

### Monthly Model Health Dashboard Definitions (SQL-ready)

```sql
CREATE OR REPLACE VIEW vw_ml_model_health_monthly AS
WITH severity_monthly AS (
    SELECT
        date_trunc('month', score_ts_utc)::date AS month_start,
        COUNT(*) AS severity_rows,
        COUNT(DISTINCT severity_model_version) AS severity_model_versions
    FROM ml_severity_predictions
    GROUP BY 1
),
hotspot_monthly AS (
    SELECT
        date_trunc('month', score_ts_utc)::date AS month_start,
        COUNT(*) AS hotspot_rows,
        AVG(CASE WHEN is_hotspot_alert THEN 1.0 ELSE 0.0 END) AS hotspot_alert_rate,
        COUNT(DISTINCT hotspot_model_version) AS hotspot_model_versions
    FROM ml_hotspot_forecasts
    GROUP BY 1
),
combined_monthly AS (
    SELECT
        date_trunc('month', score_ts_utc)::date AS month_start,
        COUNT(*) AS combined_rows,
        AVG(expected_severe_harm) AS avg_expected_severe_harm,
        AVG(CASE WHEN risk_tier = 'high' THEN 1.0 ELSE 0.0 END) AS high_risk_share,
        MAX(score_ts_utc) AS latest_score_ts_utc
    FROM ml_combined_risk_rankings
    GROUP BY 1
)
SELECT
    c.month_start,
    c.combined_rows,
    s.severity_rows,
    h.hotspot_rows,
    c.avg_expected_severe_harm,
    c.high_risk_share,
    h.hotspot_alert_rate,
    s.severity_model_versions,
    h.hotspot_model_versions,
    c.latest_score_ts_utc
FROM combined_monthly c
LEFT JOIN severity_monthly s USING (month_start)
LEFT JOIN hotspot_monthly h USING (month_start)
ORDER BY c.month_start DESC;
```

## Final Acceptance Checklist

- [ ] all release gates passed
- [ ] prediction tables populated
- [ ] monitoring jobs active
- [ ] documentation updated
