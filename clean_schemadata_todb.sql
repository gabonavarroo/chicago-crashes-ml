-- =====================================================
-- SCRIPT COMPLETO DE LIMPIEZA Y NORMALIZACIÓN
-- Crashes, Vehicles y People - PostgreSQL
-- =====================================================

-- =====================================================
-- PARTE 1: LIMPIEZA DE CRASHES
-- =====================================================

-- Limpiar CRASH_RECORD_ID
UPDATE crashes_full
SET crash_record_id = TRIM(crash_record_id)
WHERE crash_record_id IS NOT NULL;

UPDATE crashes_full
SET crash_record_id = NULL
WHERE crash_record_id IN ('', 'nan', 'None', 'NULL');

-- Eliminar duplicados por CRASH_RECORD_ID
DELETE FROM crashes_full a
USING crashes_full b
WHERE a.ctid < b.ctid 
  AND a.crash_record_id = b.crash_record_id;

-- Validar CRASH_DAY_OF_WEEK (1-7)
UPDATE crashes_full
SET crash_day_of_week = NULL
WHERE crash_day_of_week < 1 OR crash_day_of_week > 7;

-- Validar CRASH_MONTH (1-12)
UPDATE crashes_full
SET crash_month = NULL
WHERE crash_month < 1 OR crash_month > 12;

-- Validar CRASH_DATE
UPDATE crashes_full
SET crash_date = NULL
WHERE crash_date > CURRENT_TIMESTAMP;

-- Limpiar LATITUDE y LONGITUDE
UPDATE crashes_full
SET latitude = NULL
WHERE latitude IS NULL OR latitude::text !~ '^-?[0-9]+(\.[0-9]+)?$';

UPDATE crashes_full
SET longitude = NULL
WHERE longitude IS NULL OR longitude::text !~ '^-?[0-9]+(\.[0-9]+)?$';

-- Limpiar STREET_NO
UPDATE crashes_full
SET street_no = TRIM(street_no)
WHERE street_no IS NOT NULL;

UPDATE crashes_full
SET street_no = NULL
WHERE street_no IN ('', 'nan', 'None', 'NULL');

-- Limpiar STREET_NAME
UPDATE crashes_full
SET street_name = UPPER(TRIM(REGEXP_REPLACE(street_name, '\s+', ' ', 'g')))
WHERE street_name IS NOT NULL;

UPDATE crashes_full
SET street_name = NULL
WHERE street_name IN ('', 'nan', 'None', 'NULL');

-- Limpiar LANE_CNT
UPDATE crashes_full
SET lane_cnt = REPLACE(lane_cnt::text, ',', '')::INTEGER
WHERE lane_cnt IS NOT NULL;

UPDATE crashes_full
SET lane_cnt = NULL
WHERE lane_cnt < 0 OR lane_cnt > 26;

-- Convertir campos booleanos (Y/N a TRUE/FALSE)
UPDATE crashes_full
SET intersection_related_i = CASE 
    WHEN UPPER(TRIM(intersection_related_i)) = 'Y' THEN TRUE
    WHEN UPPER(TRIM(intersection_related_i)) = 'N' THEN FALSE
    ELSE NULL
END;

UPDATE crashes_full
SET not_right_of_way_i = CASE 
    WHEN UPPER(TRIM(not_right_of_way_i)) = 'Y' THEN TRUE
    WHEN UPPER(TRIM(not_right_of_way_i)) = 'N' THEN FALSE
    ELSE NULL
END;

-- Limpiar campos categóricos
UPDATE crashes_full
SET traffic_control_device = UPPER(TRIM(REGEXP_REPLACE(traffic_control_device, '\s+', ' ', 'g')))
WHERE traffic_control_device IS NOT NULL;

UPDATE crashes_full
SET traffic_control_device = NULL
WHERE traffic_control_device IN ('', 'NAN', 'NONE');

UPDATE crashes_full
SET device_condition = UPPER(TRIM(REGEXP_REPLACE(device_condition, '\s+', ' ', 'g')))
WHERE device_condition IS NOT NULL;

UPDATE crashes_full
SET device_condition = NULL
WHERE device_condition IN ('', 'NAN', 'NONE');

