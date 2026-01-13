--TABLE: CRASHES

DROP TABLE IF EXISTS crashes;
CREATE TABLE crashes (
crash_record_id VARCHAR(128) PRIMARY KEY,
incident_date TIMESTAMP,
latitude NUMERIC(9,6), 
longitude NUMERIC(9,6),
street_no INTEGER,
street_name VARCHAR(255)
);

DROP TABLE IF EXISTS crash_date;
CREATE TABLE crash_date (
crash_record_id VARCHAR(128) PRIMARY KEY REFERENCES crashes(crash_record_id),
crash_day_of_week INT,
crash_month INT
);

DROP TABLE IF EXISTS crash_circumstances;
CREATE TABLE crash_circumstances (
crash_record_id VARCHAR(128) PRIMARY KEY REFERENCES crashes(crash_record_id), 
traffic_control_device VARCHAR(100),
device_condition VARCHAR(100),
weather_condition VARCHAR(100),
lighting_condition VARCHAR(100),
lane_cnt INT,
roadway_surface_cond VARCHAR(100),
road_defect VARCHAR(100),
num_units INT,
posted_speed_limit INT,
intersection_related_i BOOLEAN,
not_right_of_way_i BOOLEAN
);

DROP TABLE IF EXISTS crash_injuries;
CREATE TABLE crash_injuries (
crash_record_id VARCHAR(128) PRIMARY KEY REFERENCES crashes(crash_record_id),
injuries_fatal INT,
injuries_incapacitating INT,
injuries_other INT
);

DROP TABLE IF EXISTS crash_classification;
CREATE TABLE crash_classification 
(
    crash_record_id          VARCHAR(128) PRIMARY KEY REFERENCES crashes(crash_record_id),
    first_crash_type         VARCHAR(150),
    crash_type               VARCHAR(150),
    prim_contributory_cause  VARCHAR(255),
    sec_contributory_cause   VARCHAR(255),
    damage                   VARCHAR(100),
    hit_and_run_i            BOOLEAN
);


-- ============================
-- TABLE: VEHICLE
-- ============================
DROP TABLE IF EXISTS vehicle;
CREATE TABLE vehicle (
    vehicle_id BIGINT PRIMARY KEY,
    crash_unit_id INTEGER NOT NULL,
    crash_record_id VARCHAR(128) NOT NULL,
    unit_no INTEGER,
    unit_type VARCHAR(30),
    num_passengers INTEGER,
    vehicle_year INTEGER,
    make VARCHAR(200),
    model VARCHAR(200),
    vehicle_type VARCHAR(200),

    CONSTRAINT fk_vehicle_crash
        FOREIGN KEY (crash_record_id)
        REFERENCES crashes (crash_record_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

DROP TABLE IF EXISTS vehicle_specs;
CREATE TABLE vehicle_specs (
    vehicle_id BIGINT PRIMARY KEY REFERENCES vehicle(vehicle_id),
    vehicle_use VARCHAR(150),
    vehicle_config VARCHAR(150),
    cargo_body_type VARCHAR(150)
);

DROP TABLE IF EXISTS vehicle_maneuvers;
CREATE TABLE vehicle_maneuvers (
    vehicle_id BIGINT PRIMARY KEY REFERENCES vehicle(vehicle_id),
    maneuver VARCHAR(150)
);

DROP TABLE IF EXISTS vehicle_violations;
CREATE TABLE vehicle_violations (
vehicle_id BIGINT PRIMARY KEY REFERENCES vehicle(vehicle_id),
cmrc_veh_i BOOLEAN,
exceed_speed_limit_i BOOLEAN,
hazmat_present_i BOOLEAN,
vehicle_defect VARCHAR(100)
);


-- ============================
-- TABLE: people
-- ============================
DROP TABLE IF EXISTS people;
CREATE TABLE people
(
    person_id              VARCHAR(50) PRIMARY KEY,
    person_type            VARCHAR(50),
    crash_record_id        VARCHAR(128),
    vehicle_id             BIGINT,
    sex                    VARCHAR(10),
    age                    INT,
    safety_equipment       VARCHAR(200),
    airbag_deployed        VARCHAR(100),
    injury_classification  VARCHAR(100),

    FOREIGN KEY (crash_record_id) REFERENCES crashes(crash_record_id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicle(vehicle_id)
);

DROP TABLE IF EXISTS driver_info;
CREATE TABLE driver_info
(
    person_id              VARCHAR(128) PRIMARY KEY,
    driver_action          VARCHAR(50),
    driver_vision          VARCHAR(50),
    physical_condition     VARCHAR(50),
    bac_result_value       FLOAT,
    cell_phone_use         BOOLEAN,
    drivers_license_class  VARCHAR(10),

    FOREIGN KEY (person_id) REFERENCES people(person_id)
);



CREATE INDEX idx_people_crash_record_id 
ON people(crash_record_id);

CREATE INDEX idx_crashes_crash_record_id
ON crashes (crash_record_id);


CREATE INDEX CONCURRENTLY idx_crashes_crash_record_id
ON crashes (crash_record_id);


CREATE INDEX idx_crash_date_crash_record_id
ON crash_date (crash_record_id);	

CREATE INDEX idx_vehicle_crash_record_id
ON vehicle (crash_record_id);

CREATE INDEX idx_people_crash_record_id
ON people (crash_record_id);