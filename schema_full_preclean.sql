DROP TABLE IF EXISTS people_full;

CREATE TABLE people_full (
    -- Identificadores
    person_id                VARCHAR(50) PRIMARY KEY,
    person_type              TEXT,
    crash_record_id          VARCHAR(128),
    vehicle_id               TEXT,

    -- Fecha
    crash_date               TIMESTAMP,

    -- Ubicación y demografía
    seat_no                  TEXT,
    city                     TEXT,
    state_                    TEXT,
    zipcode                  TEXT,
    sex                      TEXT,
    age                      INT,

    -- Licencia
    drivers_license_state    TEXT,
    drivers_license_class    TEXT,

    -- Seguridad
    safety_equipment         TEXT,
    airbag_deployed          TEXT,
    ejection                 TEXT,

    -- Lesión y atención médica
    injury_classification    TEXT,
    hospital                 TEXT,
    ems_agency               TEXT,
    ems_run_no               TEXT,

    -- Conductor
    driver_action            TEXT,
    driver_vision            TEXT,
    physical_condition       TEXT,

    -- Peatón / ciclista
    pedpedal_action          TEXT,
    pedpedal_visibility      TEXT,
    pedpedal_location        TEXT,

    -- Alcohol
    bac_result               TEXT,
    bac_result_value         NUMERIC,

    -- Celular
    cell_phone_use           TEXT
);

-- =========================
-- DROP columnas innecesarias
-- =========================

ALTER TABLE people_full
    DROP COLUMN city,
    DROP COLUMN state_,
    DROP COLUMN zipcode;

ALTER TABLE people_full
    ALTER COLUMN person_id TYPE VARCHAR(50) PRIMARY KEY,
    ALTER COLUMN person_type TYPE VARCHAR(50)
    ALTER COLUMN crash_record_id TYPE VARCHAR(128),
    ALTER COLUMN sex TYPE VARCHAR(10),
    ALTER COLUMN vehicle_id TYPE BIGINT,
    ALTER COLUMN safety_equipment TYPE VARCHAR(200),
    ALTER COLUMN airbag_deployed TYPE VARCHAR(100),
    ALTER COLUMN injury_classification TYPE VARCHAR(100).
    ALTER COLUMN hospital TYPE VARCHAR(120),
    ALTER COLUMN ems_agency TYPE VARCHAR(120),
    ALTER COLUMN ems_run_no TYPE VARCHAR(120)
    ALTER COLUMN driver_action          VARCHAR(50),
    ALTER COLUMN driver_vision          VARCHAR(50),
    ALTER COLUMN physical_condition     VARCHAR(50),
    ALTER COLUMN bac_result_value       FLOAT,
    ALTER COLUMN cell_phone_use         BOOLEAN,
    ALTER COLUMN drivers_license_class  VARCHAR(10);
--ESPACIOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO

DROP TABLE IF EXISTS vehicles_full;

CREATE TABLE vehicles_full (
    -- Identificadores
    crash_unit_id              BIGINT,
    crash_record_id            VARCHAR(128),
    crash_date                 TIMESTAMP,
    unit_no                    INT,
    vehicle_id                 BIGINT,

    -- Tipo y conteos
    unit_type                  TEXT,
    num_passengers             INT,
    occupant_cnt               INT,

    -- Identificación del vehículo
    make                       TEXT,
    model                      TEXT,
    lic_plate_state            TEXT,
    vehicle_year               INT,
    vehicle_type               TEXT,
    vehicle_use                TEXT,

    -- Condiciones / comportamiento
    travel_direction           TEXT,
    maneuver                   TEXT,
    towed_i                    TEXT,
    fire_i                     TEXT,
    exceed_speed_limit_i       TEXT,
    cmrc_veh_i                 TEXT,

    -- Defectos y contacto
    vehicle_defect             TEXT,
    first_contact_point        TEXT,

    -- Comercial / carga
    cargo_body_type            TEXT,
    load_type                  TEXT,
    hazmat_present_i           TEXT,

    -- Información de remolque
    towed_by                   TEXT,
    towed_to                   TEXT,

    -- Áreas de daño
    area_00_i                  TEXT,
    area_01_i                  TEXT,
    area_02_i                  TEXT,
    area_03_i                  TEXT,
    area_04_i                  TEXT,
    area_05_i                  TEXT,
    area_06_i                  TEXT,
    area_07_i                  TEXT,
    area_08_i                  TEXT,
    area_09_i                  TEXT,
    area_10_i                  TEXT,
    area_11_i                  TEXT,
    area_12_i                  TEXT,
    area_99_i                  TEXT,

    -- Comercial / transporte pesado
    cmv_id                     BIGINT,
    usdot_no                   TEXT,
    ccmc_no                    TEXT,
    ilcc_no                    TEXT,
    commercial_src             TEXT,
    gvwr                       TEXT,
    carrier_name               TEXT,
    carrier_state              TEXT,
    carrier_city               TEXT,

    -- Hazmat y reportes
    hazmat_placards_i          TEXT,
    hazmat_name                TEXT,
    un_no                      TEXT,
    hazmat_report_i            TEXT,
    hazmat_report_no           TEXT,
    mcs_report_i               TEXT,
    mcs_report_no              TEXT,
    hazmat_vio_cause_crash_i   TEXT,
    mcs_vio_cause_crash_i      TEXT,
    hazmat_out_of_service_i    TEXT,
    mcs_out_of_service_i       TEXT,
    hazmat_class               TEXT,

    -- Permisos y dimensiones
    idot_permit_no             TEXT,
    wide_load_i                TEXT,
    trailer1_width             TEXT,
    trailer2_width             TEXT,
    trailer1_length            INT,
    trailer2_length            INT,
    total_vehicle_length       INT,
    axle_cnt                   INT,
    vehicle_config             TEXT
);