UPDATE crashes_full
SET weather_condition = UPPER(TRIM(REGEXP_REPLACE(weather_condition, '\s+', ' ', 'g')))
WHERE weather_condition IS NOT NULL;

UPDATE crashes_full
SET weather_condition = NULL
WHERE weather_condition IN ('', 'NAN', 'NONE');

UPDATE crashes_full
SET lighting_condition = UPPER(TRIM(REGEXP_REPLACE(lighting_condition, '\s+', ' ', 'g')))
WHERE lighting_condition IS NOT NULL;

UPDATE crashes_full
SET lighting_condition = NULL
WHERE lighting_condition IN ('', 'NAN', 'NONE');

UPDATE crashes_full
SET roadway_surface_cond = UPPER(TRIM(REGEXP_REPLACE(roadway_surface_cond, '\s+', ' ', 'g')))
WHERE roadway_surface_cond IS NOT NULL;

UPDATE crashes_full
SET roadway_surface_cond = NULL
WHERE roadway_surface_cond IN ('', 'NAN', 'NONE');

UPDATE crashes_full
SET road_defect = UPPER(TRIM(REGEXP_REPLACE(road_defect, '\s+', ' ', 'g')))
WHERE road_defect IS NOT NULL;

UPDATE crashes_full
SET road_defect = NULL
WHERE road_defect IN ('', 'NAN', 'NONE');

-- Limpiar CRASH_CLASSIFICATION
UPDATE crashes_full
SET first_crash_type = TRIM(first_crash_type),
    crash_type = TRIM(crash_type),
    prim_contributory_cause = TRIM(prim_contributory_cause),
    sec_contributory_cause = TRIM(sec_contributory_cause),
    damage = TRIM(damage)
WHERE first_crash_type IS NOT NULL OR crash_type IS NOT NULL;

UPDATE crashes_full
SET first_crash_type = NULL
WHERE first_crash_type IN ('', 'NaN', 'NAN', 'nan', 'NULL', 'Null', 'null');

UPDATE crashes_full
SET crash_type = NULL
WHERE crash_type IN ('', 'NaN', 'NAN', 'nan', 'NULL', 'Null', 'null');

UPDATE crashes_full
SET prim_contributory_cause = NULL
WHERE prim_contributory_cause IN ('', 'NaN', 'NAN', 'nan', 'NULL', 'Null', 'null');

UPDATE crashes_full
SET sec_contributory_cause = NULL
WHERE sec_contributory_cause IN ('', 'NaN', 'NAN', 'nan', 'NULL', 'Null', 'null');

UPDATE crashes_full
SET damage = NULL
WHERE damage IN ('', 'NaN', 'NAN', 'nan', 'NULL', 'Null', 'null');

UPDATE crashes_full
SET hit_and_run_i = CASE 
    WHEN UPPER(TRIM(hit_and_run_i)) = 'Y' THEN TRUE
    WHEN UPPER(TRIM(hit_and_run_i)) = 'N' THEN FALSE
    ELSE NULL
END;

-- Validar CRASH_INJURIES
UPDATE crashes_full
SET injuries_fatal = NULL
WHERE injuries_fatal < 0;

UPDATE crashes_full
SET injuries_incapacitating = NULL
WHERE injuries_incapacitating < 0;

UPDATE crashes_full
SET injuries_total = NULL
WHERE injuries_total < 0;

-- Calcular INJURIES_OTHERS
ALTER TABLE crashes_full ADD COLUMN IF NOT EXISTS injuries_others INTEGER;

UPDATE crashes_full
SET injuries_others = injuries_total - COALESCE(injuries_fatal, 0) - COALESCE(injuries_incapacitating, 0)
WHERE injuries_total IS NOT NULL;

-- =====================================================
-- PARTE 2: LIMPIEZA DE VEHICLES
-- =====================================================

-- Eliminar registros con VEHICLE_ID nulo o inválido
DELETE FROM vehicles_full
WHERE VEHICLE_ID IS NULL 
   OR VEHICLE_ID::text !~ '^[0-9]+(\.[0-9]+)?$';

-- Eliminar duplicados por VEHICLE_ID
DELETE FROM vehicles_full a
USING vehicles_full b
WHERE a.ctid < b.ctid 
  AND a.vehicle_id = b.vehicle_id;

