# Data Contract

## Dataset Grain

- Severity model grain: one row per crash event (`crash_record_id`).
- Hotspot model grain: one row per spatial cell per time bucket.

## Canonical Entities and Field Mappings

### Crash-Level Core Tables (Required)

| Canonical table | Key | Canonical fields used by ML | Mapping notes |
| --- | --- | --- | --- |
| `crashes` | `crash_record_id` (PK) | `crash_record_id`, `crash_date`, `latitude`, `longitude`, `street_no`, `street_name` | If a source exposes `incident_date`, it must be renamed to `crash_date` before ML consumption. |
| `crash_date` | `crash_record_id` (PK/FK -> `crashes`) | `crash_day_of_week`, `crash_month` | One row per crash. |
| `crash_circumstances` | `crash_record_id` (PK/FK -> `crashes`) | `traffic_control_device`, `device_condition`, `weather_condition`, `lighting_condition`, `lane_cnt`, `roadway_surface_cond`, `road_defect`, `num_units`, `posted_speed_limit`, `intersection_related_i`, `not_right_of_way_i` | One row per crash. |
| `crash_classification` | `crash_record_id` (PK/FK -> `crashes`) | `first_crash_type`, `crash_type`, `prim_contributory_cause`, `sec_contributory_cause`, `damage`, `hit_and_run_i` | One row per crash. |
| `crash_injuries` | `crash_record_id` (PK/FK -> `crashes`) | `injuries_fatal`, `injuries_incapacitating`, `injuries_others` | If `injuries_other` exists upstream, map it to `injuries_others`. |

### Optional Joins (Aggregated to Crash Grain)

| Source table(s) | Row-level key(s) | Relationship to crash | Expected ML usage |
| --- | --- | --- | --- |
| `vehicles` | `vehicle_id` (PK), `crash_record_id` (FK -> `crashes`) | One crash can have zero-to-many vehicles | Build crash-level vehicle aggregates (counts, mix of types/uses, etc.). |
| `people` + `people_driver_info` | `person_id` (PK), `crash_record_id` (FK -> `crashes`) | One crash can have zero-to-many people; `people_driver_info` is zero-or-one per person | Build crash-level person/driver aggregates (driver counts, BAC indicators, behavior flags, etc.). |

## Canonical Timestamp and Timezone Policy

- Canonical event timestamp field for ML: `crashes.crash_date`.
- `incident_date` is treated as a legacy alias and must be normalized to `crash_date`.
- Timezone policy: raw timestamps are interpreted as local Chicago civil time (`America/Chicago`) when timezone metadata is missing.
- For cross-region reproducibility, downstream feature pipelines may derive `crash_timestamp_utc`, but `crash_date` remains the contract field name.

## Canonical Injury Fields

- `crash_injuries.injuries_fatal`
- `crash_injuries.injuries_incapacitating`
- `crash_injuries.injuries_others`

These three fields are the only canonical injury totals for ML features/labels. Any `injuries_other` source field must be remapped to `injuries_others`.

## Key Constraints and Expected Cardinality

- Crash grain key: `crashes.crash_record_id` must be unique and non-null.
- Core crash-extension tables (`crash_date`, `crash_circumstances`, `crash_classification`, `crash_injuries`) are one-to-one with `crashes` on `crash_record_id`.
- `vehicles.vehicle_id` is unique and non-null; `vehicles.crash_record_id` is many-to-one into `crashes`.
- `people.person_id` is unique and non-null; `people.crash_record_id` is many-to-one into `crashes`.
- `people.vehicle_id` is optional many-to-one into `vehicles.vehicle_id`.
- `people_driver_info.person_id` is one-to-one with `people.person_id` (at most one driver-info row per person).
- Aggregate layers used by ML (`source_crash_events` / `ml_crash_base`) must collapse vehicle/person joins back to exactly one row per `crash_record_id`.

## Known Schema Ambiguities

The repository currently contains conflicting names across SQL/DDL paths. ML code uses the following exact canonical names:

- Timestamp field: `crashes.crash_date` (not `crashes.incident_date`).
- Injury field set: `injuries_fatal`, `injuries_incapacitating`, `injuries_others` (not `injuries_other`).
- Driver table: `people_driver_info` (not `driver_info`).
- Vehicle table for optional joins: `vehicles` (not `vehicle`).

If upstream sources provide legacy names, rename them during staging so ML-facing SQL sees only the canonical names above.

## Quality Rules

- Primary keys must be unique and non-null.
- Foreign keys must satisfy the cardinality rules defined above.
- Timestamp coverage must be continuous by reporting period.
- Critical categorical fields must meet null and domain thresholds.

## Versioning

- Contract version: `v0.2`.
- Update policy: backward-compatible changes only within a minor version.
