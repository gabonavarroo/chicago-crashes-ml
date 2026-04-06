# Data Contract (ML Canonical Entities)

This document defines the **canonical names and joins** that ML feature pipelines must use, even when legacy schema variants exist.

## Canonical crash-level entities (1 row per `crash_record_id`)

These tables are required and joined at crash grain:

- `crashes`
- `crash_date`
- `crash_circumstances`
- `crash_classification`
- `crash_injuries`

### Canonical field mappings

| Domain | Canonical ML field | Source table.field | Notes |
|---|---|---|---|
| Crash key | `crash_record_id` | `crashes.crash_record_id` | Primary crash grain key. |
| Event timestamp | `incident_date` | `crashes.incident_date` | **Canonical timestamp field for ML code**. |
| Date dimensions | `crash_day_of_week`, `crash_month` | `crash_date.crash_day_of_week`, `crash_date.crash_month` | Derived/date dimension fields, not canonical timestamp. |
| Injury fatal | `injuries_fatal` | `crash_injuries.injuries_fatal` | Canonical injury severity field. |
| Injury incapacitating | `injuries_incapacitating` | `crash_injuries.injuries_incapacitating` | Canonical injury severity field. |
| Injury other | `injuries_other` | `crash_injuries.injuries_other` | Canonical name is singular `injuries_other`. |

## Optional joins for aggregate feature layers

These tables are optional and should be pre-aggregated before merging into crash-grain ML datasets:

- Vehicle aggregate layer from `vehicle` (grouped by `crash_record_id`)
- Person/driver aggregate layer from `people` + `driver_info` (grouped by `crash_record_id`)

### Expected cardinality for optional layers

- `crashes` (1) -> (N) `vehicle` via `vehicle.crash_record_id`
- `crashes` (1) -> (N) `people` via `people.crash_record_id`
- `people` (1) -> (0/1) `driver_info` via `driver_info.person_id`

Therefore:

- `vehicle_id` is unique at vehicle grain and is many-to-one into crash grain.
- `person_id` is unique at person grain and is many-to-one into crash grain.
- ML crash-level datasets must aggregate `vehicle`/`people`/`driver_info` records before joining to avoid row explosion.

## Key constraints and relationship contract

### Primary keys

- `crashes.crash_record_id` is the canonical crash key and primary crash grain.
- `crash_date.crash_record_id` is one-to-one to `crashes.crash_record_id`.
- `crash_circumstances.crash_record_id` is one-to-one to `crashes.crash_record_id`.
- `crash_classification.crash_record_id` is one-to-one to `crashes.crash_record_id`.
- `crash_injuries.crash_record_id` is one-to-one to `crashes.crash_record_id`.
- `vehicle.vehicle_id` is vehicle-grain primary key.
- `people.person_id` is person-grain primary key.
- `driver_info.person_id` is one-to-one extension key to `people.person_id`.

### Foreign keys / joins

- `vehicle.crash_record_id` -> `crashes.crash_record_id` (many vehicles per crash).
- `people.crash_record_id` -> `crashes.crash_record_id` (many people per crash).
- `people.vehicle_id` -> `vehicle.vehicle_id` (optional link from person to vehicle).
- `driver_info.person_id` -> `people.person_id` (at most one driver info row per person).

## Canonical timestamp and timezone policy

- **Chosen canonical timestamp field for ML code:** `incident_date` from `crashes`.
- `crash_date` table is treated as date-dimension metadata (weekday/month), not as the canonical event timestamp source.
- Timezone policy:
  - Store and process canonical timestamp as **America/Chicago local crash time** semantics.
  - If pipeline runtime requires timezone-aware values, localize naive `incident_date` to `America/Chicago` before UTC conversion.
  - Do not mix UTC-converted and local-naive timestamps in the same feature table.

## Known schema ambiguities (resolved)

1. **`incident_date` vs `crash_date` (timestamp naming)**
   - Chosen canonical name used by ML code: `incident_date`.

2. **`injuries_other` vs `injuries_others` (injury column naming)**
   - Chosen canonical name used by ML code: `injuries_other`.

3. **`driver_info` vs `people_driver_info` (driver table naming)**
   - Chosen canonical name used by ML code: `driver_info`.
   - `people_driver_info` is treated as a legacy/alternate name and must be mapped to `driver_info` in ingestion normalization when encountered.