-- Limpiar CRASH_RECORD_ID
UPDATE vehicles_full
SET crash_record_id = TRIM(crash_record_id)
WHERE crash_record_id IS NOT NULL;

-- Validar CRASH_DATE
DELETE FROM vehicles_full
WHERE crash_date > CURRENT_TIMESTAMP;

-- Limpiar y validar UNIT_NO
UPDATE vehicles_full
SET unit_no = NULL
WHERE unit_no < 0 OR unit_no > 50;

-- Limpiar NUM_PASSENGERS
UPDATE vehicles_full
SET num_passengers = NULL
WHERE num_passengers < 0 OR num_passengers > 70;

UPDATE vehicles_full
SET num_passengers = 0
WHERE num_passengers IS NULL;

-- Validar VEHICLE_YEAR
UPDATE vehicles_full
SET vehicle_year = NULL
WHERE vehicle_year < 1900 OR vehicle_year > 2026;

-- Limpiar campos de texto (MAKE, MODEL, VEHICLE_TYPE)
UPDATE vehicles_full
SET make = UPPER(TRIM(make))
WHERE make IS NOT NULL;

UPDATE vehicles_full
SET make = NULL
WHERE make IN ('', 'UNKNOWN', 'UNKNOWN/NA', 'UNK', 'N/A', 'NA', 
               'NONE', 'NULL', 'NAN', 'OTHER', 'OTHER (EXPLAIN IN NARRATIVE)', 
               'NOT APPLICABLE');

UPDATE vehicles_full
SET model = UPPER(TRIM(model))
WHERE model IS NOT NULL;

UPDATE vehicles_full
SET model = NULL
WHERE model IN ('', 'UNKNOWN', 'UNKNOWN/NA', 'UNK', 'N/A', 'NA', 
                'NONE', 'NULL', 'NAN', 'OTHER', 'OTHER (EXPLAIN IN NARRATIVE)', 
                'NOT APPLICABLE');

UPDATE vehicles_full
SET vehicle_type = UPPER(TRIM(vehicle_type))
WHERE vehicle_type IS NOT NULL;

UPDATE vehicles_full
SET vehicle_type = NULL
WHERE vehicle_type IN ('', 'UNKNOWN', 'UNKNOWN/NA', 'UNK', 'N/A', 'NA', 
                       'NONE', 'NULL', 'NAN', 'OTHER', 'OTHER (EXPLAIN IN NARRATIVE)', 
                       'NOT APPLICABLE');

-- Limpiar VEHICLE_SPECS
UPDATE vehicles_full
SET vehicle_use = UPPER(TRIM(vehicle_use))
WHERE vehicle_use IS NOT NULL;

UPDATE vehicles_full
SET vehicle_use = NULL
WHERE vehicle_use IN ('', 'UNKNOWN', 'UNKNOWN/NA', 'UNK', 'N/A', 'NA', 
                      'NONE', 'NULL', 'NAN', 'OTHER', 'OTHER (EXPLAIN IN NARRATIVE)', 
                      'NOT APPLICABLE');

UPDATE vehicles_full
SET vehicle_config = UPPER(TRIM(vehicle_config))
WHERE vehicle_config IS NOT NULL;

UPDATE vehicles_full
SET vehicle_config = NULL
WHERE vehicle_config IN ('', 'UNKNOWN', 'UNKNOWN/NA', 'UNK', 'N/A', 'NA', 
                         'NONE', 'NULL', 'NAN', 'OTHER', 'OTHER (EXPLAIN IN NARRATIVE)', 
                         'NOT APPLICABLE');

UPDATE vehicles_full
SET cargo_body_type = UPPER(TRIM(cargo_body_type))
WHERE cargo_body_type IS NOT NULL;

UPDATE vehicles_full
SET cargo_body_type = NULL
WHERE cargo_body_type IN ('', 'UNKNOWN', 'UNKNOWN/NA', 'UNK', 'N/A', 'NA', 
                          'NONE', 'NULL', 'NAN', 'OTHER', 'OTHER (EXPLAIN IN NARRATIVE)', 
                          'NOT APPLICABLE');

-- Limpiar MANEUVER
UPDATE vehicles_full
SET maneuver = UPPER(TRIM(maneuver))
WHERE maneuver IS NOT NULL;

