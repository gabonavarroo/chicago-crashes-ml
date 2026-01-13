#nueva implementacion

"""
Modelos Pydantic para la tabla people.
Define los schemas de validación para CREATE, READ y UPDATE.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class CreatePeople(BaseModel):
    """
    Schema para crear un nuevo registro de persona.
    
    Nota: person_id NO se incluye porque se genera automáticamente
    en formato Q0000001, Q0000002, etc.
    
    Validaciones:
        - crash_record_id: Debe existir en crashes (si se proporciona)
        - vehicle_id: Debe existir en vehicle (si se proporciona)
        - age: Rango 0 a 120
        - Longitudes máximas de strings
    """
    person_type: Optional[str] = Field(
        None, 
        max_length=50, 
        description="Tipo de persona (DRIVER, PASSENGER, PEDESTRIAN, etc.)"
    )
    crash_record_id: Optional[str] = Field(
        None, 
        description="ID del crash asociado (opcional, debe existir si se proporciona)"
    )
    vehicle_id: Optional[int] = Field(
        None, 
        description="ID del vehículo asociado (opcional, debe existir si se proporciona)"
    )
    sex: Optional[str] = Field(
        None, 
        max_length=10, 
        description="Sexo de la persona (M, F, X, etc.)"
    )
    age: Optional[int] = Field(
        None, 
        ge=0, 
        le=120, 
        description="Edad de la persona (0-120)"
    )
    safety_equipment: Optional[str] = Field(
        None, 
        max_length=200, 
        description="Equipo de seguridad usado"
    )
    airbag_deployed: Optional[str] = Field(
        None, 
        max_length=100, 
        description="Estado del airbag"
    )
    injury_classification: Optional[str] = Field(
        None, 
        max_length=100, 
        description="Clasificación de lesión"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "person_type": "DRIVER",
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "vehicle_id": 10,
                    "sex": "M",
                    "age": 35,
                    "safety_equipment": "SEAT BELT",
                    "airbag_deployed": "DEPLOYED",
                    "injury_classification": "NO INDICATION OF INJURY"
                }
            ]
        }
    }

class ReadPeople(BaseModel):
    """
    Schema para leer un registro de persona existente.
    Incluye person_id generado automáticamente (formato Q0000001).
    """
    person_id: str = Field(
        ..., 
        description="ID único de la persona (formato Q0000001, Q0000002, etc.)"
    )
    person_type: Optional[str] = None
    crash_record_id: Optional[str] = None
    vehicle_id: Optional[int] = None
    sex: Optional[str] = None
    age: Optional[int] = None
    safety_equipment: Optional[str] = None
    airbag_deployed: Optional[str] = None
    injury_classification: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "person_id": "Q0001234",
                    "person_type": "DRIVER",
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "vehicle_id": 10,
                    "sex": "M",
                    "age": 35,
                    "safety_equipment": "SEAT BELT",
                    "airbag_deployed": "DEPLOYED",
                    "injury_classification": "NO INDICATION OF INJURY"
                }
            ]
        }
    }

class UpdatePeople(BaseModel):
    """
    Schema para actualizar un registro de persona.
    Todos los campos son opcionales.
    
    Nota: person_id NO puede actualizarse (es PK)
    """
    person_type: Optional[str] = Field(
        None, 
        max_length=50
    )
    crash_record_id: Optional[str] = Field(
        None, 
        description="Nuevo crash_record_id (debe existir si se proporciona)"
    )
    vehicle_id: Optional[int] = Field(
        None, 
        description="Nuevo vehicle_id (debe existir si se proporciona)"
    )
    age: Optional[int] = Field(
        None, 
        ge=0, 
        le=120
    )
    safety_equipment: Optional[str] = Field(
        None, 
        max_length=200
    )
    airbag_deployed: Optional[str] = Field(
        None, 
        max_length=100
    )
    injury_classification: Optional[str] = Field(
        None, 
        max_length=100
    )
    
