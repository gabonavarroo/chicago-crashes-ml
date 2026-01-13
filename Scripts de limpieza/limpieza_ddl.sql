UPDATE people
SET
    person_type = NULLIF(person_type, ''),
    crash_record_id = NULLIF(crash_record_id, ''),
    safety_equipment = NULLIF(safety_equipment, ''),
    airbag_deployed = NULLIF(airbag_deployed, ''),
    injury_classification = NULLIF(injury_classification, ''),
    sex = NULLIF(sex, '')
WHERE
    person_type = '' OR
    crash_record_id = '' OR
    safety_equipment = '' OR
    airbag_deployed = '' OR
    injury_classification = '' OR
    sex = '';
    

UPDATE vehicle
SET
    unit_type       = NULLIF(unit_type, ''),
    make            = NULLIF(make, ''),
    model           = NULLIF(model, ''),
    vehicle_type    = NULLIF(vehicle_type, '')
WHERE
    unit_type = '' OR
    make = '' OR
    model = '' OR
    vehicle_type = '';



UPDATE vehicle_specs
SET
    vehicle_use      = NULLIF(BTRIM(vehicle_use), ''),
    vehicle_config   = NULLIF(BTRIM(vehicle_config), ''),
    cargo_body_type  = NULLIF(BTRIM(cargo_body_type), '')
WHERE
    BTRIM(vehicle_use) = ''
    OR BTRIM(vehicle_config) = ''
    OR BTRIM(cargo_body_type) = '';
    
UPDATE vehicle_maneuvers
SET manuever = NULL
WHERE manuever = '';

UPDATE driver_info
SET
    driver_action         = NULLIF(BTRIM(driver_action), ''),
    driver_vision         = NULLIF(BTRIM(driver_vision), ''),
    physical_condition    = NULLIF(BTRIM(physical_condition), ''),
    drivers_license_class = NULLIF(BTRIM(drivers_license_class), '')
WHERE
    BTRIM(driver_action) = ''
    OR BTRIM(driver_vision) = ''
    OR BTRIM(physical_condition) = ''
    OR BTRIM(drivers_license_class) = '';

UPDATE crash_injuries
SET
    injuries_fatal = COALESCE(injuries_fatal, 0),
    injuries_incapacitating = COALESCE(injuries_incapacitating, 0),
    injuries_other = COALESCE(injuries_other, 0)
WHERE 
    injuries_fatal IS NULL
    OR injuries_incapacitating IS NULL
    OR injuries_other IS NULL;

UPDATE crash_classification
SET
    first_crash_type        = NULLIF(BTRIM(first_crash_type), ''),
    crash_type              = NULLIF(BTRIM(crash_type), ''),
    prim_contributory_cause = NULLIF(BTRIM(prim_contributory_cause), ''),
    sec_contributory_cause  = NULLIF(BTRIM(sec_contributory_cause), ''),
    damage                  = NULLIF(BTRIM(damage), '')
WHERE
    BTRIM(first_crash_type) = ''
    OR BTRIM(crash_type) = ''
    OR BTRIM(prim_contributory_cause) = ''
    OR BTRIM(sec_contributory_cause) = ''
    OR BTRIM(damage) = '';