UPDATE vehicles_full
SET maneuver = NULL
WHERE maneuver IN ('', 'UNKNOWN', 'UNKNOWN/NA', 'UNK', 'N/A', 'NA', 
                   'NULL', 'NAN', 'OTHER', 'OTHER (EXPLAIN IN NARRATIVE)', 
                   'NOT APPLICABLE');

-- Convertir campos booleanos de VEHICLE_VIOLATIONS
UPDATE vehicles_full
SET cmrc_veh_i = CASE 
    WHEN UPPER(cmrc_veh_i) = 'Y' THEN TRUE
    WHEN UPPER(cmrc_veh_i) = 'N' THEN FALSE
    ELSE NULL
END;

UPDATE vehicles_full
SET exceed_speed_limit_i = CASE 
    WHEN UPPER(exceed_speed_limit_i) = 'Y' THEN TRUE
    WHEN UPPER(exceed_speed_limit_i) = 'N' THEN FALSE
    ELSE NULL
END;

UPDATE vehicles_full
SET hazmat_present_i = CASE 
    WHEN UPPER(hazmat_present_i) = 'Y' THEN TRUE
    WHEN UPPER(hazmat_present_i) = 'N' THEN FALSE
    WHEN UPPER(hazmat_present_i) = 'U' THEN NULL
    ELSE NULL
END;

-- =====================================================
-- PARTE 3: LIMPIEZA DE PEOPLE
-- =====================================================

-- Limpiar PERSON_ID
UPDATE people_full
SET person_id = TRIM(person_id)
WHERE person_id IS NOT NULL;

-- Eliminar duplicados por PERSON_ID
DELETE FROM people_full a
USING people_full b
WHERE a.ctid < b.ctid 
  AND a.person_id = b.person_id;

-- Limpiar campos de texto
UPDATE people_full
SET person_type = NULL
WHERE person_type IN ('', ' ', 'NA', 'N/A', 'null', 'NULL');

UPDATE people_full
SET crash_record_id = TRIM(crash_record_id)
WHERE crash_record_id IS NOT NULL;

UPDATE people_full
SET crash_record_id = NULL
WHERE crash_record_id IN ('', ' ', 'NA', 'N/A', 'null', 'NULL');

-- Limpiar VEHICLE_ID
UPDATE people_full
SET vehicle_id = REGEXP_REPLACE(vehicle_id::text, '\.0$', '')::BIGINT
WHERE vehicle_id IS NOT NULL AND vehicle_id::text ~ '\.0$';

-- Validar CRASH_DATE
UPDATE people_full
SET crash_date = NULL
WHERE crash_date > CURRENT_TIMESTAMP;

-- Limpiar SEX
UPDATE people_full
SET sex = UPPER(TRIM(sex))
WHERE sex IS NOT NULL;

UPDATE people_full
SET sex = NULL
WHERE sex IN ('', ' ', 'NA', 'N/A', 'null', 'NULL');

-- Limpiar AGE
UPDATE people_full
SET age = NULL
WHERE age < 0 OR age > 120;

-- Limpiar SAFETY_EQUIPMENT
UPDATE people_full
SET safety_equipment = TRIM(safety_equipment)
WHERE safety_equipment IS NOT NULL;

UPDATE people_full
SET safety_equipment = NULL
WHERE safety_equipment IN ('USAGE UNKNOWN', '', ' ', 'NA', 'N/A', 'null', 'NULL');

-- Limpiar AIRBAG_DEPLOYED
UPDATE people_full
SET airbag_deployed = TRIM(airbag_deployed)
WHERE airbag_deployed IS NOT NULL;

UPDATE people_full
SET airbag_deployed = NULL
WHERE airbag_deployed IN ('DEPLOYMENT UNKNOWN', 'NOT APPLICABLE', '', ' ', 'NA', 'N/A', 'null', 'NULL');

-- Limpiar INJURY_CLASSIFICATION
UPDATE people_full
SET injury_classification = TRIM(injury_classification)
WHERE injury_classification IS NOT NULL;

UPDATE people_full
SET injury_classification = NULL
WHERE injury_classification IN ('', ' ', 'NA', 'N/A', 'null', 'NULL');

-- Limpiar DRIVER_ACTION
UPDATE people_full
SET driver_action = TRIM(driver_action)
WHERE driver_action IS NOT NULL;

