"""
Utilidades para la API Traffic Crashes
"""
from .id_generators import (
    generate_crash_record_id,
    generate_vehicle_id,
    generate_crash_unit_id,
    generate_person_id,
    truncate_coordinates
)

from .validators import (
    validate_coordinates,
    validate_non_negative,
    validate_date_not_future,
    validate_age,
    validate_vehicle_year,
    validate_string_length,
    validate_foreign_key_exists,
    normalize_boolean
)

__all__ = [
    'generate_crash_record_id',
    'generate_vehicle_id',
    'generate_crash_unit_id',
    'generate_person_id',
    'truncate_coordinates',
    'validate_coordinates',
    'validate_non_negative',
    'validate_date_not_future',
    'validate_age',
    'validate_vehicle_year',
    'validate_string_length',
    'validate_foreign_key_exists',
    'normalize_boolean'
]