-- build_ml_hotspot_timeseries.sql
-- Purpose: Build hotspot time-series features at (grid_id, time_bucket) grain.
-- Output grain: one row per grid_id per time_bucket.

DROP TABLE IF EXISTS ml_hotspot_ts_v1;

CREATE TABLE ml_hotspot_ts_v1 AS
WITH params AS (
    SELECT
        0.01::NUMERIC AS lat_bin_size_deg,
        0.01::NUMERIC AS lon_bin_size_deg
),
base_events AS (
    SELECT
        c.crash_record_id,
        c.crash_date,
        date_trunc('hour', c.crash_date) AS time_bucket,
        FLOOR(c.latitude / p.lat_bin_size_deg)::BIGINT AS lat_bin,
        FLOOR(c.longitude / p.lon_bin_size_deg)::BIGINT AS lon_bin,
        CASE
            WHEN cc.weather_condition IS NULL THEN 'unknown'
            WHEN UPPER(cc.weather_condition) LIKE '%SNOW%' OR UPPER(cc.weather_condition) LIKE '%SLEET%' OR UPPER(cc.weather_condition) LIKE '%HAIL%' THEN 'snow'
            WHEN UPPER(cc.weather_condition) LIKE '%RAIN%' OR UPPER(cc.weather_condition) LIKE '%DRIZZLE%' OR UPPER(cc.weather_condition) LIKE '%THUNDER%' THEN 'rain'
            WHEN UPPER(cc.weather_condition) LIKE '%FOG%' OR UPPER(cc.weather_condition) LIKE '%SMOKE%' OR UPPER(cc.weather_condition) LIKE '%BLOWING%' THEN 'low_visibility'
            WHEN UPPER(cc.weather_condition) LIKE '%CLOUD%' THEN 'cloudy'
            WHEN UPPER(cc.weather_condition) LIKE '%CLEAR%' THEN 'clear'
            ELSE 'other'
        END AS weather_category
    FROM crashes c
    CROSS JOIN params p
    LEFT JOIN crash_circumstances cc
        ON cc.crash_record_id = c.crash_record_id
    WHERE c.crash_record_id IS NOT NULL
      AND c.crash_date IS NOT NULL
      AND c.latitude IS NOT NULL
      AND c.longitude IS NOT NULL
),
weather_counts AS (
    SELECT
        CONCAT('lat', lat_bin, '_lon', lon_bin) AS grid_id,
        time_bucket,
        weather_category,
        COUNT(*) AS weather_obs_count
    FROM base_events
    GROUP BY
        CONCAT('lat', lat_bin, '_lon', lon_bin),
        time_bucket,
        weather_category
),
dominant_weather AS (
    SELECT
        wc.grid_id,
        wc.time_bucket,
        wc.weather_category,
        ROW_NUMBER() OVER (
            PARTITION BY wc.grid_id, wc.time_bucket
            ORDER BY wc.weather_obs_count DESC, wc.weather_category
        ) AS weather_rank
    FROM weather_counts wc
),
freshness AS (
    SELECT MAX(crash_date) AS data_freshness_ts
    FROM crashes
),
aggregated AS (
    SELECT
        CONCAT('lat', be.lat_bin, '_lon', be.lon_bin) AS grid_id,
        be.time_bucket,
        COUNT(*)::INT AS crash_count
    FROM base_events be
    GROUP BY
        CONCAT('lat', be.lat_bin, '_lon', be.lon_bin),
        be.time_bucket
)
SELECT
    a.grid_id,
    a.time_bucket,
    a.crash_count,

    -- Exogenous features.
    COALESCE(dw.weather_category, 'unknown') AS weather_category,
    EXTRACT(ISODOW FROM a.time_bucket)::INT AS day_of_week,
    CASE
        WHEN EXTRACT(ISODOW FROM a.time_bucket) IN (6, 7) THEN TRUE
        ELSE FALSE
    END AS is_weekend,
    CASE
        WHEN a.time_bucket::DATE = make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 1, 1) THEN TRUE
        WHEN a.time_bucket::DATE = make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 6, 19) THEN TRUE
        WHEN a.time_bucket::DATE = make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 7, 4) THEN TRUE
        WHEN a.time_bucket::DATE = make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 11, 11) THEN TRUE
        WHEN a.time_bucket::DATE = make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 12, 25) THEN TRUE
        WHEN a.time_bucket::DATE = (
            date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 1, 1))::DATE
            + INTERVAL '14 days'
            + (((1 - EXTRACT(ISODOW FROM date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 1, 1))::DATE)::INT + 7) % 7)) * INTERVAL '1 day'
        )::DATE THEN TRUE -- MLK Day (3rd Monday Jan)
        WHEN a.time_bucket::DATE = (
            date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 2, 1))::DATE
            + INTERVAL '14 days'
            + (((1 - EXTRACT(ISODOW FROM date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 2, 1))::DATE)::INT + 7) % 7)) * INTERVAL '1 day'
        )::DATE THEN TRUE -- Presidents' Day (3rd Monday Feb)
        WHEN a.time_bucket::DATE = (
            (date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 6, 1))::DATE - INTERVAL '1 day')::DATE
            - (((EXTRACT(ISODOW FROM (date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 6, 1))::DATE - INTERVAL '1 day')::DATE)::INT - 1 + 7) % 7)) * INTERVAL '1 day'
        )::DATE THEN TRUE -- Memorial Day (last Monday May)
        WHEN a.time_bucket::DATE = (
            date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 9, 1))::DATE
            + (((1 - EXTRACT(ISODOW FROM date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 9, 1))::DATE)::INT + 7) % 7)) * INTERVAL '1 day'
        )::DATE THEN TRUE -- Labor Day (1st Monday Sep)
        WHEN a.time_bucket::DATE = (
            date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 10, 1))::DATE
            + INTERVAL '7 days'
            + (((1 - EXTRACT(ISODOW FROM date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 10, 1))::DATE)::INT + 7) % 7)) * INTERVAL '1 day'
        )::DATE THEN TRUE -- Columbus Day (2nd Monday Oct)
        WHEN a.time_bucket::DATE = (
            date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 11, 1))::DATE
            + INTERVAL '21 days'
            + (((4 - EXTRACT(ISODOW FROM date_trunc('month', make_date(EXTRACT(YEAR FROM a.time_bucket)::INT, 11, 1))::DATE)::INT + 7) % 7)) * INTERVAL '1 day'
        )::DATE THEN TRUE -- Thanksgiving (4th Thursday Nov)
        ELSE FALSE
    END AS is_holiday,

    -- Snapshot freshness metadata.
    f.data_freshness_ts