UPDATE people_full
SET driver_action = NULL
WHERE driver_action IN ('UNKNOWN', '', ' ', 'NA', 'N/A', 'null', 'NULL');

-- Limpiar DRIVER_VISION
UPDATE people_full
SET driver_vision = TRIM(driver_vision)
WHERE driver_vision IS NOT NULL;

UPDATE people_full
SET driver_vision = NULL
WHERE driver_vision IN ('UNKNOWN', '', ' ', 'NA', 'N/A', 'null', 'NULL');

-- Limpiar PHYSICAL_CONDITION
UPDATE people_full
SET physical_condition = TRIM(physical_condition)
WHERE physical_condition IS NOT NULL;

UPDATE people_full
SET physical_condition = NULL
WHERE physical_condition IN ('UNKNOWN', '', ' ', 'NA', 'N/A', 'null', 'NULL');

-- Validar BAC_RESULT_VALUE
UPDATE people_full
SET bac_result_value = NULL
WHERE bac_result_value < 0 OR bac_result_value > 1;

-- Convertir CELL_PHONE_USE a boolean
UPDATE people_full
SET cell_phone_use = CASE 
    WHEN UPPER(TRIM(cell_phone_use)) = 'Y' THEN TRUE
    WHEN UPPER(TRIM(cell_phone_use)) = 'N' THEN FALSE
    ELSE NULL
END;

-- Limpiar DRIVERS_LICENSE_CLASS
UPDATE people_full
SET drivers_license_class = UPPER(TRIM(drivers_license_class))
WHERE drivers_license_class IS NOT NULL;

UPDATE people_full
SET drivers_license_class = NULL
WHERE drivers_license_class !~ '^[A-Z0-9]+$'
   OR drivers_license_class IN ('', ' ', 'NA', 'N/A', 'null', 'NULL');

-- =====================================================
-- CREAR TABLAS NORMALIZADAS
-- =====================================================

-- CRASHES
DROP TABLE IF EXISTS crashes CASCADE;
CREATE TABLE crashes (
    crash_record_id VARCHAR(128) PRIMARY KEY,
    crash_date TIMESTAMP NOT NULL,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    street_no VARCHAR(20),
    street_name VARCHAR(255)
);

DROP TABLE IF EXISTS crash_date CASCADE;
CREATE TABLE crash_date (
    crash_record_id VARCHAR(128) PRIMARY KEY REFERENCES crashes(crash_record_id),
    crash_day_of_week INTEGER,
    crash_month INTEGER
);

DROP TABLE IF EXISTS crash_circumstances CASCADE;
CREATE TABLE crash_circumstances (
    crash_record_id VARCHAR(128) PRIMARY KEY REFERENCES crashes(crash_record_id),
    traffic_control_device VARCHAR(100),
    device_condition VARCHAR(100),
    weather_condition VARCHAR(100),
    lighting_condition VARCHAR(100),
    lane_cnt INTEGER,
    roadway_surface_cond VARCHAR(100),
    road_defect VARCHAR(100),
    num_units INTEGER,
    posted_speed_limit INTEGER,
    intersection_related_i BOOLEAN,
    not_right_of_way_i BOOLEAN
);

DROP TABLE IF EXISTS crash_classification CASCADE;
CREATE TABLE crash_classification (
    crash_record_id VARCHAR(128) PRIMARY KEY REFERENCES crashes(crash_record_id),
    first_crash_type VARCHAR(150),
    crash_type VARCHAR(150),
    prim_contributory_cause VARCHAR(255),
    sec_contributory_cause VARCHAR(255),
    damage VARCHAR(100),
    hit_and_run_i BOOLEAN
);

DROP TABLE IF EXISTS crash_injuries CASCADE;
CREATE TABLE crash_injuries (
    crash_record_id VARCHAR(128) PRIMARY KEY REFERENCES crashes(crash_record_id),
    injuries_fatal INTEGER,
    injuries_incapacitating INTEGER,
    injuries_others INTEGER
);

