-- build_ml_crash_base.sql
-- Purpose: Build crash-grain ML base features by joining canonical crash tables.
-- Output grain: exactly one row per crash_record_id.

DROP TABLE IF EXISTS ml_crash_base_v1;

CREATE TABLE ml_crash_base_v1 AS
WITH vehicle_agg AS (
    SELECT
        v.crash_record_id,
        COUNT(*)::INT AS vehicle_count,
        COALESCE(
            SUM(CASE WHEN UPPER(COALESCE(v.unit_type, 'UNKNOWN')) LIKE '%DRIVER%' THEN 1 ELSE 0 END)::NUMERIC
            / NULLIF(COUNT(*)::NUMERIC, 0),
            0
        ) AS prop_unit_type_driver,
        COALESCE(
            SUM(CASE WHEN UPPER(COALESCE(v.vehicle_type, 'UNKNOWN')) LIKE '%TRUCK%' THEN 1 ELSE 0 END)::NUMERIC
            / NULLIF(COUNT(*)::NUMERIC, 0),
            0
        ) AS prop_vehicle_type_truck,
        COALESCE(
            SUM(CASE WHEN UPPER(COALESCE(v.vehicle_type, 'UNKNOWN')) LIKE '%MOTORCYCLE%' THEN 1 ELSE 0 END)::NUMERIC
            / NULLIF(COUNT(*)::NUMERIC, 0),
            0
        ) AS prop_vehicle_type_motorcycle,
        COALESCE(
            SUM(CASE WHEN UPPER(COALESCE(v.vehicle_type, 'UNKNOWN')) LIKE '%BICYCLE%' THEN 1 ELSE 0 END)::NUMERIC
            / NULLIF(COUNT(*)::NUMERIC, 0),
            0
        ) AS prop_vehicle_type_bicycle
    FROM vehicles v
    WHERE v.crash_record_id IS NOT NULL
    GROUP BY v.crash_record_id
),
person_agg AS (
    SELECT
        p.crash_record_id,
        COUNT(*)::INT AS person_count,
        SUM(CASE WHEN UPPER(COALESCE(p.person_type, 'UNKNOWN')) = 'DRIVER' THEN 1 ELSE 0 END)::INT AS driver_count,
        SUM(CASE WHEN UPPER(COALESCE(p.person_type, 'UNKNOWN')) LIKE '%PEDESTRIAN%' THEN 1 ELSE 0 END)::INT AS pedestrian_count,
        SUM(CASE WHEN UPPER(COALESCE(p.person_type, 'UNKNOWN')) LIKE '%BICYCLE%' THEN 1 ELSE 0 END)::INT AS cyclist_count,
        COALESCE(
            SUM(CASE WHEN UPPER(COALESCE(p.sex, 'UNKNOWN')) = 'M' THEN 1 ELSE 0 END)::NUMERIC
            / NULLIF(COUNT(*)::NUMERIC, 0),
            0
        ) AS prop_person_male,
        COALESCE(
            SUM(CASE WHEN UPPER(COALESCE(p.injury_classification, 'NO INDICATION OF INJURY')) NOT LIKE '%NO INDICATION%' THEN 1 ELSE 0 END)::NUMERIC
            / NULLIF(COUNT(*)::NUMERIC, 0),
            0
        ) AS prop_person_injured
    FROM people p
    WHERE p.crash_record_id IS NOT NULL
    GROUP BY p.crash_record_id
),
driver_agg AS (
    SELECT
        p.crash_record_id,
        SUM(CASE WHEN COALESCE(d.cell_phone_use, FALSE) THEN 1 ELSE 0 END)::INT AS driver_cell_phone_use_count,
        SUM(CASE WHEN COALESCE(d.bac_result_value, 0) > 0 THEN 1 ELSE 0 END)::INT AS driver_positive_bac_count,
        COALESCE(
            SUM(CASE WHEN COALESCE(d.cell_phone_use, FALSE) THEN 1 ELSE 0 END)::NUMERIC
            / NULLIF(COUNT(*)::NUMERIC, 0),
            0
        ) AS prop_driver_cell_phone_use,
        COALESCE(
            SUM(CASE WHEN COALESCE(d.bac_result_value, 0) > 0 THEN 1 ELSE 0 END)::NUMERIC
            / NULLIF(COUNT(*)::NUMERIC, 0),
            0
        ) AS prop_driver_positive_bac
    FROM people p
    LEFT JOIN people_driver_info d
        ON d.person_id = p.person_id
    WHERE p.crash_record_id IS NOT NULL
      AND UPPER(COALESCE(p.person_type, 'UNKNOWN')) = 'DRIVER'
    GROUP BY p.crash_record_id
),
freshness AS (
    SELECT MAX(c.crash_date) AS data_freshness_ts
    FROM crashes c
)
SELECT
    c.crash_record_id,
    c.crash_date,
    EXTRACT(HOUR FROM c.crash_date)::INT AS crash_hour,
    CASE
        WHEN EXTRACT(ISODOW FROM c.crash_date) IN (6, 7) THEN TRUE
        ELSE FALSE
    END AS is_weekend,
    CASE
        WHEN EXTRACT(MONTH FROM c.crash_date) IN (12, 1, 2) THEN 'winter'
        WHEN EXTRACT(MONTH FROM c.crash_date) IN (3, 4, 5) THEN 'spring'
        WHEN EXTRACT(MONTH FROM c.crash_date) IN (6, 7, 8) THEN 'summer'
        ELSE 'fall'
    END AS season,
    COALESCE(cd.crash_day_of_week, EXTRACT(ISODOW FROM c.crash_date)::INT) AS crash_day_of_week,
    COALESCE(cd.crash_month, EXTRACT(MONTH FROM c.crash_date)::INT) AS crash_month,
    c.latitude,
    c.longitude,
    CASE
        WHEN c.latitude IS NOT NULL AND c.longitude IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS has_coordinates,

    -- Environment fields (null-handled to canonical defaults).
    COALESCE(cc.weather_condition, 'UNKNOWN') AS weather_condition,
    COALESCE(cc.lighting_condition, 'UNKNOWN') AS lighting_condition,
    COALESCE(cc.traffic_control_device, 'UNKNOWN') AS traffic_control_device,
    COALESCE(cc.device_condition, 'UNKNOWN') AS device_condition,

    -- Road fields (null-handled to numeric/category defaults).
    COALESCE(cc.lane_cnt, 0) AS lane_cnt,
    COALESCE(cc.roadway_surface_cond, 'UNKNOWN') AS roadway_surface_cond,
    COALESCE(cc.road_defect, 'UNKNOWN') AS road_defect,
    COALESCE(cc.posted_speed_limit, 0) AS posted_speed_limit,
    COALESCE(cc.intersection_related_i, FALSE) AS intersection_related_i,
    COALESCE(cc.not_right_of_way_i, FALSE) AS not_right_of_way_i,
    COALESCE(cc.num_units, 0) AS num_units,

    -- Classification fields.
    COALESCE(cl.first_crash_type, 'UNKNOWN') AS first_crash_type,
    COALESCE(cl.crash_type, 'UNKNOWN') AS crash_type,
    COALESCE(cl.prim_contributory_cause, 'UNKNOWN') AS prim_contributory_cause,
    COALESCE(cl.sec_contributory_cause, 'UNKNOWN') AS sec_contributory_cause,
    COALESCE(cl.damage, 'UNKNOWN') AS damage,
    COALESCE(cl.hit_and_run_i, FALSE) AS hit_and_run_i,

    -- Injury counts (null->0).
    COALESCE(ci.injuries_fatal, 0) AS injuries_fatal,
    COALESCE(ci.injuries_incapacitating, 0) AS injuries_incapacitating,
    COALESCE(ci.injuries_others, 0) AS injuries_others,
    CASE
        WHEN COALESCE(ci.injuries_fatal, 0) > 0 OR COALESCE(ci.injuries_incapacitating, 0) > 0 THEN 1
        ELSE 0
    END AS severe_injury_flag,

    -- Vehicle/person aggregates at crash grain (counts/proportions only).
    COALESCE(va.vehicle_count, 0) AS vehicle_count,
    COALESCE(va.prop_unit_type_driver, 0) AS prop_unit_type_driver,
    COALESCE(va.prop_vehicle_type_truck, 0) AS prop_vehicle_type_truck,
    COALESCE(va.prop_vehicle_type_motorcycle, 0) AS prop_vehicle_type_motorcycle,
    COALESCE(va.prop_vehicle_type_bicycle, 0) AS prop_vehicle_type_bicycle,
    COALESCE(pa.person_count, 0) AS person_count,
    COALESCE(pa.driver_count, 0) AS driver_count,
    COALESCE(pa.pedestrian_count, 0) AS pedestrian_count,
    COALESCE(pa.cyclist_count, 0) AS cyclist_count,
    COALESCE(pa.prop_person_male, 0) AS prop_person_male,
    COALESCE(pa.prop_person_injured, 0) AS prop_person_injured,
    COALESCE(da.driver_cell_phone_use_count, 0) AS driver_cell_phone_use_count,
    COALESCE(da.driver_positive_bac_count, 0) AS driver_positive_bac_count,
    COALESCE(da.prop_driver_cell_phone_use, 0) AS prop_driver_cell_phone_use,
    COALESCE(da.prop_driver_positive_bac, 0) AS prop_driver_positive_bac,

    -- Snapshot freshness metadata.
    f.data_freshness_ts
