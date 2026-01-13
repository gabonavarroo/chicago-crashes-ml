"""
Modelos Pydantic para la tabla crash_injuries.
Define los schemas de validación para CREATE, READ y UPDATE.
"""
from pydantic import BaseModel, Field
from typing import Optional


class CreateCrashInjuries(BaseModel):
    """
    Schema para crear información de lesiones en un crash.
    
    Nota: crash_record_id debe corresponder a un crash existente.
    
    Validaciones:
        - crash_record_id: Debe existir en crashes
        - injuries_fatal: No negativo
        - injuries_incapacitating: No negativo
        - injuries_other: No negativo
    """
    crash_record_id: str = Field(
        ..., 
        description="ID único del crash (debe existir en crashes)"
    )
    injuries_fatal: Optional[int] = Field(
        None, 
        ge=0,
        le=100,
        description="Número de lesiones fatales"
    )
    injuries_incapacitating: Optional[int] = Field(
        None, 
        ge=0,
        le=100,
        description="Número de lesiones incapacitantes"
    )
    injuries_other: Optional[int] = Field(
        None, 
        ge=0,
        le=100,
        description="Número de otras lesiones"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "injuries_fatal": 0,
                    "injuries_incapacitating": 2,
                    "injuries_other": 3
                }
            ]
        }
    }


class ReadCrashInjuries(BaseModel):
    """
    Schema para leer información de lesiones en un crash existente.
    """
    crash_record_id: str = Field(
        ..., 
        description="ID único del crash"
    )
    injuries_fatal: Optional[int] = Field(
        None, 
        description="Número de lesiones fatales"
    )
    injuries_incapacitating: Optional[int] = Field(
        None, 
        description="Número de lesiones incapacitantes"
    )
    injuries_other: Optional[int] = Field(
        None, 
        description="Número de otras lesiones"
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "injuries_fatal": 0,
                    "injuries_incapacitating": 2,
                    "injuries_other": 3
                }
            ]
        }
    }


class UpdateCrashInjuries(BaseModel):
    """
    Schema para actualizar información de lesiones de un crash.
    Todos los campos son opcionales.
    
    Nota: crash_record_id NO puede actualizarse (es PK)
    """
    injuries_fatal: Optional[int] = Field(
        None, 
        ge=0,
        le=100,
        description="Nuevo número de lesiones fatales"
    )
    injuries_incapacitating: Optional[int] = Field(
        None, 
        ge=0,
        le=100,
        description="Nuevo número de lesiones incapacitantes"
    )
    injuries_other: Optional[int] = Field(
        None, 
        ge=0,
        le=100,
        description="Nuevo número de otras lesiones"
    )
