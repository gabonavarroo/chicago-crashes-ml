-- build_prediction_tables.sql
-- Purpose: Persist model predictions and metadata for downstream consumers.

CREATE TABLE IF NOT EXISTS ml_severity_predictions (
    crash_record_id TEXT NOT NULL,
    crash_date TIMESTAMP,
    time_bucket TIMESTAMP NOT NULL,
    grid_id TEXT NOT NULL,
    severity_probability DOUBLE PRECISION NOT NULL,
    risk_tier TEXT NOT NULL CHECK (risk_tier IN ('low', 'medium', 'high')),
    score_ts_utc TIMESTAMPTZ NOT NULL,
    severity_model_version TEXT NOT NULL,
    snapshot_version TEXT NOT NULL,
    snapshot_extraction_date DATE NOT NULL,
    PRIMARY KEY (crash_record_id, score_ts_utc)
);

CREATE TABLE IF NOT EXISTS ml_hotspot_forecasts (
    grid_id TEXT NOT NULL,
    forecast_anchor_time TIMESTAMP NOT NULL,
    forecast_time TIMESTAMP NOT NULL,
    horizon_hours INT NOT NULL CHECK (horizon_hours > 0),
    predicted_crash_count DOUBLE PRECISION NOT NULL CHECK (predicted_crash_count >= 0),
    hotspot_alert_score DOUBLE PRECISION,
    is_hotspot_alert BOOLEAN,
    score_ts_utc TIMESTAMPTZ NOT NULL,
    hotspot_model_version TEXT NOT NULL,
    snapshot_version TEXT NOT NULL,
    snapshot_extraction_date DATE NOT NULL,
    version_metadata JSONB,
    PRIMARY KEY (grid_id, forecast_time, horizon_hours, score_ts_utc)
);

CREATE TABLE IF NOT EXISTS ml_combined_risk_rankings (
    grid_id TEXT NOT NULL,
    forecast_time TIMESTAMP NOT NULL,
    horizon_hours INT NOT NULL CHECK (horizon_hours > 0),
    expected_severe_harm DOUBLE PRECISION NOT NULL CHECK (expected_severe_harm >= 0),
    risk_rank BIGINT NOT NULL CHECK (risk_rank > 0),
    risk_tier TEXT NOT NULL CHECK (risk_tier IN ('low', 'medium', 'high')),
    severity_probability DOUBLE PRECISION NOT NULL,
    predicted_crash_count DOUBLE PRECISION NOT NULL CHECK (predicted_crash_count >= 0),
    score_ts_utc TIMESTAMPTZ NOT NULL,
    severity_model_version TEXT NOT NULL,
    hotspot_model_version TEXT NOT NULL,
    snapshot_version TEXT NOT NULL,
    snapshot_extraction_date DATE NOT NULL,
    PRIMARY KEY (grid_id, forecast_time, horizon_hours, score_ts_utc)
);

-- Severity read paths: by date/time, grid, and risk tier.
CREATE INDEX IF NOT EXISTS idx_ml_severity_predictions_crash_date
    ON ml_severity_predictions (crash_date DESC);
CREATE INDEX IF NOT EXISTS idx_ml_severity_predictions_grid_time
    ON ml_severity_predictions (grid_id, time_bucket DESC);
CREATE INDEX IF NOT EXISTS idx_ml_severity_predictions_risk_tier
    ON ml_severity_predictions (risk_tier, score_ts_utc DESC);

-- Hotspot read paths: by forecast date/time and grid.
CREATE INDEX IF NOT EXISTS idx_ml_hotspot_forecasts_forecast_time
    ON ml_hotspot_forecasts (forecast_time DESC);
CREATE INDEX IF NOT EXISTS idx_ml_hotspot_forecasts_grid_time
    ON ml_hotspot_forecasts (grid_id, forecast_time DESC);
CREATE INDEX IF NOT EXISTS idx_ml_hotspot_forecasts_horizon
    ON ml_hotspot_forecasts (horizon_hours, forecast_time DESC);

-- Combined risk read paths: by date/time, grid, and risk tier.
CREATE INDEX IF NOT EXISTS idx_ml_combined_risk_rankings_forecast_time
    ON ml_combined_risk_rankings (forecast_time DESC);
CREATE INDEX IF NOT EXISTS idx_ml_combined_risk_rankings_grid_time
    ON ml_combined_risk_rankings (grid_id, forecast_time DESC);
CREATE INDEX IF NOT EXISTS idx_ml_combined_risk_rankings_risk_tier
    ON ml_combined_risk_rankings (risk_tier, forecast_time DESC);
CREATE INDEX IF NOT EXISTS idx_ml_combined_risk_rankings_rank
    ON ml_combined_risk_rankings (risk_rank, forecast_time DESC);