-- =========================
-- DROP columnas innecesarias
-- =========================

ALTER TABLE vehicles_full
    DROP COLUMN lic_plate_state,
    DROP COLUMN vehicle_use,
    DROP COLUMN cmrc_veh_i,
    DROP COLUMN vehicle_defect,
    DROP COLUMN first_contact_point,
    DROP COLUMN towed_by,
    DROP COLUMN towed_to,
    DROP COLUMN area_00_i,
    DROP COLUMN area_01_i,
    DROP COLUMN area_02_i,
    DROP COLUMN area_03_i,
    DROP COLUMN area_04_i,
    DROP COLUMN area_05_i,
    DROP COLUMN area_06_i,
    DROP COLUMN area_07_i,
    DROP COLUMN area_08_i,
    DROP COLUMN area_09_i,
    DROP COLUMN area_10_i,
    DROP COLUMN area_11_i,
    DROP COLUMN area_12_i,
    DROP COLUMN area_99_i,
    DROP COLUMN cmv_id,
    DROP COLUMN usdot_no,
    DROP COLUMN ccmc_no,
    DROP COLUMN ilcc_no,
    DROP COLUMN commercial_src,
    DROP COLUMN gvwr,
    DROP COLUMN carrier_name,
    DROP COLUMN carrier_state,
    DROP COLUMN carrier_city,
    DROP COLUMN hazmat_placards_i,
    DROP COLUMN hazmat_name,
    DROP COLUMN un_no,
    DROP COLUMN hazmat_report_i,
    DROP COLUMN hazmat_report_no,
    DROP COLUMN mcs_report_i,
    DROP COLUMN mcs_report_no,
    DROP COLUMN hazmat_vio_cause_crash_i,
    DROP COLUMN mcs_vio_cause_crash_i,
    DROP COLUMN hazmat_out_of_service_i,
    DROP COLUMN mcs_out_of_service_i,
    DROP COLUMN hazmat_class,
    DROP COLUMN idot_permit_no,
    DROP COLUMN wide_load_i,
    DROP COLUMN trailer1_width,
    DROP COLUMN trailer2_width,
    DROP COLUMN trailer1_length,
    DROP COLUMN trailer2_length,
    DROP COLUMN total_vehicle_length,
    DROP COLUMN axle_cnt,
    DROP COLUMN vehicle_config;

ALTER TABLE vehicles_full
    ALTER COLUMN vehicle_id TYPE BIGINT PRIMARY KEY,
    ALTER COLUMN crash_unit_id TYPE VARCHAR(128) NOT NULL,
    ALTER COLUMN crash_date TYPE TIMESTAMP NOT NULL,
    ALTER COLUMN unit_no TYPE INTEGER,
    ALTER COLUMN unit_type TYPE VARCHAR(30),
    ALTER COLUMN num_passengers TYPE INTEGER,
    ALTER COLUMN vehicle_year TYPE INTEGER,
    ALTER COLUMN make TYPE VARCHAR(200),
    ALTER COLUMN model TYPE VARCHAR(200),
    ALTER COLUMN vehicle_type TYPE VARCHAR(200),
    ALTER COLUMN vehicle_use TYPE VARCHAR(150),
    ALTER COLUMN vehicle_config TYPE VARCHAR(150),
    ALTER COLUMN cargo_body_type TYPE VARCHAR(150)
	ALTER COLUMN manuever TYPE VARCHAR(150)
	ALTER COLUMN cmrc_veh_i TYPE BOOLEAN,
	ALTER COLUMN exceed_speed_limit_i TYPE BOOLEAN,
	ALTER COLUMN hazmat_present_i TYPE BOOLEAN,
	ALTER COLUMN vehicle_defect TYPE VARCHAR(100);