FROM crashes c
LEFT JOIN crash_date cd
    ON cd.crash_record_id = c.crash_record_id
LEFT JOIN crash_circumstances cc
    ON cc.crash_record_id = c.crash_record_id
LEFT JOIN crash_classification cl
    ON cl.crash_record_id = c.crash_record_id
LEFT JOIN crash_injuries ci
    ON ci.crash_record_id = c.crash_record_id
LEFT JOIN vehicle_agg va
    ON va.crash_record_id = c.crash_record_id
LEFT JOIN person_agg pa
    ON pa.crash_record_id = c.crash_record_id
LEFT JOIN driver_agg da
    ON da.crash_record_id = c.crash_record_id
CROSS JOIN freshness f
WHERE c.crash_record_id IS NOT NULL
  AND c.crash_date IS NOT NULL;

-- Data quality checks: row-count parity and crash-key uniqueness at crash grain.
DO $$
DECLARE
    v_rows BIGINT;
    v_expected_rows BIGINT;
    v_duplicate_keys BIGINT;
    v_null_keys BIGINT;
BEGIN
    SELECT COUNT(*) INTO v_rows
    FROM ml_crash_base_v1;

    SELECT COUNT(*) INTO v_expected_rows
    FROM crashes
    WHERE crash_record_id IS NOT NULL
      AND crash_date IS NOT NULL;

    SELECT COUNT(*) INTO v_duplicate_keys
    FROM (
        SELECT crash_record_id
        FROM ml_crash_base_v1
        GROUP BY crash_record_id
        HAVING COUNT(*) > 1
    ) d;

    SELECT COUNT(*) INTO v_null_keys
    FROM ml_crash_base_v1
    WHERE crash_record_id IS NULL;

    IF v_rows = 0 THEN
        RAISE EXCEPTION 'ml_crash_base_v1 check failed: table has 0 rows';
    END IF;

    IF v_rows <> v_expected_rows THEN
        RAISE EXCEPTION 'ml_crash_base_v1 check failed: row_count (%) != expected crash rows (%)', v_rows, v_expected_rows;
    END IF;

    IF v_duplicate_keys > 0 THEN
        RAISE EXCEPTION 'ml_crash_base_v1 check failed: duplicate crash_record_id rows found (%)', v_duplicate_keys;
    END IF;

    IF v_null_keys > 0 THEN
        RAISE EXCEPTION 'ml_crash_base_v1 check failed: null crash_record_id rows found (%)', v_null_keys;
    END IF;

    RAISE NOTICE 'ml_crash_base_v1 checks passed: rows=%, expected_rows=%, duplicate_keys=%, null_keys=%',
        v_rows, v_expected_rows, v_duplicate_keys, v_null_keys;
END $$;