-- VEHICLES
DROP TABLE IF EXISTS vehicles CASCADE;
CREATE TABLE vehicles (
    vehicle_id BIGINT PRIMARY KEY,
    crash_unit_id VARCHAR(128) NOT NULL,
    crash_record_id VARCHAR(128) NOT NULL,
    crash_date TIMESTAMP NOT NULL,
    unit_no INTEGER,
    unit_type VARCHAR(30),
    num_passengers INTEGER,
    vehicle_year INTEGER,
    make VARCHAR(200),
    model VARCHAR(200),
    vehicle_type VARCHAR(200)
);

DROP TABLE IF EXISTS vehicle_specs CASCADE;
CREATE TABLE vehicle_specs (
    vehicle_id BIGINT PRIMARY KEY REFERENCES vehicles(vehicle_id),
    vehicle_use VARCHAR(150),
    vehicle_config VARCHAR(150),
    cargo_body_type VARCHAR(150)
);

DROP TABLE IF EXISTS vehicle_maneuvers CASCADE;
CREATE TABLE vehicle_maneuvers (
    vehicle_id BIGINT PRIMARY KEY REFERENCES vehicles(vehicle_id),
    maneuver VARCHAR(150)
);

DROP TABLE IF EXISTS vehicle_violations CASCADE;
CREATE TABLE vehicle_violations (
    vehicle_id BIGINT PRIMARY KEY REFERENCES vehicles(vehicle_id),
    cmrc_veh_i BOOLEAN,
    exceed_speed_limit_i BOOLEAN,
    hazmat_present_i BOOLEAN,
    vehicle_defect VARCHAR(100)
);

-- PEOPLE
DROP TABLE IF EXISTS people CASCADE;
CREATE TABLE people (
    person_id VARCHAR(50) PRIMARY KEY,
    person_type VARCHAR(50),
    crash_record_id VARCHAR(128) REFERENCES crashes(crash_record_id),
    vehicle_id BIGINT,
    crash_date TIMESTAMP,
    sex VARCHAR(10),
    age INTEGER,
    safety_equipment VARCHAR(200),
    airbag_deployed VARCHAR(100),
    injury_classification VARCHAR(100)
);

DROP TABLE IF EXISTS people_driver_info CASCADE;
CREATE TABLE people_driver_info (
    person_id VARCHAR(50) PRIMARY KEY REFERENCES people(person_id),
    driver_action VARCHAR(50),
    driver_vision VARCHAR(50),
    physical_condition VARCHAR(50),
    bac_result_value FLOAT,
    cell_phone_use BOOLEAN,
    drivers_license_class VARCHAR(10)
);

-- =====================================================
-- INSERTAR DATOS EN TABLAS NORMALIZADAS
-- =====================================================

-- CRASHES
INSERT INTO crashes (crash_record_id, crash_date, latitude, longitude, street_no, street_name)
SELECT DISTINCT crash_record_id, crash_date, latitude, longitude, street_no, street_name
FROM crashes_full
WHERE crash_record_id IS NOT NULL
ORDER BY crash_record_id;

INSERT INTO crash_date (crash_record_id, crash_day_of_week, crash_month)
SELECT DISTINCT crash_record_id, crash_day_of_week, crash_month
FROM crashes_full
WHERE crash_record_id IS NOT NULL
ORDER BY crash_record_id;

INSERT INTO crash_circumstances (
    crash_record_id, traffic_control_device, device_condition, weather_condition,
    lighting_condition, lane_cnt, roadway_surface_cond, road_defect,
    num_units, posted_speed_limit, intersection_related_i, not_right_of_way_i
)
SELECT DISTINCT
    crash_record_id, traffic_control_device, device_condition, weather_condition,
    lighting_condition, lane_cnt, roadway_surface_cond, road_defect,
    num_units, posted_speed_limit, intersection_related_i, not_right_of_way_i
FROM crashes_full
WHERE crash_record_id IS NOT NULL
ORDER BY crash_record_id;

INSERT INTO crash_classification (
    crash_record_id, first_crash_type, crash_type, prim_contributory_cause,
    sec_contributory_cause, damage, hit_and_run_i
)
SELECT DISTINCT
    crash_record_id, first_crash_type, crash_type, prim_contributory_cause,
    sec_contributory_cause, damage, hit_and_run_i
FROM crashes_full
WHERE crash_record_id IS NOT NULL
ORDER BY crash_record_id;

