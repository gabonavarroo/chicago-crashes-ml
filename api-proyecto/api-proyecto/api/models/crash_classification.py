"""
Modelos Pydantic para la tabla crash_classification.
Define los schemas de validación para CREATE, READ y UPDATE.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class CreateCrashClassification(BaseModel):
    """
    Schema para crear una nueva clasificación de crash.
    
    Nota: crash_record_id debe existir previamente en la tabla crashes.
    
    Validaciones:
        - crash_record_id: Exactamente 128 caracteres
        - Strings: Longitud máxima según DDL
        - hit_and_run_i: Booleano (acepta True/False, 1/0, "true"/"false")
    """
    crash_record_id: str = Field(
        ...,
        min_length=128,
        max_length=128,
        description="ID del crash (debe existir en crashes)"
    )
    first_crash_type: Optional[str] = Field(
        None,
        max_length=150,
        description="Primer tipo de crash"
    )
    crash_type: Optional[str] = Field(
        None,
        max_length=150,
        description="Tipo de crash"
    )
    prim_contributory_cause: Optional[str] = Field(
        None,
        max_length=255,
        description="Causa contributiva primaria"
    )
    sec_contributory_cause: Optional[str] = Field(
        None,
        max_length=255,
        description="Causa contributiva secundaria"
    )
    damage: Optional[str] = Field(
        None,
        max_length=100,
        description="Nivel de daño"
    )
    hit_and_run_i: Optional[bool] = Field(
        None,
        description="Indicador de hit and run (true/false)"
    )

    @field_validator('crash_record_id')
    @classmethod
    def validate_crash_id_format(cls, v):
        """Valida que el crash_record_id sea hexadecimal en minúsculas."""
        if v and not all(c in '0123456789abcdef' for c in v):
            raise ValueError(
                'crash_record_id debe contener solo caracteres hexadecimales en minúsculas'
            )
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "first_crash_type": "PARKED MOTOR VEHICLE",
                    "crash_type": "ANGLE",
                    "prim_contributory_cause": "FAILING TO YIELD RIGHT-OF-WAY",
                    "sec_contributory_cause": "IMPROPER LANE USAGE",
                    "damage": "$501 - $1,500",
                    "hit_and_run_i": False
                }
            ]
        }
    }


class ReadCrashClassification(BaseModel):
    """
    Schema para leer una clasificación de crash existente.
    """
    crash_record_id: str
    first_crash_type: Optional[str] = None
    crash_type: Optional[str] = None
    prim_contributory_cause: Optional[str] = None
    sec_contributory_cause: Optional[str] = None
    damage: Optional[str] = None
    hit_and_run_i: Optional[bool] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "first_crash_type": "PARKED MOTOR VEHICLE",
                    "crash_type": "ANGLE",
                    "prim_contributory_cause": "FAILING TO YIELD RIGHT-OF-WAY",
                    "sec_contributory_cause": "IMPROPER LANE USAGE",
                    "damage": "$501 - $1,500",
                    "hit_and_run_i": False
                }
            ]
        }
    }


class UpdateCrashClassification(BaseModel):
    """
    Schema para actualizar una clasificación de crash existente.
    Todos los campos son opcionales excepto crash_record_id (no se puede cambiar).
    """
    first_crash_type: Optional[str] = Field(
        None,
        max_length=150
    )
    crash_type: Optional[str] = Field(
        None,
        max_length=150
    )
    prim_contributory_cause: Optional[str] = Field(
        None,
        max_length=255
    )
    sec_contributory_cause: Optional[str] = Field(
        None,
        max_length=255
    )
    damage: Optional[str] = Field(
        None,
        max_length=100
    )
    hit_and_run_i: Optional[bool] = None