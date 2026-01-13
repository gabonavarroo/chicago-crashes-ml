"""
Modelos Pydantic para la tabla crash_date.
Define los schemas de validación para CREATE, READ y UPDATE.
"""
from pydantic import BaseModel, Field
from typing import Optional


class CreateCrashDate(BaseModel):
    """
    Schema para crear información temporal de un crash.
    
    Nota: crash_record_id debe corresponder a un crash existente.
    
    Validaciones:
        - crash_record_id: Debe existir en crashes
        - crash_day_of_week: Rango 1-7 (1=Lunes, 7=Domingo)
        - crash_month: Rango 1-12 (1=Enero, 12=Diciembre)
    """
    crash_record_id: str = Field(
        ..., 
        description="ID único del crash (debe existir en crashes)"
    )
    crash_day_of_week: Optional[int] = Field(
        None, 
        ge=1, 
        le=7,
        description="Día de la semana (1=Lunes, 7=Domingo)"
    )
    crash_month: Optional[int] = Field(
        None, 
        ge=1, 
        le=12,
        description="Mes del año (1=Enero, 12=Diciembre)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "crash_day_of_week": 3,
                    "crash_month": 1
                }
            ]
        }
    }


class ReadCrashDate(BaseModel):
    """
    Schema para leer información temporal de un crash existente.
    """
    crash_record_id: str = Field(
        ..., 
        description="ID único del crash"
    )
    crash_day_of_week: Optional[int] = Field(
        None, 
        description="Día de la semana (1=Lunes a 7=Domingo)"
    )
    crash_month: Optional[int] = Field(
        None, 
        description="Mes del año (1=Enero a 12=Diciembre)"
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "crash_day_of_week": 3,
                    "crash_month": 1
                }
            ]
        }
    }


class UpdateCrashDate(BaseModel):
    """
    Schema para actualizar información temporal de un crash.
    Todos los campos son opcionales.
    
    Nota: crash_record_id NO puede actualizarse (es PK)
    """
    crash_day_of_week: Optional[int] = Field(
        None, 
        ge=1, 
        le=7,
        description="Nuevo día de la semana"
    )
    crash_month: Optional[int] = Field(
        None, 
        ge=1, 
        le=12,
        description="Nuevo mes del año"
    )