INSERT INTO crash_injuries (crash_record_id, injuries_fatal, injuries_incapacitating, injuries_others)
SELECT DISTINCT crash_record_id, injuries_fatal, injuries_incapacitating, injuries_others
FROM crashes_full
WHERE crash_record_id IS NOT NULL
ORDER BY crash_record_id;

-- VEHICLES
INSERT INTO vehicles (
    vehicle_id, crash_unit_id, crash_record_id, crash_date,
    unit_no, unit_type, num_passengers, vehicle_year,
    make, model, vehicle_type
)
SELECT DISTINCT
    vehicle_id, crash_unit_id, crash_record_id, crash_date,
    unit_no, unit_type, num_passengers, vehicle_year,
    make, model, vehicle_type
FROM vehicles_full
WHERE vehicle_id IS NOT NULL
ORDER BY vehicle_id;

INSERT INTO vehicle_specs (vehicle_id, vehicle_use, vehicle_config, cargo_body_type)
SELECT DISTINCT vehicle_id, vehicle_use, vehicle_config, cargo_body_type
FROM vehicles_full
WHERE vehicle_id IS NOT NULL
ORDER BY vehicle_id;

INSERT INTO vehicle_maneuvers (vehicle_id, maneuver)
SELECT DISTINCT vehicle_id, maneuver
FROM vehicles_full
WHERE vehicle_id IS NOT NULL
ORDER BY vehicle_id;

INSERT INTO vehicle_violations (vehicle_id, cmrc_veh_i, exceed_speed_limit_i, 
                                 hazmat_present_i, vehicle_defect)
SELECT DISTINCT vehicle_id, cmrc_veh_i, exceed_speed_limit_i, 
                hazmat_present_i, vehicle_defect
FROM vehicles_full
WHERE vehicle_id IS NOT NULL
ORDER BY vehicle_id;

-- PEOPLE
INSERT INTO people (
    person_id, person_type, crash_record_id, vehicle_id, crash_date,
    sex, age, safety_equipment, airbag_deployed, injury_classification
)
SELECT DISTINCT
    person_id, person_type, crash_record_id, vehicle_id, crash_date,
    sex, age, safety_equipment, airbag_deployed, injury_classification
FROM people_full
WHERE person_id IS NOT NULL
ORDER BY person_id;

INSERT INTO people_driver_info (
    person_id, driver_action, driver_vision, physical_condition,
    bac_result_value, cell_phone_use, drivers_license_class
)
SELECT DISTINCT
    person_id, driver_action, driver_vision, physical_condition,
    bac_result_value, cell_phone_use, drivers_license_class
FROM people_full
WHERE person_id IS NOT NULL
ORDER BY person_id;

-- =====================================================
-- VALIDACIONES FINALES
-- =====================================================

-- Conteo de registros
SELECT 'CRASHES' as tabla, COUNT(*) as registros FROM crashes
UNION ALL SELECT 'CRASH_DATE', COUNT(*) FROM crash_date
UNION ALL SELECT 'CRASH_CIRCUMSTANCES', COUNT(*) FROM crash_circumstances
UNION ALL SELECT 'CRASH_CLASSIFICATION', COUNT(*) FROM crash_classification
UNION ALL SELECT 'CRASH_INJURIES', COUNT(*) FROM crash_injuries
UNION ALL SELECT 'VEHICLES', COUNT(*) FROM vehicles
UNION ALL SELECT 'VEHICLE_SPECS', COUNT(*) FROM vehicle_specs
UNION ALL SELECT 'VEHICLE_MANEUVERS', COUNT(*) FROM vehicle_maneuvers
UNION ALL SELECT 'VEHICLE_VIOLATIONS', COUNT(*) FROM vehicle_violations
UNION ALL SELECT 'PEOPLE', COUNT(*) FROM people
UNION ALL SELECT 'PEOPLE_DRIVER_INFO', COUNT(*) FROM people_driver_info;

-- Verificar integridad referencial
SELECT 'People sin Crash' as issue, COUNT(*) as count
FROM people p
LEFT JOIN crashes c ON p.crash_record_id = c.crash_record_id
WHERE c.crash_record_id IS NULL;

-- Opcional: Eliminar tablas temporales
-- DROP TABLE crashes_full;
-- DROP TABLE vehicles_full;
-- DROP TABLE people_full;