DROP TABLE IF EXISTS crashes_full;

CREATE TABLE crashes_full (
    crash_record_id              VARCHAR(128) PRIMARY KEY,
    crash_date_est_i             TEXT,
    crash_date                   TIMESTAMP,
    posted_speed_limit           INT,
    traffic_control_device       TEXT,
    device_condition             TEXT,
    weather_condition            TEXT,
    lighting_condition           TEXT,
    first_crash_type             TEXT,
    trafficway_type              TEXT,
    lane_cnt                     INT,
    alignment                    TEXT,
    roadway_surface_cond         TEXT,
    road_defect                  TEXT,
    report_type                  TEXT,
    crash_type                   TEXT,
    intersection_related_i       BOOLEAN,
    not_right_of_way_i           BOOLEAN,
    hit_and_run_i                BOOLEAN,
    damage                       TEXT,
    date_police_notified         TIMESTAMP,
    prim_contributory_cause      TEXT,
    sec_contributory_cause       TEXT,
    street_no                    INT,
    street_direction             TEXT,
    street_name                  TEXT,
    beat_of_occurrence           INT,
    photos_taken_i               BOOLEAN,
    statements_taken_i           BOOLEAN,
    dooring_i                    BOOLEAN,
    work_zone_i                  BOOLEAN,
    work_zone_type               TEXT,
    workers_present_i            BOOLEAN,
    num_units                    INT,
    most_severe_injury           TEXT,
    injuries_total               INT,
    injuries_fatal               INT,
    injuries_incapacitating      INT,
    injuries_non_incapacitating  INT,
    injuries_reported_not_evident INT,
    injuries_no_indication       INT,
    injuries_unknown             INT,
    crash_hour                   INT,
    crash_day_of_week            INT,
    crash_month                  INT,
    latitude                     NUMERIC(9,6),
    longitude                    NUMERIC(9,6),
    location                     POINT
);

-- =========================
-- DROP columnas innecesarias
-- =========================

ALTER TABLE crashes_full
    DROP COLUMN crash_date_est_i,
    DROP COLUMN trafficway_type,
    DROP COLUMN alignment,
    DROP COLUMN roadway_surface_cond,
    DROP COLUMN road_defect,
    DROP COLUMN intersection_related_i,
    DROP COLUMN private_property_i,
    DROP COLUMN hit_and_run_i,
    DROP COLUMN damage,
    DROP COLUMN date_police_notified,
    DROP COLUMN beat_of_occurrence,
    DROP COLUMN work_zone_type,
    DROP COLUMN injuries_reported_not_evident,
    DROP COLUMN location;

ALTER TABLE crashes_full
    ALTER COLUMN crash_record_id TYPE VARCHAR(120),
    ALTER COLUMN traffic_control_device TYPE VARCHAR(100),
	ALTER COLUMN device_condition TYPE VARCHAR(100),0
	ALTER COLUMN weather_condition TYPE VARCHAR(100),
	ALTER COLUMN lighting_condition TYPE VARCHAR(100),
	ALTER COLUMN roadway_surface_cond TYPE VARCHAR(100),
	ALTER COLUMN road_defect VARCHAR(100),
	ALTER COLUMN first_crash_type TYPE VARCHAR(150),
    ALTER COLUMN crash_type TYPE VARCHAR(150),
    ALTER COLUMN prim_contributory_cause TYPE VARCHAR(255),
    ALTER COLUMN sec_contributory_cause TYPE VARCHAR(255),
    ALTER COLUMN damage TYPE VARCHAR(100),
    ALTER COLUMN street_no TYPE VARCHAR(20),
    ALTER COLUMN street_name TYPE VARCHAR(255),
    ALTER COLUMN street_direction TYPE VARCHAR(120),
    ALTER COLUMN report_type TYPE VARCHAR(120);