FROM aggregated a
LEFT JOIN dominant_weather dw
    ON dw.grid_id = a.grid_id
   AND dw.time_bucket = a.time_bucket
   AND dw.weather_rank = 1
CROSS JOIN freshness f;

-- Data quality checks: row-count, uniqueness, and null-key validation.
DO $$
DECLARE
    v_rows BIGINT;
    v_expected_rows BIGINT;
    v_duplicate_keys BIGINT;
    v_null_keys BIGINT;
BEGIN
    SELECT COUNT(*) INTO v_rows
    FROM ml_hotspot_ts_v1;

    SELECT COUNT(*) INTO v_expected_rows
    FROM (
        SELECT
            CONCAT('lat', FLOOR(c.latitude / 0.01)::BIGINT, '_lon', FLOOR(c.longitude / 0.01)::BIGINT) AS grid_id,
            date_trunc('hour', c.crash_date) AS time_bucket
        FROM crashes c
        WHERE c.crash_record_id IS NOT NULL
          AND c.crash_date IS NOT NULL
          AND c.latitude IS NOT NULL
          AND c.longitude IS NOT NULL
        GROUP BY 1, 2
    ) s;

    SELECT COUNT(*) INTO v_duplicate_keys
    FROM (
        SELECT grid_id, time_bucket
        FROM ml_hotspot_ts_v1
        GROUP BY grid_id, time_bucket
        HAVING COUNT(*) > 1
    ) d;

    SELECT COUNT(*) INTO v_null_keys
    FROM ml_hotspot_ts_v1
    WHERE grid_id IS NULL OR time_bucket IS NULL;

    IF v_rows = 0 THEN
        RAISE EXCEPTION 'ml_hotspot_ts_v1 check failed: table has 0 rows';
    END IF;

    IF v_rows <> v_expected_rows THEN
        RAISE EXCEPTION 'ml_hotspot_ts_v1 check failed: row_count (%) != expected grouped rows (%)', v_rows, v_expected_rows;
    END IF;

    IF v_duplicate_keys > 0 THEN
        RAISE EXCEPTION 'ml_hotspot_ts_v1 check failed: duplicate (grid_id,time_bucket) rows found (%)', v_duplicate_keys;
    END IF;

    IF v_null_keys > 0 THEN
        RAISE EXCEPTION 'ml_hotspot_ts_v1 check failed: null key rows found (%)', v_null_keys;
    END IF;

    RAISE NOTICE 'ml_hotspot_ts_v1 checks passed: rows=%, expected_rows=%, duplicate_keys=%, null_keys=%',
        v_rows, v_expected_rows, v_duplicate_keys, v_null_keys;
END $$;
